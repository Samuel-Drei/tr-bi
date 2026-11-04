from pathlib import Path

from django.core.management.base import BaseCommand

from dados.importadores import importar_arquivo


class Command(BaseCommand):
    help = "Importa os relatórios do Revenda Mais de uma pasta (ou de um arquivo)."

    def add_arguments(self, parser):
        parser.add_argument("caminho")
        parser.add_argument("--forcar", action="store_true", help="reimporta arquivos já vistos")

    def handle(self, caminho, forcar, **kw):
        p = Path(caminho)
        arquivos = sorted(p.iterdir()) if p.is_dir() else [p]
        for f in arquivos:
            if f.is_dir() or f.suffix.lower() not in (".xls", ".xlsx", ".pdf"):
                continue
            status, tipo, n = importar_arquivo(f, forcar=forcar)
            if status == "desconhecido":
                self.stdout.write(f"?  ignorado (tipo desconhecido): {f.name}")
            elif status == "ja_importado":
                self.stdout.write(f"=  já importado: {f.name}")
            else:
                self.stdout.write(self.style.SUCCESS(f"+  {tipo}: {n} linhas  ({f.name})"))
