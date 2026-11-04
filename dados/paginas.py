"""Páginas de lista do painel: cada uma monta filtros, KPIs e linhas; _lista cuida de paginar e exportar CSV."""
import csv
import os
import tempfile
from collections import defaultdict
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .models import (Cliente, EstoqueSnapshot, Fechamento, Importacao, NotaVenda, Veiculo,
                     VendasVendedorMes)
from .views import MES, PERIODO_ROTULO, PERIODOS, brl, ym, ym_to_date

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url="login")


def _pct(v, total):
    return f"{100 * float(v) / float(total):.1f}%".replace(".", ",") if total else "—"


def _periodo(request, padrao="6m"):
    """Lê ?p= e devolve (p, ini_ym, fim_ym, data_ini, data_fim_exclusiva)."""
    p = request.GET.get("p", padrao)
    if p not in PERIODOS:
        p = padrao
    ultima = NotaVenda.objects.order_by("-dt_venda").values_list("dt_venda", flat=True).first() or date.today()
    ref = ym(ultima)
    n = PERIODOS[p] or ultima.month
    ini, fim = ref - n + 1, ref
    return p, ini, fim, ym_to_date(ini), ym_to_date(fim + 1)


def _lista(request, ativo, titulo, sub, cols, itens, to_row, kpis=(), filtros=None, csv_nome="dados",
           por_pagina=50, extra=None, vazio=None):
    """cols: [(rótulo, 'r'|'')]; to_row devolve células str ou (str, classe)."""
    def celulas(item):
        out = []
        for (rot, alin), c in zip(cols, to_row(item)):
            t, cls = c if isinstance(c, tuple) else (c, "")
            out.append((t, f"{alin} {cls}".strip()))
        return out

    if request.GET.get("csv"):
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{csv_nome}.csv"'
        resp.write("﻿")
        w = csv.writer(resp, delimiter=";")
        w.writerow([c[0] for c in cols])
        for i, it in enumerate(itens):
            if i >= 100_000:
                break
            w.writerow([c[0] for c in celulas(it)])
        return resp

    pagina = Paginator(itens, por_pagina).get_page(request.GET.get("pg"))
    qs = request.GET.copy()
    qs.pop("pg", None)
    qs.pop("csv", None)
    csv_qs = request.GET.copy()
    csv_qs.pop("pg", None)
    csv_qs["csv"] = "1"
    ctx = {
        "ativo": ativo, "titulo": titulo, "sub": sub, "cols": cols, "rows": [celulas(i) for i in pagina.object_list],
        "pagina": pagina, "qs": qs.urlencode(), "kpis": kpis, "filtros": filtros,
        "csv_url": "?" + csv_qs.urlencode(), "periodos": list(PERIODO_ROTULO.items()),
        "p": request.GET.get("p", "6m"), "q": request.GET.get("q", ""), "vazio": vazio,
    }
    ctx.update(extra or {})
    return render(request, "dados/lista.html", ctx)


def _lucro_nota(n):
    return n.valor_venda - n.valor_compra - n.impostos


# ---------------------------------------------------------------------------------- vendas
@login_required
def vendas(request):
    p, _ini, _fim, d_ini, d_fim = _periodo(request)
    q = request.GET.get("q", "").strip()
    qs = NotaVenda.objects.filter(cfop="5102", dt_venda__gte=d_ini, dt_venda__lt=d_fim)
    if q:
        qs = qs.filter(Q(modelo__icontains=q) | Q(placa__icontains=q))
    qs = qs.order_by("-dt_venda", "-id")
    a = qs.aggregate(v=Sum("valor_venda"), c=Sum("valor_compra"), i1=Sum("icms"), i2=Sum("pis"), i3=Sum("cofins"),
                     i4=Sum("irpj"), i5=Sum("csll"))
    venda, compra = a["v"] or 0, a["c"] or 0
    imp = sum((a[k] or 0) for k in ("i1", "i2", "i3", "i4", "i5"))
    lucro, n = venda - compra - imp, qs.count()
    kpis = [("Vendas com nota", n, f"{MES[d_ini.month - 1]}/{d_ini.year} em diante"), ("Faturamento", brl(venda, True), None),
            ("Lucro bruto", brl(lucro, True), f"margem {_pct(lucro, venda)}"),
            ("Ticket médio", brl(venda / n if n else 0), None)]

    def row(n):
        lucro = _lucro_nota(n)
        return [n.dt_venda.strftime("%d/%m/%Y"), n.modelo.title(), n.placa, n.tipo.title(), brl(n.valor_compra),
                brl(n.valor_venda), brl(n.impostos), (brl(lucro), "pos" if lucro >= 0 else "neg"),
                _pct(lucro, n.valor_venda)]

    cols = [("Data", ""), ("Veículo", ""), ("Placa", ""), ("Tipo", ""), ("Compra", "r"), ("Venda", "r"),
            ("Impostos", "r"), ("Lucro bruto", "r"), ("Margem", "r")]
    return _lista(request, "vendas", "Vendas", "Vendas com nota fiscal emitida, com custo, impostos e lucro de cada veículo.",
                  cols, qs, row, kpis, {"periodo": True, "busca": "Buscar modelo ou placa"}, "vendas")


