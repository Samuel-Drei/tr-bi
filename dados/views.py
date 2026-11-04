from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render

from .models import (EstoqueSnapshot, Importacao, NotaVenda, Veiculo, VendaCanal,
                     VendasVendedorMes)

MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MES_LONGO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
             "agosto", "setembro", "outubro", "novembro", "dezembro"]
CORES = ["#f5a623", "#1f2937", "#16c79a", "#fb7185", "#c9bfa5"]
PERIODOS = {"mes": 1, "3m": 3, "6m": 6, "ano": 0}
PERIODO_ROTULO = {"mes": "Mês atual", "3m": "Últimos 3 meses", "6m": "Últimos 6 meses", "ano": "Ano todo"}


def brl(v, compacto=False):
    v = float(v or 0)
    if compacto and abs(v) >= 1_000_000:
        return f"R$ {v / 1_000_000:.2f} mi".replace(".", ",")
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if v < 0 else ''}R$ {s}"


def ym(d):
    return d.year * 12 + d.month - 1


def ym_to_date(i):
    return date(i // 12, i % 12 + 1, 1)


def delta(atual, anterior):
    if not anterior:
        return None
    return round((float(atual) - float(anterior)) / abs(float(anterior)) * 100, 1)


def soma_nf(ini_ym, fim_ym):
    """Totais das vendas com nota (CFOP 5102) entre dois índices de mês, inclusive."""
    ini, fim = ym_to_date(ini_ym), ym_to_date(fim_ym + 1)
    qs = NotaVenda.objects.filter(cfop="5102", dt_venda__gte=ini, dt_venda__lt=fim)
    a = qs.aggregate(v=Sum("valor_venda"), c=Sum("valor_compra"), i=Sum("icms"), p=Sum("pis"),
                     cf=Sum("cofins"), ir=Sum("irpj"), cs=Sum("csll"), n=Count("codigo", distinct=True))
    z = Decimal(0)
    imp = sum((a[k] or z) for k in ("i", "p", "cf", "ir", "cs"))
    v, c = a["v"] or z, a["c"] or z
    return {"venda": v, "compra": c, "impostos": imp, "lucro": v - c - imp, "n": a["n"] or 0}


@login_required
def painel(request):
    p = request.GET.get("p", "mes")
    if p not in PERIODOS:
        p = "mes"

    ultima = NotaVenda.objects.order_by("-dt_venda").values_list("dt_venda", flat=True).first() or date.today()
    ref = ym(ultima)
    meses_p = PERIODOS[p] or (ultima.month)
    ini, fim = ref - meses_p + 1, ref
    ini_ant, fim_ant = ini - meses_p, ini - 1

    atual, anterior = soma_nf(ini, fim), soma_nf(ini_ant, fim_ant)

    # séries mensais (todos os meses com dados) -------------------------------------------------
    primeiro = NotaVenda.objects.order_by("dt_venda").values_list("dt_venda", flat=True).first() or ultima
    serie_meses = list(range(ym(primeiro), ref + 1))
    mensal = {m: soma_nf(m, m) for m in serie_meses}
    rot = [f"{MES[m % 12]}" for m in serie_meses]

    # estoque ----------------------------------------------------------------------------------
    data_ref = EstoqueSnapshot.objects.order_by("-data_ref").values_list("data_ref", flat=True).first()
    est = list(EstoqueSnapshot.objects.filter(data_ref=data_ref)) if data_ref else []
    n_est = len(est)
    custo_est = sum((e.custo_total for e in est), Decimal(0))
    dias_med = round(sum(e.dias for e in est) / n_est) if n_est else 0
    entradas = defaultdict(int)
    for d in Veiculo.objects.filter(dt_compra__isnull=False).values_list("dt_compra", flat=True):
        entradas[ym(d)] += 1
    ent_serie = [entradas.get(m, 0) for m in serie_meses]

    def pct(k):
        return round(100 * k / n_est) if n_est else 0

    comp = [
        ("Até 60 dias", pct(sum(1 for e in est if e.dias <= 60))),
        ("Até 90 dias", pct(sum(1 for e in est if e.dias <= 90))),
        ("Margem positiva", pct(sum(1 for e in est if e.margem > 0))),
        ("Margem ≥ 10%", pct(sum(1 for e in est if e.custo_total and e.margem / e.custo_total >= Decimal("0.10")))),
    ]
    score = round(sum(c[1] for c in comp) / len(comp)) if comp else 0
    selo = "Bom" if score >= 70 else ("Atenção" if score >= 50 else "Crítico")
    parados = [e for e in est if e.dias > 90]
    parados_valor = sum((e.custo_total for e in parados), Decimal(0))

    # vendas por vendedor / origem --------------------------------------------------------------
    linhas = list(VendasVendedorMes.objects.all())
    por_v = defaultdict(lambda: defaultdict(int))
    por_origem = defaultdict(int)
    total_p = total_ant = 0
    for l in linhas:
        m = l.ano * 12 + l.mes - 1
        por_v[l.vendedor][m] += l.qtd
        if ini <= m <= fim:
            total_p += l.qtd
            por_origem[l.origem] += l.qtd
        if ini_ant <= m <= fim_ant:
            total_ant += l.qtd
    vend_rows = []
    for nome, d in por_v.items():
        if nome.upper().startswith("VENDAS FEIR"):
            continue
        atu = sum(q for m, q in d.items() if ini <= m <= fim)
        ant = sum(q for m, q in d.items() if ini_ant <= m <= fim_ant)
        if atu == 0 and ant == 0:
            continue
        vend_rows.append({
            "nome": nome, "atual": atu, "delta": atu - ant,
            "part": round(100 * atu / total_p) if total_p else 0,
            "serie": [d.get(m, 0) for m in serie_meses],
            "ano": sum(d.values()),
        })
    vend_rows.sort(key=lambda r: (-r["atual"], -r["ano"]))
    vend_rows = vend_rows[:4]

    # composição (donut) -----------------------------------------------------------------------
    def top(d, n=4):
        itens = sorted(d.items(), key=lambda x: -x[1])
        if len(itens) > n:
            itens = itens[:n] + [("Outros", sum(v for _, v in itens[n:]))]
        return itens

    ini_d, fim_d = ym_to_date(ini), ym_to_date(fim + 1)
    por_canal = defaultdict(int)
    for c, n in VendaCanal.objects.values_list("canal").annotate(n=Count("id")):
        por_canal[c.title()] += n
    por_pessoa = defaultdict(int)
    for m in Veiculo.objects.filter(situacao="Vendido", dt_venda__gte=ini_d, dt_venda__lt=fim_d).values_list("marcador", flat=True):
        k = "Pessoa Física" if m.startswith("PF") else "Pessoa Jurídica" if m.startswith("PJ") else \
            "Consignado" if "CONSIG" in m else "Outros"
        por_pessoa[k] += 1
    abas = {}
    for chave, titulo, dados in (("origem", "Por Origem", por_origem), ("canal", "Por Canal", por_canal),
                                 ("pessoa", "Por Cliente", por_pessoa)):
        itens = top({k.title() if k.isupper() else k: v for k, v in dados.items()})
        tot = sum(v for _, v in itens)
        abas[chave] = {"titulo": titulo, "total": tot, "itens": [
            {"nome": n, "valor": v, "pct": round(100 * v / tot) if tot else 0, "cor": CORES[i]}
            for i, (n, v) in enumerate(itens)]}

    # últimas movimentações ---------------------------------------------------------------------
    mov = []
    for n in NotaVenda.objects.filter(cfop__in=["5102", "1102"]).order_by("-dt_venda", "-id")[:4]:
        venda = n.cfop == "5102"
        mov.append({"titulo": n.modelo.title()[:30], "sub": f"{'Venda' if venda else 'Compra'} · {n.placa}",
                    "valor": ("+ " if venda else "- ") + brl(n.valor_venda if venda else n.valor_compra),
                    "tipo": "pos" if venda else "neg", "data": n.dt_venda.strftime("%d/%m/%Y")})

    vendas_total_nf = atual["n"]
    cobertura = f"{vendas_total_nf} de {total_p}" if total_p else str(vendas_total_nf)
    kpis = [
        {"nome": "Faturamento (c/ NF)", "valor": brl(atual["venda"], True), "delta": delta(atual["venda"], anterior["venda"]),
         "serie": [float(mensal[m]["venda"]) for m in serie_meses], "cor": "#16c79a", "icone": "badge-dollar-sign", "tom": "indigo", "sobe_bom": True},
        {"nome": "Custo dos veículos", "valor": brl(atual["compra"], True), "delta": delta(atual["compra"], anterior["compra"]),
         "serie": [float(mensal[m]["compra"]) for m in serie_meses], "cor": "#ef4444", "icone": "car", "tom": "red", "sobe_bom": False},
        {"nome": "Lucro bruto", "valor": brl(atual["lucro"], True), "delta": delta(atual["lucro"], anterior["lucro"]),
         "serie": [float(mensal[m]["lucro"]) for m in serie_meses], "cor": "#f5a623", "icone": "trending-up", "tom": "indigo", "sobe_bom": True},
        {"nome": "Estoque atual", "valor": brl(custo_est, True), "chip": f"{n_est} veículos",
         "serie": ent_serie, "cor": "#f5a524", "icone": "warehouse", "tom": "orange", "sobe_bom": True,
         "sub": f"{dias_med} dias em média"},
    ]
    for k in kpis:
        d = k.get("delta")
        if d is not None:
            k["abs"], k["seta"], k["bom"] = abs(d), ("↑" if d >= 0 else "↓"), (d >= 0) == k["sobe_bom"]
    imp = Importacao.objects.order_by("-criado_em").first()
    hora = datetime.now().hour
    ctx = {
        "ativo": "painel", "alertas": len(parados) or None,
        "saudacao": "Bom dia" if hora < 12 else "Boa tarde" if hora < 18 else "Boa noite",
        "periodo": p, "periodos": [(k, v) for k, v in PERIODO_ROTULO.items()],
        "periodo_txt": f"{MES[ini % 12]}/{ini // 12} – {MES[fim % 12]}/{fim // 12}",
        "kpis": kpis,
        "grafico": {"labels": rot, "receita": [float(mensal[m]["venda"]) for m in serie_meses],
                    "custo": [float(mensal[m]["compra"]) for m in serie_meses],
                    "lucro": [float(mensal[m]["lucro"]) for m in serie_meses]},
        "cobertura": cobertura, "total_vendas": total_p,
        "saude": {"score": score, "selo": selo, "comp": comp, "parados": len(parados),
                  "parados_valor": brl(parados_valor, True), "tem": bool(n_est)},
        "vendedores": vend_rows, "abas": abas, "mov": mov,
        "ultima_importacao": imp.criado_em.strftime("%d/%m %H:%M") if imp else "—",
        "data_estoque": data_ref.strftime("%d/%m/%Y") if data_ref else "—",
    }
    return render(request, "dados/painel.html", ctx)
