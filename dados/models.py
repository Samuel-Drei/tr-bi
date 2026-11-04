from django.db import models


class Importacao(models.Model):
    """Registro de cada arquivo importado; o hash evita processar o mesmo arquivo duas vezes."""

    arquivo = models.CharField(max_length=300)
    tipo = models.CharField(max_length=40)
    sha256 = models.CharField(max_length=64, unique=True)
    linhas = models.PositiveIntegerField(default=0)
    periodo_ini = models.DateField(null=True, blank=True)
    periodo_fim = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.tipo} · {self.arquivo}"


class Veiculo(models.Model):
    """Histórico de estoque: todo veículo que passou pela loja."""

    codigo = models.CharField(max_length=20, primary_key=True)
    marca = models.CharField(max_length=60, blank=True)
    modelo = models.CharField(max_length=120)
    ano_fab = models.PositiveSmallIntegerField(null=True, blank=True)
    ano_mod = models.PositiveSmallIntegerField(null=True, blank=True)
    cor = models.CharField(max_length=40, blank=True)
    placa = models.CharField(max_length=10, blank=True, db_index=True)
    status = models.CharField(max_length=10, blank=True)  # NOVO / USADO
    tipo = models.CharField(max_length=20, blank=True)  # PRÓPRIO / CONSIG.
    dt_compra = models.DateField(null=True, blank=True)
    dt_venda = models.DateField(null=True, blank=True, db_index=True)
    situacao = models.CharField(max_length=20, blank=True, db_index=True)
    marcador = models.CharField(max_length=60, blank=True)  # PF, PJ, CONSIGNADO...

    def __str__(self):
        return f"{self.modelo} {self.placa}"


class Cliente(models.Model):
    clie_cod = models.CharField(max_length=20, primary_key=True)
    cpf_cnpj = models.CharField(max_length=20, blank=True, db_index=True)
    pessoa = models.CharField(max_length=20, blank=True)
    nome = models.CharField(max_length=200)
    cidade = models.CharField(max_length=80, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    grupos = models.CharField(max_length=200, blank=True)
    dt_cadastro = models.DateField(null=True, blank=True)
    dt_ultima_compra = models.DateField(null=True, blank=True)
    qtd_veiculos_comprados = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.nome


class NotaVenda(models.Model):
    """Lista de impostos de veículos vendidos: uma linha por nota (entrada 1102, saída 5102...)."""

    codigo = models.CharField(max_length=20, db_index=True)
    dt_venda = models.DateField(db_index=True)
    modelo = models.CharField(max_length=120)
    placa = models.CharField(max_length=20, blank=True)
    tipo = models.CharField(max_length=20, blank=True)
    cfop = models.CharField(max_length=6, db_index=True)
    valor_compra = models.DecimalField(max_digits=12, decimal_places=2)
    valor_venda = models.DecimalField(max_digits=12, decimal_places=2)
    icms = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pis = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cofins = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    irpj = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    csll = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    localizacao = models.CharField(max_length=40, blank=True)

    @property
    def impostos(self):
        return self.icms + self.pis + self.cofins + self.irpj + self.csll


class EstoqueSnapshot(models.Model):
    """Foto diária da Lista Gerencial de Estoque com Margem."""

    data_ref = models.DateField(db_index=True)
    codigo = models.CharField(max_length=20)
    marca = models.CharField(max_length=60, blank=True)
    modelo = models.CharField(max_length=120)
    ano = models.CharField(max_length=10, blank=True)
    cor = models.CharField(max_length=40, blank=True)
    placa = models.CharField(max_length=10, blank=True)
    dias = models.PositiveIntegerField(default=0)
    custo_compra = models.DecimalField(max_digits=12, decimal_places=2)
    custo_lancamentos = models.DecimalField(max_digits=12, decimal_places=2)
    custo_total = models.DecimalField(max_digits=12, decimal_places=2)
    valor_venda = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = [("data_ref", "codigo")]

    @property
    def margem(self):
        return self.valor_venda - self.custo_total


class VendasVendedorMes(models.Model):
    ano = models.PositiveSmallIntegerField(db_index=True)
    mes = models.PositiveSmallIntegerField()
    rotulo = models.CharField(max_length=200)  # texto original do relatório
    vendedor = models.CharField(max_length=120, db_index=True)
    origem = models.CharField(max_length=30, blank=True)  # PRÓPRIO, LEAD, CONSIGNADO...
    qtd = models.PositiveIntegerField()

    class Meta:
        unique_together = [("ano", "mes", "rotulo")]


class VendaCanal(models.Model):
    vendedor = models.CharField(max_length=120)
    dt_venda = models.DateField(db_index=True)
    modelo = models.CharField(max_length=120)
    placa = models.CharField(max_length=10)
    canal = models.CharField(max_length=60, db_index=True)


class Fechamento(models.Model):
    """Fechamento mensal (PDF do sistema). Lançado à mão no admin até haver relatório em XLS."""

    mes = models.DateField(unique=True, help_text="Primeiro dia do mês")
    receita_vendas = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    custo_mercadorias = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    custo_lancamentos = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    custo_comissoes = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    custo_impostos = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    receita_financeiras = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    receita_despachante = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    custo_despachante = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    diferenca_quitacao = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    margem_bruta = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    estoque_proprio = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    contas_pagar = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    contas_receber = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vendas_proprio = models.PositiveIntegerField(default=0)
    vendas_consignado = models.PositiveIntegerField(default=0)
    dias_medio_estoque = models.PositiveIntegerField(default=0)
    giro_estoque_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    recebimentos = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    pagamentos = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["-mes"]