# ---------------------------------------------------------------------------------- estoque
@login_required
def estoque(request):
    data_ref = EstoqueSnapshot.objects.order_by("-data_ref").values_list("data_ref", flat=True).first()
    q = request.GET.get("q", "").strip()
    faixa = request.GET.get("faixa", "todos")
    itens = list(EstoqueSnapshot.objects.filter(data_ref=data_ref)) if data_ref else []
    if q:
        ql = q.lower()
        itens = [e for e in itens if ql in e.modelo.lower() or ql in e.placa.lower() or ql in e.marca.lower()]
    total_geral = itens
    filtros_f = {"60": lambda e: e.dias <= 60, "90": lambda e: 60 < e.dias <= 90, "parado": lambda e: e.dias > 90,
                 "neg": lambda e: e.margem < 0}
    if faixa in filtros_f:
        itens = [e for e in itens if filtros_f[faixa](e)]
    itens.sort(key=lambda e: -e.dias)
    custo = sum((e.custo_total for e in itens), 0)
    preco = sum((e.valor_venda for e in itens), 0)
    parados = [e for e in total_geral if e.dias > 90]
    kpis = [("Veículos", len(itens), f"posição de {data_ref:%d/%m/%Y}" if data_ref else None),
            ("Capital em estoque", brl(custo, True), "custo total"), ("Valor de venda", brl(preco, True), None),
            ("Margem projetada", brl(preco - custo, True), _pct(preco - custo, custo) + " sobre o custo"),
            ("Parados > 90 dias", len(parados), brl(sum((e.custo_total for e in parados), 0), True))]

    def row(e):
        cls = "c-ok" if e.dias <= 60 else "c-warn" if e.dias <= 90 else "c-bad"
        return [e.modelo.title(), e.marca.title(), e.ano, e.placa, (f"{e.dias} dias", cls), brl(e.custo_total),
                brl(e.valor_venda), (brl(e.margem), "pos" if e.margem >= 0 else "neg"), _pct(e.margem, e.custo_total)]

    cols = [("Veículo", ""), ("Marca", ""), ("Ano", ""), ("Placa", ""), ("Tempo na loja", "r"), ("Custo total", "r"),
            ("Preço de venda", "r"), ("Margem", "r"), ("Margem %", "r")]
    sel = {"nome": "faixa", "atual": faixa, "opcoes": [("todos", "Todo o estoque"), ("60", "Até 60 dias"),
                                                       ("90", "61 a 90 dias"), ("parado", "Mais de 90 dias"),
                                                       ("neg", "Margem negativa")]}
    return _lista(request, "estoque", "Estoque", "Veículos na loja hoje, com tempo de permanência, custo e margem projetada.",
                  cols, itens, row, kpis, {"busca": "Buscar modelo, marca ou placa", "selects": [sel]}, "estoque",
                  vazio="Nenhum veículo em estoque. Importe a Lista Gerencial de Estoque com Margem.")


