from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .importadores import detectar
from .models import Cliente, EstoqueSnapshot, NotaVenda

PAGINAS = ["painel", "vendas", "estoque", "financeiro", "equipe", "clientes", "notas", "buscar"]


class PlataformaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("gerar_demo", forcar=True, verbosity=0)
        U = get_user_model()
        cls.usuario = U.objects.create_user("vendedor", password="senha-teste-123")
        cls.admin = U.objects.create_superuser("admin", password="senha-teste-123")

    def entra(self, u="vendedor"):
        self.client.login(username=u, password="senha-teste-123")

    def test_anonimo_vai_para_login(self):
        for nome in PAGINAS + ["importar"]:
            r = self.client.get(reverse(nome))
            self.assertEqual(r.status_code, 302, nome)
            self.assertIn("/entrar/", r["Location"])

    def test_todas_as_paginas_abrem(self):
        self.entra()
        for nome in PAGINAS:
            r = self.client.get(reverse(nome))
            self.assertEqual(r.status_code, 200, nome)
        for p in ("mes", "3m", "6m", "ano"):
            for nome in ("painel", "vendas", "equipe", "notas"):
                self.assertEqual(self.client.get(reverse(nome), {"p": p}).status_code, 200, f"{nome}?p={p}")

    def test_painel_tem_dados(self):
        self.entra()
        ctx = self.client.get(reverse("painel")).context
        self.assertEqual(len(ctx["kpis"]), 4)
        self.assertTrue(ctx["vendedores"])
        self.assertTrue(ctx["saude"]["tem"])

    def test_exportacao_csv(self):
        self.entra()
        for nome in ("vendas", "estoque", "clientes", "notas", "financeiro", "equipe"):
            r = self.client.get(reverse(nome), {"csv": "1"})
            self.assertEqual(r.status_code, 200, nome)
            self.assertIn("text/csv", r["Content-Type"])
            linhas = r.content.decode("utf-8-sig").strip().splitlines()
            self.assertGreater(len(linhas), 1, nome)

    def test_filtros(self):
        self.entra()
        r = self.client.get(reverse("estoque"), {"faixa": "parado", "csv": "1"})
        n_parados = EstoqueSnapshot.objects.filter(dias__gt=90).count()
        self.assertEqual(len(r.content.decode("utf-8-sig").strip().splitlines()) - 1, n_parados)
        r = self.client.get(reverse("clientes"), {"pessoa": "Jurídica", "csv": "1"})
        self.assertEqual(len(r.content.decode("utf-8-sig").strip().splitlines()) - 1, Cliente.objects.filter(pessoa="Jurídica").count())
        todas = len(self.client.get(reverse("vendas"), {"p": "ano", "csv": "1"}).content.splitlines())
        onix = len(self.client.get(reverse("vendas"), {"p": "ano", "q": "ONIX", "csv": "1"}).content.splitlines())
        self.assertLess(onix, todas)

    def test_paginacao_clientes(self):
        self.entra()
        r = self.client.get(reverse("clientes"), {"pg": 2})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["pagina"].number, 2)

    def test_busca(self):
        self.entra()
        placa = NotaVenda.objects.filter(cfop="5102").first().placa
        r = self.client.get(reverse("buscar"), {"q": placa})
        self.assertTrue(r.context["veiculos"])

    def test_importar_so_para_staff(self):
        self.entra("vendedor")
        self.assertEqual(self.client.get(reverse("importar")).status_code, 302)
        self.client.logout()
        self.entra("admin")
        self.assertEqual(self.client.get(reverse("importar")).status_code, 200)
        arq = SimpleUploadedFile("qualquer-coisa.xls", b"nada")
        r = self.client.post(reverse("importar"), {"arquivos": arq})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["resultados"][0]["icone"], "✕")

    def test_reconhece_tipos_de_relatorio(self):
        casos = {
            "histórico de estoque.XLS": "historico_estoque",
            "exportação de clientes.xlsx": "clientes",
            "Lista de Impostos Veiculos Vendidos_06102026.XLS": "impostos",
            "Lista Gerencial de Estoque com Margem_06102026.XLS": "estoque_margem",
            "Vendas Mensais por Vendedor_24092026 (1).PDF": "vendas_vendedor",
            "Relatorio Canal de Venda_24092026.PDF": "canal_venda",
        }
        for nome, tipo in casos.items():
            self.assertEqual(detectar(nome)[0], tipo, nome)
        self.assertIsNone(detectar("fechamento setembro.pdf")[0])
