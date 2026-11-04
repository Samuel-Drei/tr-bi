"""Gera uma loja fictícia com 12 meses fechados de histórico, para demonstrações.

Todos os nomes, placas e valores são inventados. Os números são coerentes entre as tabelas
(vendas por vendedor, canais, notas, estoque e fechamento saem da mesma lista de vendas).
"""
import math
import random
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dados.models import (Cliente, EstoqueSnapshot, Fechamento, Importacao, NotaVenda,
                          Veiculo, VendaCanal, VendasVendedorMes)

# marca, modelo, faixa de compra (R$), é moto
CATALOGO = [
    ("Chevrolet", "ONIX 1.0 LT", 42000, 62000, False), ("Chevrolet", "ONIX PLUS PREMIER TURBO", 70000, 92000, False),
    ("Chevrolet", "S10 LTZ 2.8 4X4 DIESEL AUT", 185000, 245000, False), ("Chevrolet", "PRISMA 1.0 LT", 33000, 48000, False),
    ("Volkswagen", "POLO COMFORTLINE 1.0 TSI AUT", 75000, 98000, False), ("Volkswagen", "NIVUS HIGHLINE 1.0 TSI", 100000, 128000, False),
    ("Volkswagen", "GOL 1.0 MPI", 30000, 46000, False), ("Volkswagen", "T-CROSS COMFORTLINE 1.0 TSI", 98000, 125000, False),
    ("Fiat", "MOBI LIKE", 38000, 53000, False), ("Fiat", "STRADA ENDURANCE CS", 70000, 95000, False),
    ("Fiat", "TORO FREEDOM 1.8 AT6", 115000, 148000, False), ("Fiat", "UNO MILLE WAY ECONOMY", 18000, 29000, False),
    ("Toyota", "COROLLA XEI 2.0 FLEX AUT", 105000, 138000, False), ("Toyota", "HILUX CD SRV 4X4 2.8 DIESEL", 220000, 285000, False),
    ("Toyota", "YARIS XL SEDAN 1.5 AUT", 68000, 85000, False), ("Jeep", "COMPASS LONGITUDE 1.3 TURBO", 115000, 155000, False),
    ("Hyundai", "HB20 COMFORT 1.0", 52000, 72000, False), ("Renault", "KWID ZEN 1.0", 36000, 50000, False),
    ("Honda", "CIVIC EXL 2.0 AUT", 105000, 138000, False), ("Ford", "RANGER XLS 3.2 DIESEL 4X4", 190000, 255000, False),
    ("Nissan", "KICKS ADVANCE 1.6 CVT", 90000, 118000, False), ("Caoa Chery", "TIGGO 7 PRO 1.6 TGDI", 115000, 148000, False),
    ("Mitsubishi", "L200 TRITON SPORT HPE-S", 175000, 228000, False), ("Honda", "CG 160 FAN", 11000, 15500, True),
    ("Honda", "BIZ 125", 9000, 13000, True), ("Yamaha", "FACTOR 150 ED", 10000, 14500, True),
]
CORES = ["BRANCO", "PRETO", "PRATA", "CINZA", "VERMELHO", "AZUL"]
CORES_W = [34, 24, 18, 13, 6, 5]
VENDEDORES = [("Carlos Eduardo Lima", 22), ("Fernanda Alves Rocha", 19), ("Rafael Souza Pinto", 16),
              ("Juliana Martins Costa", 14), ("Marcos Vinícius Duarte", 11), ("Patrícia Gomes Ribeiro", 9),
              ("Thiago Barbosa Nunes", 6), ("Aline Cardoso Freitas", 3)]
ORIGENS = [("PRÓPRIO", 62), ("LEAD", 25), ("FEIRÃO", 6), ("REPASSE", 7)]
CANAIS = [("VISITA A LOJA", 55), ("INTERNET", 22), ("POR TELEFONE", 9), ("OUTRO", 8), ("INDICAÇÃO DE AMIGO", 6)]
NOMES = ["Ana", "Bruno", "Carla", "Diego", "Eduarda", "Felipe", "Gabriela", "Henrique", "Isabela", "João", "Karina",
         "Lucas", "Mariana", "Nicolas", "Olívia", "Paulo", "Rafaela", "Samuel", "Tatiane", "Vitor", "Wesley", "Yasmin"]
