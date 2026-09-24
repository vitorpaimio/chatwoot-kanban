# ADR-026 — Métricas visuais de funis e contatos

Data: 23/09/2026. Estado: aceito. Complementa ADR-025.

Métricas compartilha o `theme.js` e o CSS base do quadro. Cabeçalho, tipografia,
superfícies, bordas e gráficos usam as variáveis do Chatwoot pai, incluindo o tema
escuro. Cores de etapas continuam sendo dados configuráveis. Textos são inseridos
com `textContent`; não há interpolação de dados em HTML.

O painel apresenta quantidade de cartões, contatos únicos, valor, conversão atual,
distribuição por funil ou etapa, comparação dos funis ativos, evolução diária,
movimentos por agente e trajetória dos contatos. Quantidade, valor e conversão são
retratos da posição atual. O filtro de período se aplica à evolução, agentes e
trajetória; não reconstrói um saldo histórico que não foi registrado.

`GET /kanban/reports` mantém os campos anteriores e acrescenta `evolution`, com
filtros opcionais `funnel_id` e `days` (1 a 365, padrão 30). A interface oferece
7, 30 e 90 dias. A conta é validada pela sessão; funis de outra conta retornam 404.
As agregações ocorrem no PostgreSQL, com dias civis em `America/Sao_Paulo`, e incluem
dias sem atividade. Não há escrita durante a consulta nem alteração de esquema.

Entradas incluem importação e criação de cartões. Movimentos incluem mudanças
efetivas de etapa, inclusive externas e por arquivamento de etapa. Reordenação e
alteração apenas de valor não contam. Contatos movimentados são distintos dentro
do recorte; entradas são por cartão/funil. Conversão continua sendo ganhos divididos
por ganhos mais perdas. Nenhuma duração anterior à importação é inventada.

A trajetória geral mostra os 20 eventos mais recentes. A seleção de contato usa
a rota de histórico existente, paginada, respeitando funil e período. SSE atualiza
o painel e refaz a consulta ao reconectar para recuperar eventos perdidos.

## Correção de concorrência do cache — 23/09/2026

O mutex Python por chave era liberado antes do commit da transação externa.
Outra requisição podia obter o mutex e ficar bloqueada no UPSERT enquanto a
primeira aguardava esse mesmo mutex para outra leitura. A espera circular esgotava
o pool e impedia até o carregamento do quadro.

O cache agora usa pg_try_advisory_xact_lock por conta/chave, sem espera. Quando
outra transação já é responsável pela chave, a requisição consulta o Chatwoot e
retorna o resultado sem disputar a escrita. Mantém TTL de cinco minutos e as
transações/autorização existentes. Pode haver consultas remotas duplicadas em
concorrência; esse custo evita a espera circular e não usa permissões antigas.
Teste de regressão executa duas transações com chaves em ordem oposta.