# ---------------------------------------------------------------------------------- financeiro
@login_required
def financeiro(request):
    fs = list(Fechamento.objects.order_by("-mes"))
    cres = sorted(fs, key=lambda f: f.mes)
    kpis = []
    if fs:
        u = fs[0]
        kpis = [(f"Receita · {MES[u.mes.month - 1]}/{u.mes.year}", brl(u.receita_vendas, True), None),
                ("Margem bruta", brl(u.margem_bruta, True), _pct(u.margem_bruta, u.receita_vendas) + " da receita"),
                ("Estoque próprio", brl(u.estoque_proprio, True), None),
                ("Saldo de caixa", brl(u.recebimentos - u.pagamentos, True), "recebimentos − pagamentos")]

    def row(f):
        saldo = f.recebimentos - f.pagamentos
        return [f"{MES[f.mes.month - 1]}/{f.mes.year}", brl(f.receita_vendas), brl(f.custo_mercadorias), brl(f.custo_comissoes),
                brl(f.custo_impostos), brl(f.receita_financeiras), (brl(f.margem_bruta), "pos" if f.margem_bruta >= 0 else "neg"),
                _pct(f.margem_bruta, f.receita_vendas), f"{f.vendas_proprio + f.vendas_consignado}",
                f"{f.dias_medio_estoque} dias", (brl(saldo), "pos" if saldo >= 0 else "neg")]

    cols = [("Mês", ""), ("Receita", "r"), ("Custo veículos", "r"), ("Comissões", "r"), ("Impostos", "r"),
            ("Financeiras", "r"), ("Margem bruta", "r"), ("Margem %", "r"), ("Vendas", "r"), ("Dias em estoque", "r"),
            ("Saldo de caixa", "r")]
    grafico = None
    if cres:
        grafico = {"titulo": "Margem bruta por mês", "labels": [f"{MES[f.mes.month - 1]}/{str(f.mes.year)[2:]}" for f in cres],
                   "valores": [float(f.margem_bruta) for f in cres]}
    acao = {"url": "/admin/dados/fechamento/add/", "texto": "+ Lançar fechamento"} if request.user.is_staff else None
    return _lista(request, "financeiro", "Financeiro", "Fechamento mensal: receita, custos, margem bruta e caixa. Custos em valor positivo.",
                  cols, fs, row, kpis, None, "fechamento", extra={"grafico": grafico, "acao": acao},
                  vazio="Nenhum fechamento lançado. Use “Lançar fechamento” com os dados do Fechamento Mensal do Revenda Mais.")


# ---------------------------------------------------------------------------------- equipe
@login_required
def equipe(request):
    p, ini, fim, _di, _df = _periodo(request, "ano")
    n = fim - ini + 1
    ini_ant, fim_ant = ini - n, ini - 1
    por = defaultdict(lambda: defaultdict(int))
    ant = defaultdict(int)
    for l in VendasVendedorMes.objects.all():
        m = l.ano * 12 + l.mes - 1
        if ini <= m <= fim:
            por[l.vendedor][l.origem] += l.qtd
        elif ini_ant <= m <= fim_ant:
            ant[l.vendedor] += l.qtd
    linhas = [{"nome": v, "orig": o, "tot": sum(o.values()), "ant": ant.get(v, 0)} for v, o in por.items()]
    linhas.sort(key=lambda x: -x["tot"])
    total = sum(x["tot"] for x in linhas)
    kpis = [("Vendas no período", total, None), ("Vendedores ativos", len(linhas), None),
            ("Média por vendedor", f"{total / len(linhas):.1f}".replace(".", ",") if linhas else "—", None),
            ("Líder", linhas[0]["nome"] if linhas else "—", f"{linhas[0]['tot']} vendas" if linhas else None)]

    def row(x):
        d = x["tot"] - x["ant"]
        o = x["orig"]
        outros = x["tot"] - o.get("PRÓPRIO", 0) - o.get("LEAD", 0) - o.get("CONSIGNADO", 0)
        return [x["nome"], (str(x["tot"]), "c-ok" if x is linhas[0] else ""), (f"{'↑' if d >= 0 else '↓'} {abs(d)}", "pos" if d >= 0 else "neg"),
                _pct(x["tot"], total), str(o.get("PRÓPRIO", 0)), str(o.get("LEAD", 0)), str(o.get("CONSIGNADO", 0)), str(outros)]

    cols = [("Vendedor", ""), ("Vendas", "r"), ("vs período anterior", "r"), ("Participação", "r"), ("Próprio", "r"),
            ("Lead", "r"), ("Consignado", "r"), ("Outros", "r")]
    return _lista(request, "equipe", "Equipe", "Vendas por vendedor e por origem do cliente no período.", cols, linhas, row, kpis,
                  {"periodo": True}, "equipe", extra={"p": p},
                  vazio="Sem vendas por vendedor. Importe o relatório Vendas Mensais por Vendedor.")


