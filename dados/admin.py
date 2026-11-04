from django.contrib import admin

from . import models

admin.site.site_header = "Administração"
admin.site.site_title = "Administração"
admin.site.index_title = "Dados da revenda"

# nomes legíveis no admin (sem exigir migração)
NOMES = {
    "importacao": ("Importação", "Importações"), "veiculo": ("Veículo", "Veículos"),
    "cliente": ("Cliente", "Clientes"), "notavenda": ("Nota de venda", "Notas de venda"),
    "estoquesnapshot": ("Posição de estoque", "Posições de estoque"),
    "vendasvendedormes": ("Vendas por vendedor/mês", "Vendas por vendedor/mês"),
    "vendacanal": ("Venda por canal", "Vendas por canal"), "fechamento": ("Fechamento mensal", "Fechamentos mensais"),
}
for m in (models.Importacao, models.Veiculo, models.Cliente, models.NotaVenda,
          models.EstoqueSnapshot, models.VendasVendedorMes, models.VendaCanal, models.Fechamento):
    admin.site.register(m)

for m in (models.Importacao, models.Veiculo, models.Cliente, models.NotaVenda, models.EstoqueSnapshot,
          models.VendasVendedorMes, models.VendaCanal, models.Fechamento):
    m._meta.verbose_name, m._meta.verbose_name_plural = NOMES[m._meta.model_name]
