# ADR-050 — Transferência de negociações entre funis

Estado: aceito em 28/09/2026.
Complementa o ADR-047 e o ADR-049.

## Contexto

O cartão só mudava de etapa dentro do próprio funil. Contas com mais de um funil
(follow-up, pós-venda, SDR para closer) não tinham como levar a negociação adiante
sem recriá-la à mão, um contato por vez, pelo atributo Funil / Etapa. Trocar o
`funnel_id` do cartão não serve: as métricas filtram por `c.funnel_id` e o
`kb_visible_history` só mostra o histórico quando o funil do registro é o do
cartão. O histórico sairia do funil de origem e ficaria invisível para agentes.

## Decisão

- Transferir **cria um cartão novo** no funil de destino, com `origin_card_id`
  apontando para a origem. Conversa vinculada, fixação da conversa e valor (opcional)
  vêm da origem; origem, campanha e temperatura continuam vindo do contato.
- Quem transfere escolhe o que acontece com a origem:
  - `keep`: fica na etapa; o quadro mostra o selo de transferida.
  - `stage`: vai para uma etapa do próprio funil, com a validação de perda.
  - `close`: grava `transferred_at`, sai do quadro e deixa de ser aberta nas
    métricas sem virar ganho nem perda (evento e tipo `transferred`).
- A duplicidade é barrada pela origem, não pelo contato: uma origem não pode ter
  dois destinos abertos no mesmo funil. O ADR-031 mantém várias negociações do
  mesmo contato no mesmo funil.
- `POST /kanban/cards/{id}/transfer` transfere um cartão com trava de versão.
  `POST /kanban/stages/{id}/transfer` transfere em lote uma etapa, com filtro
  opcional de dias sem atividade (maior entre a entrada na etapa e a última
  atividade do contato), até 200 cartões por chamada, cada um num savepoint.
  A interface repete a chamada até não restar cartão elegível.
- Os dois funis são travados em ordem de id e cada contato com `lock_contact`.
  O histórico ganha `cartao_transferido` nos dois funis, e `last_card_id` passa a
  ser o destino, para o atributo do Chatwoot mostrar a nova etapa.
- Cartões encerrados por transferência ficam fora do quadro, do atributo,
  da movimentação pelo contato e do arquivamento de etapa, mas continuam em
  `kb_visible_cards` para histórico, métricas e autorização.

Rotas pré-configuradas por funil, transferência pelo atributo Funil / Etapa com
vínculo e regras automáticas (tempo sem resposta do cliente) ficam para depois;
todas devem reutilizar `transfer_card`.

## Consequências

- As views de cartões foram recriadas para expor as colunas novas.
- O downgrade da migração 016 é bloqueado quando já existe transferência.
- Desfazer uma transferência ainda exige excluir o destino e mover a origem à mão.
