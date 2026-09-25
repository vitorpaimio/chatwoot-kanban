# ADR-040 — Criação automática de negociações para leads novos

Estado: aceito em 25/09/2026.
Complementa o ADR-022 (sincronização transacional) e o ADR-039.

## Contexto

O mantenedor pediu que um lead novo no Chatwoot virasse negociação no Kanban sem
ação do atendente. A automação nativa do Chatwoot não serve: a ação "Enviar
evento de Webhook" não envia a assinatura que o endpoint do Kanban exige, e não
há ação que preencha o atributo `kanban_etapa`. O Kanban já recebe
`conversation_created` pelo webhook cadastrado na ativação.

## Decisão

Cada funil tem uma configuração de entrada automática, editada por
administradores em "Novo funil" e "Editar funil":

- `kb_funnels.auto_create_stage_id`: etapa de entrada; `NULL` desliga. A chave
  estrangeira garante que a etapa pertence ao funil. A API aceita apenas etapas
  ativas do tipo `open`; sem escolha, usa a primeira etapa aberta (no funil novo,
  "Novo").
- `kb_funnels.auto_create_inboxes`: caixas de entrada aceitas; vazio aceita todas.
  A tela lista as caixas por `GET /kanban/inboxes`, com o token de serviço.

Ao processar uma entrega `conversation_created`, o worker atualiza o contato e,
na mesma transação e com o bloqueio do contato, chama `create_automatic_cards`.
Para cada funil ativo com entrada automática cuja lista de caixas aceita o
`inbox_id` do evento, cria a negociação na etapa escolhida. Só vale para o
primeiro contato: se o contato já teve negociação naquele funil, inclusive
excluída, nada é criado. A criação é registrada como `cartao_criado`, com autor
"Criação automática" e `automatico: true`, e enfileira a projeção para o Chatwoot.

Arquivar a etapa de entrada ou mudar seu tipo para Ganho/Perdido desliga a
entrada automática do funil.

## Consequências

- Reentregas do mesmo evento não duplicam negociações.
- Contatos antigos sem negociação no funil também recebem uma na próxima conversa
  nova, pois o Kanban não distingue esse caso de um lead novo.
- Sem webhook (conta desativada ou entrega perdida) nada é criado; a
  reconciliação não cria negociações.
- O filtro guarda identificadores de caixa; uma caixa removida no Chatwoot apenas
  deixa de receber eventos.

Ver [sessão 041](../sesiones/041-2026-09-25-criacao-automatica.md).
