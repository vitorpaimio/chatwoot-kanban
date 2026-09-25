# ADR-039 — Funil / Etapa como lista editável no Chatwoot

Estado: aceito em 25/09/2026.
Altera a autoridade da etapa definida no ADR-033; mantém o ADR-022.

## Contexto

O atributo de contato `kanban_etapa` era texto e apenas espelhava o quadro.
O mantenedor pediu que "Funil / Etapa" fosse uma lista no Chatwoot e que alterar
a opção no contato movesse o contato no Kanban.

## Decisão

`kanban_etapa` passa a ser do tipo lista. Cada opção tem o formato
`Funil / Etapa` e corresponde a uma etapa ativa de um funil ativo, na ordem do
quadro (funil principal primeiro). O catálogo cria a lista com as etapas padrão;
o worker compara, a cada ciclo, as opções registradas em `kb_resources` com os
funis e etapas locais e envia `PATCH /custom_attribute_definitions/:id` somente
quando há diferença. Definições antigas do tipo texto são aceitas pelo plano de
provisionamento e convertidas nessa mesma sincronização, sem alterar os valores
já gravados nos contatos. O instalador faz a mesma conversão e aceita a lista ao
remover um atributo que criou como texto. Falha ao atualizar as opções gera apenas
aviso e não bloqueia eventos, importação ou projeções.

Somente eventos de webhook aplicam a etapa escolhida no Chatwoot. O processamento
relê o contato e, dentro da transação com bloqueio do contato:

- ignora o valor se houver projeção local ainda não sincronizada (o quadro vence);
- ignora o valor igual à última projeção enviada pelo Kanban (eco);
- ignora valor vazio, desconhecido ou ambíguo, registrando `espelho_divergente`
  como antes, e a reconciliação restaura o espelho;
- move a negociação do contato naquele funil (a última usada, senão a mais recente),
  ou cria uma negociação quando o contato não tem nenhuma ativa no funil.

A mudança é registrada no histórico como `cartao_movido` ou `cartao_criado`, com
autor "Chatwoot", e reenfileira a projeção. Etapas de perda exigem motivo; pela
lista, o motivo gravado é `Outro: etapa alterada no atributo do contato`.
Importação e reconciliação continuam sem autoridade remota: não recriam
negociações a partir de espelhos antigos.

## Consequências

- Renomear funil ou etapa troca o texto da opção; contatos com o valor antigo
  recebem o novo valor pela projeção já enfileirada nessas alterações.
- Nomes que geram o mesmo rótulo (por exemplo, com ` / ` no nome) tornam a opção
  ambígua e ela não move o contato.
- Webhook perdido não aplica a escolha; a reconciliação volta o atributo ao quadro.

Ver [sessão 040](../sesiones/040-2026-09-25-etapa-lista-editavel.md).
