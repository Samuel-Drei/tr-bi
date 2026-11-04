# Painel TR Motors (MVP)

Painel gerencial da TR Motors, alimentado pelos relatórios exportados do Revenda Mais.

## Rodar
    pip install -r requirements-import.txt
    python manage.py migrate
    python manage.py importar "C:\caminho\da\pasta\com\relatorios"
    python manage.py runserver        # http://localhost:8000

`importar` reconhece o tipo de cada arquivo pelo nome, ignora arquivos já importados (hash)
e regrava só o período/foto do relatório, então pode ser repetido sem duplicar.

## Relatórios aceitos
- histórico de estoque.XLS · exportação de clientes.xlsx
- Lista de Impostos Veículos Vendidos.XLS · Lista Gerencial de Estoque com Margem.XLS
- Vendas Mensais por Vendedor.PDF · Relatório Canal de Venda.PDF

## Limitações conhecidas do MVP
- Receita, custo e lucro vêm da lista de impostos: só cobre vendas com nota fiscal.
- O Fechamento Mensal (PDF em imagem) ainda não é lido; o modelo `Fechamento` existe para lançar à mão.
- Sem login: não publicar na internet antes de adicionar autenticação (há dados de clientes).
- Só a página "Painel" está ativa; os demais itens do menu são marcadores.
