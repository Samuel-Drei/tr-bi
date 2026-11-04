# Painel da revenda

Painel gerencial para revendas de veículos, alimentado pelos relatórios exportados do Revenda Mais.
Python + Django, um único serviço, Postgres em produção.

**Páginas:** Painel · Vendas · Estoque · Financeiro · Notas fiscais · Clientes · Equipe · Importar dados · Busca global.
Todas as listas têm filtros e exportação CSV. O login é obrigatório.

## Rodar localmente
    pip install -r requirements.txt
    python manage.py migrate
    python manage.py gerar_demo                 # loja fictícia (ou: python manage.py importar "<pasta com os relatórios>")
    python manage.py createsuperuser
    python manage.py runserver                  # http://localhost:8000

Testes: `python manage.py test dados`

## Publicar direto do repositório

### Render (recomendado)
1. **New → Blueprint** e selecione este repositório (usa o `render.yaml`).
2. Informe a senha do administrador (`DJANGO_SUPERUSER_PASSWORD`) quando o Render pedir.
3. Abra a URL gerada e entre com o usuário `admin`.

O primeiro deploy já carrega a loja fictícia (`SEED_DEMO=1`). Para usar dados reais, mude `SEED_DEMO` para `0`
e envie os relatórios pela página **Importar dados**.

### Railway / Heroku / Koyeb
Crie o serviço a partir do repositório (usa o `Procfile`), adicione um Postgres e defina as variáveis abaixo.

### Vercel
Funciona (o Django é detectado pelo `manage.py`), mas o upload pela tela de importação esbarra no limite de 4,5 MB por
requisição. Nesse caso importe pelo seu computador com `DATABASE_URL` apontando para o banco de produção:
`python manage.py importar "<arquivo ou pasta>"`.

## Variáveis de ambiente
| Variável | Função |
|---|---|
| `DJANGO_SECRET_KEY` | obrigatória em produção (sem ela o app não sobe) |
| `DATABASE_URL` | Postgres; sem ela usa SQLite local |
| `LOJA_NOME`, `LOJA_LOCAL` | identidade exibida no painel |
| `DJANGO_SUPERUSER_USERNAME` / `_PASSWORD` / `_EMAIL` | cria o administrador no deploy (comando `preparar`) |
| `SEED_DEMO=1` | carrega a loja fictícia se o banco estiver vazio |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_ORIGINS` | domínios próprios, separados por vírgula |

## Relatórios aceitos
Histórico de estoque (XLS) · Lista Gerencial de Estoque com Margem (XLS) · Lista de Impostos Veículos Vendidos (XLS) ·
Vendas Mensais por Vendedor (PDF) · Relatório Canal de Venda (PDF) · Exportação de clientes (XLSX).
O tipo é reconhecido pelo nome do arquivo; reimportar um período substitui os dados dele, sem duplicar.

## Limitações conhecidas
- Receita, custo e lucro do Painel e de Vendas vêm da lista de impostos: só cobrem vendas com nota fiscal.
- O Fechamento Mensal (PDF em imagem) não é lido automaticamente; lance pelo botão **Lançar fechamento** em Financeiro.
- Uma instalação por loja (sem multiempresa).
