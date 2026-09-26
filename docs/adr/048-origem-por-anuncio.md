# ADR-048 — Origem e campanha pelo anúncio de Click-to-WhatsApp

Estado: aceito em 25/09/2026.
Complementa o ADR-033 (catálogo de atributos) e o ADR-047.

## Contexto

Na conta 8, 126 de 269 leads chegaram por anúncio de Click-to-WhatsApp, mas as
métricas de origem e campanha mostravam "não configurado". O Chatwoot grava o
anúncio na primeira mensagem recebida, em `content_attributes.referral`
(`source_type=ad`, `source_id`, `headline`, `ctwa_clid`). O Kanban não lia
mensagens.

## Decisão

- `kb_contacts` ganha `ad_source`, `ad_campaign`, `ad_id`, `ad_click_id` e
  `ad_seen_at` (migração 015).
- Ao processar `conversation_created`, o worker lê as primeiras mensagens da
  conversa (`GET /conversations/{id}/messages?after=0`, até 100 em ordem de envio)
  e grava o primeiro anúncio das mensagens recebidas. Vale o primeiro contato: um
  contato que já tem origem de anúncio não é sobrescrito. A leitura acontece antes
  da entrada automática, para o evento de criação da negociação já levar a origem.
- Origem = "Anúncio (Click-to-WhatsApp)"; campanha = título do anúncio, ou
  "Anúncio {id}" sem título. O atributo mapeado nas Configurações tem prioridade;
  o anúncio só preenche quando ele está vazio. Os gatilhos de dimensões levam os
  valores às negociações do contato.
- As métricas consideram origem e campanha configuradas quando há contato com
  anúncio, mesmo sem mapeamento.
- `python -m app.maintenance --ad-origin` percorre os contatos sem anúncio,
  lendo a conversa mais antiga primeiro, e registra `origem_anuncio`.
- Não foi adotada a assinatura de `message_created`: uma chamada por conversa nova
  basta para a origem, sem multiplicar os webhooks.

## Consequências

- Uma chamada a mais ao Chatwoot por conversa nova, em qualquer canal.
- Anúncios que não sejam de Click-to-WhatsApp (sem `referral`) continuam como
  "Não informada", salvo atributo mapeado.
- Custo por lead e ROI dependem de informar o gasto por anúncio; fica para depois.
