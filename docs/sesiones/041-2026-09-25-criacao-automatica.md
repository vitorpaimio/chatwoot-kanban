# Sessão 041 — Criação automática de negociações

O mantenedor pediu que um lead novo no Chatwoot criasse a negociação sozinho,
com a etapa escolhida na configuração do funil, apenas no primeiro contato e com
filtro por caixa de entrada. Decisão registrada no
[ADR-040](../adr/040-criacao-automatica-negociacoes.md).

## Alterações

- `migrations/versions/013_auto_create.py`: `auto_create_stage_id` e
  `auto_create_inboxes` em `kb_funnels`.
- `app/services.py`: `create_automatic_cards` e o autor "Criação automática".
- `app/worker.py`: entregas `conversation_created` criam as negociações.
- `app/routers/workspace.py`: configuração em `POST/PUT /funnels`,
  `GET /inboxes` e desligamento ao arquivar ou encerrar a etapa de entrada.
- `app/static/kanban.js` e `kanban.css`: bloco "Entrada automática" na janela do
  funil e resumo em "Gerenciar funil".
- `tests/test_auto_create.py`: etapa padrão, primeira conversa, reentrega,
  negociação existente ou excluída, filtro de caixa, outros eventos e etapa
  inválida ou arquivada.

## Validação

- Ruff e 207 testes Python aprovados no banco exclusivo (dois opt-in omitidos);
  testes JavaScript aprovados.
- Chatwoot local, conta 1: com a entrada automática ligada no funil principal
  para a caixa 1, um contato e uma conversa criados pela API geraram a negociação
  na etapa "Novo", com autor "Criação automática", e o atributo `kanban_etapa`
  voltou ao Chatwoot como `Funil principal / Novo`. Uma segunda conversa do mesmo
  contato não criou outra negociação. A configuração foi desligada ao final.

## Próximos passos

- Validar a janela do funil logado no Chatwoot local e em homologação.
