# 📊 Painel da Revenda

Painel gerencial (BI) para revendas de veículos, alimentado pelos relatórios que o ERP **Revenda Mais** já exporta. Transforma planilhas e PDFs soltos em vendas, estoque, margem e impostos num só lugar, com filtros e exportação.

**[Demo ao vivo](#)** *(loja fictícia)* · Python · Django · PostgreSQL

![Visão geral do painel](docs/painel.png)

---

## Por que existe

O dono de uma revenda acompanha o negócio em relatórios separados do ERP: um para estoque, outro para vendas, outro para impostos. Cada um precisa ser aberto, exportado e cruzado à mão.

O painel lê esses mesmos relatórios, padroniza os dados e mostra o que importa: quanto vendeu, com que margem, quais carros estão parados e quanto de imposto saiu.

Foi construído para uma rede de revenda de veículos de 3 lojas.

---

## O que ele mostra

| Página | Responde |
|---|---|
| **Painel** | Receita, custo, lucro e vendas do período num resumo |
| **Vendas** | O que foi vendido, por vendedor, canal e período |
| **Estoque** | Veículos em estoque, dias parados, custo e valor de venda |
| **Financeiro** | Fechamento mensal, custos, comissões e impostos |
| **Notas fiscais** | Vendas com nota, CFOP e impostos (ICMS, PIS, COFINS, IRPJ, CSLL) |
| **Clientes** | Base de clientes, última compra e veículos comprados |
| **Equipe** | Desempenho por vendedor |
| **Importar dados** | Envio dos relatórios pelo navegador |
| **Busca global** | Procura por placa, modelo ou cliente em todas as páginas |

Todas as listas têm **filtros e exportação CSV**. O **login é obrigatório**.

---

## Como funciona

```text
Relatórios do Revenda Mais          Painel (Django)
┌─────────────────────────┐     ┌───────────────────────────────────┐
│ XLS · XLSX · PDF        │     │ Importadores (Python)             │
│ estoque, vendas,        │ ──► │  reconhece o tipo pelo nome,      │ ──► Postgres ──► Páginas
│ impostos, clientes      │     │  limpa e grava sem duplicar       │                 + CSV
└─────────────────────────┘     └───────────────────────────────────┘
```

- **Leitura de formatos difíceis:** os `.XLS` do ERP são, na verdade, XML Spreadsheet 2003 (lidos com `lxml`); os PDFs são lidos com `pdfplumber`; o XLSX, com `pandas`.
- **Importação idempotente:** reimportar um período substitui os dados dele, sem duplicar.
- **Por que relatórios e não API:** a API pública do Revenda Mais que conhecemos é só de entrada de leads. Por isso a ingestão parte dos relatórios exportados.

### Relatórios aceitos

| Relatório | Formato |
|---|---|
| Histórico de estoque | XLS |
| Lista Gerencial de Estoque com Margem | XLS |
| Lista de Impostos de Veículos Vendidos | XLS |
| Vendas Mensais por Vendedor | PDF |
| Relatório Canal de Venda | PDF |
| Exportação de clientes | XLSX |

O tipo é reconhecido pelo nome do arquivo.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python, Django 5 |
| Banco | PostgreSQL (SQLite local) |
| Dados | pandas, openpyxl, lxml, pdfplumber |
| Servidor | Gunicorn, WhiteNoise |
| Deploy | Render (`render.yaml`), Docker, Procfile |

---

## Rodar localmente

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py gerar_demo        # loja fictícia
# ou: python manage.py importar "<pasta com os relatórios>"
python manage.py createsuperuser
python manage.py runserver         # http://localhost:8000
```

Testes:

```bash
python manage.py test dados
```

---

## Publicar

### Render (recomendado)
1. **New → Blueprint** e selecione este repositório (usa o `render.yaml`).
2. Informe a senha do administrador (`DJANGO_SUPERUSER_PASSWORD`) quando o Render pedir.
3. Abra a URL gerada e entre com o usuário `admin`.

O primeiro deploy carrega a loja fictícia (`SEED_DEMO=1`). Para usar dados reais, mude `SEED_DEMO` para `0` e envie os relatórios pela página **Importar dados**.

### Docker, Railway, Heroku ou Koyeb
Use o `Dockerfile`/`docker-compose.yml` ou o `Procfile`, adicione um Postgres e defina as variáveis abaixo.

### Vercel
Funciona, mas o upload pela tela de importação esbarra no limite de 4,5 MB por requisição. Nesse caso importe pelo computador, com `DATABASE_URL` apontando para o banco de produção:

```bash
python manage.py importar "<arquivo ou pasta>"
```

### Variáveis de ambiente

| Variável | Função |
|---|---|
| `DJANGO_SECRET_KEY` | obrigatória em produção (sem ela o app não sobe) |
| `DATABASE_URL` | Postgres; sem ela usa SQLite local |
| `LOJA_NOME`, `LOJA_LOCAL` | identidade exibida no painel |
| `DJANGO_SUPERUSER_USERNAME` / `_PASSWORD` / `_EMAIL` | cria o administrador no deploy (comando `preparar`) |
| `SEED_DEMO=1` | carrega a loja fictícia se o banco estiver vazio |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_ORIGINS` | domínios próprios, separados por vírgula |

---

## Limitações conhecidas

- Receita, custo e lucro do Painel e de Vendas vêm da lista de impostos: só cobrem vendas com nota fiscal.
- O Fechamento Mensal (PDF em imagem) não é lido automaticamente; lance pelo botão **Lançar fechamento** em Financeiro.
- Uma instalação por loja (sem multiempresa).
- A ingestão depende da exportação manual dos relatórios.

---

## Roadmap

- [ ] Ingestão automática (API ou webhook de saída do ERP, ou exportação agendada)
- [ ] Auditoria automática dos dados: margem negativa, custo zerado, placa duplicada
- [ ] Explicação das variações do mês em linguagem natural, com a conta aberta
- [ ] Alertas no WhatsApp dos donos, sob pedido
- [ ] Multiempresa

---

## Autor

Desenvolvido por **Samuel Teixeira** · [LinkedIn](https://linkedin.com/in/samuel-andrei) · [GitHub](https://github.com/Samuel-Drei)