# ---------------------------------------------------------------------------------- clientes
def _doc(c):
    d = "".join(ch for ch in c.cpf_cnpj if ch.isdigit())
    if c.pessoa == "Física" and len(d) == 11:
        return f"•••.{d[3:6]}.{d[6:9]}-••"
    return c.cpf_cnpj or "—"


@login_required
def clientes(request):
    q = request.GET.get("q", "").strip()
    pessoa = request.GET.get("pessoa", "")
    comprou = request.GET.get("compraram", "")
    qs = Cliente.objects.all()
    if q:
        dig = "".join(ch for ch in q if ch.isdigit())
        qs = qs.filter(Q(nome__icontains=q) | Q(cidade__icontains=q) | (Q(cpf_cnpj__contains=dig) if len(dig) >= 4 else Q(pk__in=[])))
    if pessoa:
        qs = qs.filter(pessoa=pessoa)
    if comprou == "sim":
        qs = qs.filter(qtd_veiculos_comprados__gt=0)
    qs = qs.order_by(F("dt_ultima_compra").desc(nulls_last=True), "nome")
    total = qs.count()
    comp = qs.filter(qtd_veiculos_comprados__gt=0).count()
    cidades = defaultdict(int)
    for c in qs.values_list("cidade", flat=True)[:50000]:
        cidades[c or "—"] += 1
    topc = max(cidades.items(), key=lambda x: x[1]) if cidades else ("—", 0)
    kpis = [("Cadastros", f"{total:,}".replace(",", "."), None), ("Já compraram", f"{comp:,}".replace(",", "."), _pct(comp, total)),
            ("Pessoa jurídica", qs.filter(pessoa="Jurídica").count(), None), ("Principal cidade", topc[0], f"{topc[1]} cadastros")]

    def row(c):
        return [c.nome.title(), c.pessoa, f"{c.cidade}{'/' + c.estado if c.estado else ''}", c.grupos.title(), _doc(c),
                c.dt_cadastro.strftime("%d/%m/%Y") if c.dt_cadastro else "—",
                c.dt_ultima_compra.strftime("%d/%m/%Y") if c.dt_ultima_compra else "—", str(c.qtd_veiculos_comprados)]

    cols = [("Nome", ""), ("Tipo", ""), ("Cidade", ""), ("Grupo", ""), ("Documento", ""), ("Cadastro", ""),
            ("Última compra", ""), ("Veículos", "r")]
    sels = [{"nome": "pessoa", "atual": pessoa, "opcoes": [("", "Todos os tipos"), ("Física", "Pessoa física"), ("Jurídica", "Pessoa jurídica")]},
            {"nome": "compraram", "atual": comprou, "opcoes": [("", "Todos os cadastros"), ("sim", "Só quem já comprou")]}]
    return _lista(request, "clientes", "Clientes", "Base de clientes, fornecedores e parceiros. CPF exibido de forma parcial.",
                  cols, qs, row, kpis, {"busca": "Buscar nome, cidade ou documento", "selects": sels}, "clientes")


# ---------------------------------------------------------------------------------- notas fiscais
@login_required
def notas(request):
    p, _ini, _fim, d_ini, d_fim = _periodo(request)
    q = request.GET.get("q", "").strip()
    cfop = request.GET.get("cfop", "")
    qs = NotaVenda.objects.filter(dt_venda__gte=d_ini, dt_venda__lt=d_fim)
    if q:
        qs = qs.filter(Q(modelo__icontains=q) | Q(placa__icontains=q))
    if cfop == "outros":
        qs = qs.exclude(cfop__in=["5102", "1102"])
    elif cfop:
        qs = qs.filter(cfop=cfop)
    qs = qs.order_by("-dt_venda", "-id")
    a = qs.aggregate(i1=Sum("icms"), i2=Sum("pis"), i3=Sum("cofins"), i4=Sum("irpj"), i5=Sum("csll"), v=Sum("valor_venda"))
    tot = [a[k] or 0 for k in ("i1", "i2", "i3", "i4", "i5")]
    venda_5102 = qs.filter(cfop="5102").aggregate(v=Sum("valor_venda"))["v"] or 0
    kpis = [("Notas", qs.count(), None), ("Impostos totais", brl(sum(tot), True), None),
            ("ICMS", brl(tot[0], True), None), ("Carga sobre vendas", _pct(sum(tot), venda_5102), "impostos ÷ faturamento")]

    def row(n):
        return [n.dt_venda.strftime("%d/%m/%Y"), n.modelo.title(), n.placa, n.cfop, brl(n.valor_compra), brl(n.valor_venda),
                brl(n.icms), brl(n.pis), brl(n.cofins), brl(n.irpj), brl(n.csll)]

    cols = [("Data", ""), ("Veículo", ""), ("Placa", ""), ("CFOP", ""), ("Compra", "r"), ("Venda", "r"), ("ICMS", "r"),
            ("PIS", "r"), ("COFINS", "r"), ("IRPJ", "r"), ("CSLL", "r")]
    sel = {"nome": "cfop", "atual": cfop, "opcoes": [("", "Todos os CFOP"), ("5102", "5102 · Saída (venda)"),
                                                     ("1102", "1102 · Entrada (compra)"), ("outros", "Outros")]}
    return _lista(request, "notas", "Notas fiscais", "Notas de entrada e saída dos veículos, com os impostos de cada uma.",
                  cols, qs, row, kpis, {"periodo": True, "busca": "Buscar modelo ou placa", "selects": [sel]}, "notas")


