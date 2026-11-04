from django.contrib import admin

from . import models

for m in (models.Importacao, models.Veiculo, models.Cliente, models.NotaVenda,
          models.EstoqueSnapshot, models.VendasVendedorMes, models.VendaCanal, models.Fechamento):
    admin.site.register(m)
