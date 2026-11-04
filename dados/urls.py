from django.urls import path

from . import paginas, views

urlpatterns = [
    path("", views.painel, name="painel"),
    path("vendas/", paginas.vendas, name="vendas"),
    path("estoque/", paginas.estoque, name="estoque"),
    path("financeiro/", paginas.financeiro, name="financeiro"),
    path("equipe/", paginas.equipe, name="equipe"),
    path("clientes/", paginas.clientes, name="clientes"),
    path("notas/", paginas.notas, name="notas"),
    path("importar/", paginas.importar, name="importar"),
    path("buscar/", paginas.buscar, name="buscar"),
]
