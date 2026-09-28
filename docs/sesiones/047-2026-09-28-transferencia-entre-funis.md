# Sessão 047 — Transferência entre funis

Pedido da conta 8: levar negociações paradas do funil principal para o funil de
follow-up. A solução vale para qualquer conta com mais de um funil. Decisão no
[ADR-050](../adr/050-transferencia-entre-funis.md).

## Alterações

- `migrations/transfer.sql` e `016_transfer.py`: `origin_card_id`,
  `transferred_at`, evento `transferred`, gatilhos de métricas e views de cartões.
- `app/routers/workspace.py`: `transfer_plan`, `transfer_card` e as rotas de
  transferência individual e por etapa; bloqueio de mover a origem encerrada.
- `app/board.py`: vínculos de origem e destino; origem encerrada fora do quadro.
- `app/services.py`, `app/routers/pages.py`: atributo e tarefas ignoram a origem
  encerrada.
- `app/static/kanban.js` e `kanban.css`: ação "Transferir para outro funil",
  transferência em lote pelo cabeçalho da coluna, selo e linhas de vínculo.
- `tests/test_transfer.py`: modos, métricas, validações, lote e histórico visível
  para agente.

## Validação

- Ruff, testes Python e JavaScript.
- Migração 016 aplicada, revertida e reaplicada no banco de testes.
- Chatwoot local: transferência de um cartão mantendo a origem (selo e linha
  "Transferida para"), lote da etapa Novo encerrando a origem, e atributo
  Funil / Etapa sincronizado com o destino nos dois contatos.

## Próximos passos

- Rotas pré-configuradas por funil e transferência pelo atributo com vínculo.
- Registrar a direção da última mensagem (`message_created`) para filtrar
  "aguardando o cliente" e automatizar o follow-up.
- Desfazer transferência.
