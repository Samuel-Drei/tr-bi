"""Leitores dos relatórios exportados do Revenda Mais.

Cada função recebe o caminho do arquivo, grava no banco de forma idempotente
(apaga o período/foto correspondente e regrava) e devolve (linhas, ini, fim).
"""
import re
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
from django.db import transaction
from lxml import etree

from .models import (Cliente, EstoqueSnapshot, NotaVenda, Veiculo,
                     VendaCanal, VendasVendedorMes)

NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
IDX = "{urn:schemas-microsoft-com:office:spreadsheet}Index"
MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
         "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def linhas_xml(caminho):
    """Lê um .XLS que na verdade é XML Spreadsheet 2003 e devolve lista de listas."""
    saida = []
    for r in etree.parse(caminho).findall(".//ss:Row", NS):
        vals = []
        for c in r.findall("ss:Cell", NS):
            if c.get(IDX):
                while len(vals) < int(c.get(IDX)) - 1:
                    vals.append("")
            d = c.find("ss:Data", NS)
            vals.append((d.text or "") if d is not None else "")
        saida.append(vals)
    return saida


def dec(v):
    try:
        return Decimal(str(v).strip() or "0").quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def data_iso(v):
    v = (v or "").strip()
    return date.fromisoformat(v[:10]) if len(v) >= 10 and v[4] == "-" else None


