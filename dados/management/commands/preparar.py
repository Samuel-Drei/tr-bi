"""Rodado a cada deploy (idempotente): cria o usuário admin e, se pedido, carrega a demonstração."""
import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from dados.models import Importacao, NotaVenda, Veiculo


class Command(BaseCommand):
    help = "Cria o superusuário (DJANGO_SUPERUSER_*) e carrega dados de demonstração (SEED_DEMO=1)."

    def handle(self, **kw):
        U = get_user_model()
        user, senha = os.environ.get("DJANGO_SUPERUSER_USERNAME"), os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if user and senha and not U.objects.filter(username=user).exists():
            U.objects.create_superuser(user, os.environ.get("DJANGO_SUPERUSER_EMAIL", ""), senha)
            self.stdout.write(f"usuário '{user}' criado")
        if os.environ.get("SEED_DEMO") == "1" and not (Importacao.objects.exists() or Veiculo.objects.exists() or NotaVenda.objects.exists()):
            call_command("gerar_demo")