# ---------------------------------------------------------------------------------- importar
ACEITOS = [
    ("Histórico de estoque (.XLS)", "Todos os veículos que passaram pela loja, com datas de compra e venda."),
    ("Lista Gerencial de Estoque com Margem (.XLS)", "Posição atual do estoque com custo e preço de venda."),
    ("Lista de Impostos Veículos Vendidos (.XLS)", "Notas de venda com valores e impostos."),
    ("Vendas Mensais por Vendedor (.PDF)", "Quantidade de vendas por vendedor e origem."),
    ("Relatório Canal de Venda (.PDF)", "Canal de cada venda (loja, internet…)."),
    ("Exportação de clientes (.XLSX)", "Cadastro de clientes e fornecedores."),
]


@login_required
@staff_required
def importar(request):
    resultados = []
    if request.method == "POST":
        from .importadores import importar_arquivo  # carrega pandas/pdfplumber só aqui

        forcar = bool(request.POST.get("forcar"))
        for f in request.FILES.getlist("arquivos"):
            sufixo = os.path.splitext(f.name)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo) as tmp:
                for chunk in f.chunks():
                    tmp.write(chunk)
            try:
                status, tipo, n = importar_arquivo(tmp.name, nome=f.name, forcar=forcar)
                if status == "ok":
                    resultados.append({"arquivo": f.name, "icone": "✓", "cls": "c-ok", "msg": f"{tipo}: {n} linhas importadas."})
                elif status == "ja_importado":
                    resultados.append({"arquivo": f.name, "icone": "=", "cls": "c-warn", "msg": "Arquivo já importado antes (marque “reimportar” para refazer)."})
                else:
                    resultados.append({"arquivo": f.name, "icone": "✕", "cls": "c-bad", "msg": "Tipo de relatório não reconhecido pelo nome do arquivo."})
            except Exception as e:  # relatório fora do formato esperado
                resultados.append({"arquivo": f.name, "icone": "✕", "cls": "c-bad", "msg": f"Falha ao ler: {type(e).__name__}: {e}"[:300]})
            finally:
                os.unlink(tmp.name)
    return render(request, "dados/importar.html", {"ativo": "importar", "resultados": resultados, "aceitos": ACEITOS,
                                                    "historico": Importacao.objects.all()[:15]})


# ---------------------------------------------------------------------------------- busca
@login_required
def buscar(request):
    q = request.GET.get("q", "").strip()
    ctx = {"ativo": "", "q": q, "q_busca": q}
    if q:
        ctx["veiculos"] = list(Veiculo.objects.filter(Q(modelo__icontains=q) | Q(placa__icontains=q)).order_by("-dt_compra")[:20])
        ctx["clientes"] = list(Cliente.objects.filter(Q(nome__icontains=q)).order_by("nome")[:20])
        tot = defaultdict(int)
        for v, qt in VendasVendedorMes.objects.filter(vendedor__icontains=q).values_list("vendedor", "qtd"):
            tot[v] += qt
        ctx["vendedores"] = sorted(tot.items(), key=lambda x: -x[1])[:20]
    return render(request, "dados/busca.html", ctx)