def data_br(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    d = pd.to_datetime(v, dayfirst=True, errors="coerce")
    return None if pd.isna(d) else d.date()


def data_emissao(texto):
    """'6 de out de 2026 10:38' -> date(2026, 10, 6)"""
    m = re.match(r"(\d{1,2}) de (\w{3}) de (\d{4})", texto or "")
    return date(int(m[3]), MESES[m[2].lower()], int(m[1])) if m else date.today()


def periodo_titulo(texto):
    d = re.findall(r"(\d{2}/\d{2}/\d{4})", texto or "")
    if len(d) >= 2:
        f = lambda s: datetime.strptime(s, "%d/%m/%Y").date()
        return f(d[0]), f(d[1])
    return None, None


# --------------------------------------------------------------------------- estoque histórico
def importar_historico_estoque(caminho):
    linhas = linhas_xml(caminho)
    cab = linhas[0]
    objs = []
    for r in linhas[1:]:
        if len(r) < len(cab) or not r[0].strip():
            continue
        d = dict(zip(cab, r))
        ano = (d.get("Ano") or "").split("/")
        objs.append(Veiculo(
            codigo=d["Codigo"], modelo=d["Modelo"],
            ano_fab=int(ano[0]) if ano[0].isdigit() else None,
            ano_mod=int(ano[1]) if len(ano) > 1 and ano[1].isdigit() else None,
            cor=d.get("Cor", ""), placa=d.get("Placa", ""), status=d.get("Status", ""),
            tipo=d.get("Tipo", ""), dt_compra=data_iso(d.get("Dt. Compra")),
            dt_venda=data_iso(d.get("Dt. Venda")), situacao=d.get("Situação", ""),
            marcador=d.get("Marcador", ""),
        ))
    campos = ["modelo", "ano_fab", "ano_mod", "cor", "placa", "status", "tipo",
              "dt_compra", "dt_venda", "situacao", "marcador"]
    Veiculo.objects.bulk_create(objs, update_conflicts=True, unique_fields=["codigo"],
                                update_fields=campos, batch_size=500)
    datas = [o.dt_venda for o in objs if o.dt_venda]
    return len(objs), min(datas) if datas else None, max(datas) if datas else None


# --------------------------------------------------------------------------- clientes
def importar_clientes(caminho):
    df = pd.read_excel(caminho, dtype=str)
    objs = []
    for _, r in df.iterrows():
        if pd.isna(r.get("clie_cod")):
            continue
        g = lambda k: "" if pd.isna(r.get(k)) else str(r.get(k)).strip()
        qtd = pd.to_numeric(r.get("quantidade_veic_compradas"), errors="coerce")
        objs.append(Cliente(
            clie_cod=g("clie_cod"), cpf_cnpj=g("cpf_cnpj"), pessoa=g("pessoa"),
            nome=g("nome")[:200], cidade=g("cidade"), estado=g("estado")[:2],
            grupos=g("grupos")[:200], dt_cadastro=data_br(r.get("data_cadastro")),
            dt_ultima_compra=data_br(r.get("data_ultima_compra")),
            qtd_veiculos_comprados=0 if pd.isna(qtd) else int(qtd),
        ))
    campos = ["cpf_cnpj", "pessoa", "nome", "cidade", "estado", "grupos",
              "dt_cadastro", "dt_ultima_compra", "qtd_veiculos_comprados"]
    Cliente.objects.bulk_create(objs, update_conflicts=True, unique_fields=["clie_cod"],
                                update_fields=campos, batch_size=500)
    return len(objs), None, None


# --------------------------------------------------------------------------- impostos
def importar_impostos(caminho):
    linhas = linhas_xml(caminho)
    ini, fim = periodo_titulo(" ".join(linhas[0]))
    cab = linhas[2]
    pos = {n: i for i, n in enumerate(cab) if n}
    objs = []
    for r in linhas[3:]:
        if not r or not r[0].isdigit():
            continue
        g = lambda n: r[pos[n]] if pos[n] < len(r) else ""
        objs.append(NotaVenda(
            codigo=g("Código"), dt_venda=data_iso(g("Dt Venda")), modelo=g("Modelo"),
            placa=g("Placa/Chassi"), tipo=g("Tipo"), cfop=g("CFOP"),
            valor_compra=dec(g("Valor Compra")), valor_venda=dec(g("Valor Venda")),
            icms=dec(g("ICMS")), pis=dec(g("PIS")), cofins=dec(g("COFINS")),
            irpj=dec(g("IRPJ")), csll=dec(g("CSLL")), localizacao=g("Localização"),
        ))
    with transaction.atomic():
        NotaVenda.objects.filter(dt_venda__gte=ini, dt_venda__lte=fim).delete()
        NotaVenda.objects.bulk_create(objs, batch_size=500)
    return len(objs), ini, fim


# --------------------------------------------------------------------------- estoque com margem
def importar_estoque_margem(caminho):
    linhas = linhas_xml(caminho)
    ref = data_emissao(linhas[1][0])
    pos = {n: i for i, n in enumerate(linhas[2]) if n}
    objs = []
    for r in linhas[3:]:
        if len(r) <= pos["Código"] or not r[pos["Código"]].isdigit():
            continue
        g = lambda n: r[pos[n]] if pos[n] < len(r) else ""
        objs.append(EstoqueSnapshot(
            data_ref=ref, codigo=g("Código"), marca=g("Marca"), modelo=g("Modelo"),
            ano=g("Ano"), cor=g("Cor"), placa=g("Placa"),
            dias=int(float(g("Dias") or 0)),
            custo_compra=abs(dec(g("Compra"))), custo_lancamentos=abs(dec(g("Lançamentos"))),
            custo_total=abs(dec(g("Total"))), valor_venda=dec(g("Valor p/ Venda")),
        ))
    with transaction.atomic():
        EstoqueSnapshot.objects.filter(data_ref=ref).delete()
        EstoqueSnapshot.objects.bulk_create(objs, batch_size=500)
        for o in objs:  # aproveita a marca para enriquecer o histórico
            Veiculo.objects.filter(codigo=o.codigo, marca="").update(marca=o.marca)
    return len(objs), ref, ref


# --------------------------------------------------------------------------- PDFs
def _texto_pdf(caminho):
    import pdfplumber
    with pdfplumber.open(caminho) as p:
        return [ln for pg in p.pages for ln in (pg.extract_text() or "").splitlines()]


def _origem(txt):
    t = (txt or "").upper().replace("Ó", "O")
    for chave, nome in (("CONSIG", "CONSIGNADO"), ("LEAD", "LEAD"), ("REPASSE", "REPASSE"),
                        ("PROPRI", "PRÓPRIO"), ("FEIR", "FEIRÃO")):
        if chave in t:
            return nome
    return t or "OUTRO"


def importar_vendas_vendedor(caminho):
    linhas = _texto_pdf(caminho)
    cab = next(l for l in linhas if l.startswith("Vendedor/"))
    ano = int(re.search(r"/(\d{4})", cab)[1])
    padrao = re.compile(r"^(.*?)\s+((?:\d+\s+){12}\d+)$")
    regs = []
    for ln in linhas:
        if ln.startswith(("TR MOTORS", "Vendedor/", "Total", "Página", "Pagina")) or "Usuário" in ln \
                or re.match(r"^\d{1,2} de \w{3} de", ln):
            continue
        m = padrao.match(ln)
        if m:
            regs.append([m[1].strip(), [int(x) for x in m[2].split()][:12]])
        elif regs:  # continuação do rótulo que quebrou de linha
            regs[-1][0] += " " + ln.strip()
    objs = []
    for rotulo, meses in regs:
        if " - " in rotulo:
            vend, resto = rotulo.split(" - ", 1)
        elif " % " in rotulo:
            vend, resto = rotulo.split(" % ", 1)
        else:
            vend, resto = rotulo, ""
        origem = _origem(resto or vend)
        for i, q in enumerate(meses, 1):
            if q:
                objs.append(VendasVendedorMes(ano=ano, mes=i, rotulo=rotulo,
                                              vendedor=vend.strip().title(), origem=origem, qtd=q))
    with transaction.atomic():
        VendasVendedorMes.objects.filter(ano=ano).delete()
        VendasVendedorMes.objects.bulk_create(objs)
    return len(objs), date(ano, 1, 1), date(ano, 12, 31)


def importar_canal_venda(caminho):
    linhas = _texto_pdf(caminho)
    ini, fim = periodo_titulo(linhas[0])
    padrao = re.compile(r"^(.+?)\s+(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([A-Z]{3}\d[A-Z0-9]\d{2})\s+(.+)$")
    objs = []
    for ln in linhas[2:]:
        m = padrao.match(ln)
        if m:
            objs.append(VendaCanal(vendedor=m[1].strip().title(),
                                   dt_venda=datetime.strptime(m[2], "%d/%m/%Y").date(),
                                   modelo=m[3], placa=m[4], canal=m[5].strip().upper()))
    with transaction.atomic():
        VendaCanal.objects.filter(dt_venda__gte=ini, dt_venda__lte=fim).delete()
        VendaCanal.objects.bulk_create(objs)
    return len(objs), ini, fim


# --------------------------------------------------------------------------- roteamento
def detectar(nome):
    n = nome.lower()
    if "histórico de estoque" in n or "historico de estoque" in n:
        return "historico_estoque", importar_historico_estoque
    if "exportação de clientes" in n or "exportacao de clientes" in n:
        return "clientes", importar_clientes
    if "lista de impostos" in n:
        return "impostos", importar_impostos
    if "estoque com margem" in n:
        return "estoque_margem", importar_estoque_margem
    if "vendas mensais por vendedor" in n:
        return "vendas_vendedor", importar_vendas_vendedor
    if "canal de venda" in n:
        return "canal_venda", importar_canal_venda
    return None, None