SOBRENOMES = ["Silva", "Santos", "Oliveira", "Souza", "Pereira", "Lima", "Ferreira", "Costa", "Rodrigues", "Almeida",
              "Nascimento", "Carvalho", "Gomes", "Martins", "Araújo", "Ribeiro", "Barbosa", "Cardoso", "Rocha", "Dias"]
CIDADES = [("Primavera do Leste", "MT", 62), ("Campo Verde", "MT", 9), ("Rondonópolis", "MT", 8), ("Paranatinga", "MT", 6),
           ("Cuiabá", "MT", 6), ("Poxoréu", "MT", 5), ("Sinop", "MT", 4)]


def d(v):
    return Decimal(str(round(v, 2)))


def escolhe(r, pares):
    return r.choices([p[0] for p in pares], weights=[p[1] for p in pares])[0]


def placa(r):
    L = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return f"{r.choice(L)}{r.choice(L)}{r.choice(L)}{r.randint(0, 9)}{r.choice(L + '0123456789')}{r.randint(0, 9)}{r.randint(0, 9)}"


def soma_meses(dt, n):
    i = dt.year * 12 + dt.month - 1 + n
    return date(i // 12, i % 12 + 1, 1)


class Command(BaseCommand):
    help = "Gera dados fictícios de uma loja para demonstração."

    def add_arguments(self, parser):
        parser.add_argument("--forcar", action="store_true", help="apaga os dados existentes (inclusive dados reais!)")
        parser.add_argument("--semente", type=int, default=2026)

    @transaction.atomic
    def handle(self, forcar, semente, **kw):
        if (Importacao.objects.exists() or Veiculo.objects.exists()) and not forcar:
            raise CommandError("Já existem dados neste banco. Use --forcar para apagá-los e gerar a demonstração.")
        for m in (NotaVenda, EstoqueSnapshot, VendasVendedorMes, VendaCanal, Fechamento, Cliente, Veiculo, Importacao):
            m.objects.all().delete()

        r = random.Random(semente)
        hoje = date.today()
        inicio = soma_meses(date(hoje.year, hoje.month, 1), -12)  # 12 meses fechados, até o mês passado
        codigo = 7_000_000

        def novo_codigo():
            nonlocal codigo
            codigo += r.randint(3, 40)
            return str(codigo)

        veiculos, notas, canais, vendas_vm = [], [], [], []
        por_mes = defaultdict(lambda: {"venda": 0.0, "compra": 0.0, "imp": 0.0, "n_prop": 0, "n_cons": 0, "dias": [],
                                       "lanc": 0.0, "n": 0})

        # ---- vendas dos últimos 12 meses
        for k in range(12):
            mes = soma_meses(inicio, k)
            ultimo = (soma_meses(mes, 1) - timedelta(days=1))
            limite = min(ultimo, hoje)
            dias_mes = (limite - mes).days + 1
            base = 38 + 14 * math.sin(k / 12 * 2 * math.pi + 1.2) + r.randint(-5, 5)
            n = max(4, round(base * dias_mes / ((ultimo - mes).days + 1)))
            for _ in range(n):
                marca, modelo, pmin, pmax, moto = r.choice(CATALOGO)
                compra = round(r.uniform(pmin, pmax) / 500) * 500
                margem = r.triangular(0.02, 0.26, 0.10)
                venda = round(compra * (1 + margem) / 100) * 100
                dt_venda = mes + timedelta(days=r.randrange(dias_mes))
                dias = int(min(300, max(2, r.lognormvariate(math.log(32), 0.75))))
                consig = r.random() < 0.18
                pessoa = r.choices(["PF", "PJ"], weights=[64, 36])[0]
                ano_mod = r.randint(hoje.year - 12, hoje.year)
                cod = novo_codigo()
                vend = escolhe(r, VENDEDORES)
                origem = "CONSIGNADO" if consig else escolhe(r, ORIGENS)
                pl = placa(r)
                veiculos.append(Veiculo(
                    codigo=cod, marca=marca, modelo=modelo, ano_fab=ano_mod - r.randint(0, 1), ano_mod=ano_mod,
                    cor=r.choices(CORES, weights=CORES_W)[0], placa=pl, status="USADO",
                    tipo="CONSIG." if consig else "PRÓPRIO", dt_compra=dt_venda - timedelta(days=dias), dt_venda=dt_venda,
                    situacao="Vendido", marcador="CONSIGNADO" if consig else pessoa))
                vendas_vm.append((dt_venda, vend, origem))
                canais.append(VendaCanal(vendedor=vend, dt_venda=dt_venda, modelo=modelo, placa=pl, canal=escolhe(r, CANAIS)))
                pm = por_mes[(mes.year, mes.month)]
                pm["n"] += 1
                pm["dias"].append(dias)
                if consig:
                    pm["n_cons"] += 1
                    continue
                pm["n_prop"] += 1
                lucro_bruto = venda - compra
                imp = {"icms": lucro_bruto * .0482, "pis": lucro_bruto * .0062, "cofins": lucro_bruto * .0286,
                       "irpj": lucro_bruto * .048, "csll": lucro_bruto * .0288}
                base_nota = dict(codigo=cod, dt_venda=dt_venda, modelo=modelo, placa=pl, tipo="PRÓPRIO",
                                 valor_compra=d(compra), localizacao="Pátio")
                notas.append(NotaVenda(cfop="1102", valor_venda=d(compra), **base_nota))
                notas.append(NotaVenda(cfop="5102", valor_venda=d(venda), **{k2: d(v) for k2, v in imp.items()}, **base_nota))
                pm["venda"] += venda
                pm["compra"] += compra
                pm["imp"] += sum(imp.values())
                pm["lanc"] += compra * r.uniform(0.004, 0.035)

        # ---- devolvidos (consignados que voltaram) e histórico de 2 anos antes
        for _ in range(55):
            marca, modelo, pmin, pmax, _m = r.choice(CATALOGO)
            dt_c = hoje - timedelta(days=r.randint(30, 700))
            veiculos.append(Veiculo(codigo=novo_codigo(), marca=marca, modelo=modelo, ano_fab=hoje.year - r.randint(2, 12),
                                    ano_mod=hoje.year - r.randint(1, 11), cor=r.choice(CORES), placa=placa(r), status="USADO",
                                    tipo="CONSIG.", dt_compra=dt_c, dt_venda=dt_c + timedelta(days=r.randint(5, 60)),
                                    situacao="Devolvido", marcador="CONSIGNADO DEVOLVIDO"))

        # ---- estoque atual
        snaps = []
        for _ in range(r.randint(98, 118)):
            marca, modelo, pmin, pmax, _m = r.choice(CATALOGO)
            dias = int(min(330, max(1, r.lognormvariate(math.log(52), 0.8))))
            compra = round(r.uniform(pmin, pmax) / 500) * 500
            lanc = round(compra * r.uniform(0.002, 0.06), 2)
            total = compra + lanc
            preco = round(total * r.triangular(0.96, 1.28, 1.13) / 1000) * 1000 - 100
            cod, ano = novo_codigo(), hoje.year - r.randint(0, 11)
            pl = placa(r)
            consig = r.random() < 0.2
            veiculos.append(Veiculo(codigo=cod, marca=marca, modelo=modelo, ano_fab=ano - 1, ano_mod=ano,
                                    cor=r.choices(CORES, weights=CORES_W)[0], placa=pl, status="USADO",
                                    tipo="CONSIG." if consig else "PRÓPRIO", dt_compra=hoje - timedelta(days=dias),
                                    situacao="Estoque", marcador="CONSIG. DENTRO DA LJ" if consig else "PF"))
            snaps.append(EstoqueSnapshot(data_ref=hoje, codigo=cod, marca=marca.upper(), modelo=modelo, ano=f"{ano - 1}/{ano}",
                                         cor=r.choice(CORES), placa=pl, dias=dias, custo_compra=d(compra),
                                         custo_lancamentos=d(lanc), custo_total=d(total), valor_venda=d(preco)))

        Veiculo.objects.bulk_create(veiculos, batch_size=500)
        NotaVenda.objects.bulk_create(notas, batch_size=500)
        VendaCanal.objects.bulk_create(canais, batch_size=500)
        EstoqueSnapshot.objects.bulk_create(snaps, batch_size=500)

        # ---- vendas por vendedor/mês (mesma lista de vendas)
        cont = defaultdict(int)
        for dt, vend, origem in vendas_vm:
            cont[(dt.year, dt.month, vend, origem)] += 1
        VendasVendedorMes.objects.bulk_create([
            VendasVendedorMes(ano=a, mes=m, rotulo=f"{v.upper()} - {o}", vendedor=v, origem=o, qtd=q)
            for (a, m, v, o), q in cont.items()])

        # ---- fechamento mensal
        est_total = float(sum(s.custo_total for s in snaps))
        fechs = []
        for (ano, mes), pm in sorted(por_mes.items()):
            venda, compra = pm["venda"], pm["compra"]
            comissao = venda * r.uniform(.004, .007)
            financ = venda * r.uniform(.006, .011)
            desp = pm["n_prop"] * r.uniform(280, 360)
            margem = venda - compra - pm["lanc"] - comissao - pm["imp"] + financ + desp
            estoque = est_total * r.uniform(.86, 1.08)
            fechs.append(Fechamento(
                mes=date(ano, mes, 1), receita_vendas=d(venda), custo_mercadorias=d(compra), custo_lancamentos=d(pm["lanc"]),
                custo_comissoes=d(comissao), custo_impostos=d(pm["imp"]), receita_financeiras=d(financ),
                receita_despachante=d(desp), custo_despachante=0, diferenca_quitacao=d(r.uniform(0, venda * .001)),
                margem_bruta=d(margem), estoque_proprio=d(estoque), contas_pagar=d(estoque * r.uniform(.8, 1.1)),
                contas_receber=d(venda * r.uniform(.35, .6)), vendas_proprio=pm["n_prop"], vendas_consignado=pm["n_cons"],
                dias_medio_estoque=round(sum(pm["dias"]) / len(pm["dias"])), giro_estoque_pct=d(100 * pm["n"] / max(1, len(snaps))),
                recebimentos=d(venda * r.uniform(1.0, 1.25)), pagamentos=d(venda * r.uniform(1.0, 1.3))))
        Fechamento.objects.bulk_create(fechs)

        # ---- clientes fictícios (documentos mascarados)
        clientes = []
        for i in range(1800):
            cidade, uf, _w = r.choices(CIDADES, weights=[c[2] for c in CIDADES])[0]
            comprou = r.random() < 0.34
            pj = r.random() < 0.06
            nome = f"{r.choice(NOMES)} {r.choice(SOBRENOMES)} {r.choice(SOBRENOMES)}"
            cadastro = hoje - timedelta(days=r.randint(5, 2100))
            clientes.append(Cliente(
                clie_cod=str(5_000_000 + i), pessoa="Jurídica" if pj else "Física",
                cpf_cnpj=(f"**.{r.randint(100, 999)}.{r.randint(100, 999)}/0001-**" if pj
                          else f"***.{r.randint(100, 999)}.{r.randint(100, 999)}-**"),
                nome=(nome + " Ltda") if pj else nome, cidade=cidade, estado=uf,
                grupos=r.choices(["CLIENTES", "CLIENTES | FORNECEDORES", "FORNECEDORES"], weights=[70, 15, 15])[0],
                dt_cadastro=cadastro,
                dt_ultima_compra=cadastro + timedelta(days=r.randint(0, max(0, (hoje - cadastro).days))) if comprou else None,
                qtd_veiculos_comprados=r.choices([1, 2, 3], weights=[78, 16, 6])[0] if comprou else 0))
        Cliente.objects.bulk_create(clientes, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f"Demonstração gerada: {len(veiculos)} veículos, {len(vendas_vm)} vendas, {len(snaps)} em estoque, "
            f"{len(fechs)} fechamentos, {len(clientes)} clientes."))
