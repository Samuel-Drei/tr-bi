import hashlib
from pathlib import Path

from django.core.management.base import BaseCommand

from dados.importadores import detectar
from dados.models import Importacao


class Command(BaseCommand):
    help = "Importa os relatórios do Revenda Mais de uma pasta (ou de um arquivo)."

    def add_arguments(self, parser):
        parser.add_argument("caminho")
        parser.add_argument("--forcar", action="store_true", help="reimporta arquivos já vistos")

    def handle(self, caminho, forcar, **kw):
        p = Path(caminho)
        arquivos = sorted(p.iterdir()) if p.is_dir() else [p]
        for f in arquivos:
            if f.suffix.lower() not in (".xls", ".xlsx", ".pdf") or f.is_dir():
                continue
            tipo, fn = detectar(f.name)
            if not fn:
                self.stdout.write(f"?  ignorado (tipo desconhecido): {f.name}")
                continue
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            if not forcar and Importacao.objects.filter(sha256=h).exists():
                self.stdout.write(f"=  já importado: {f.name}")
                continue
            n, ini, fim = fn(str(f))
            Importacao.objects.update_or_create(
                sha256=h, defaults=dict(arquivo=f.name, tipo=tipo, linhas=n, periodo_ini=ini, periodo_fim=fim))
            self.stdout.write(self.style.SUCCESS(f"+  {tipo}: {n} linhas  ({f.name})"))
