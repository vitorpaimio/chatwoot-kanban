# ADR-049 — Visão comercial nas métricas

Estado: aceito em 25/09/2026.
Complementa o ADR-046 e o ADR-047.

## Contexto

O diagnóstico da conta 8 apontou que Métricas respondia sobretudo "quantos cartões
estão onde". Faltavam o funil de passagem, a previsão de receita e o dinheiro no
tempo. Os relatórios de atendimento continuam no Chatwoot.

## Decisão

- **Passagem entre etapas** (`flow` no bloco `funnel`): dos leads criados no
  período, quantos chegaram a cada etapa aberta ou além e ao ganho, pela ordem
  `(position, id)`. Etapas de perda não contam como avanço. A tela mostra a
  porcentagem sobre a etapa anterior e pede um funil quando o recorte mistura
  vários.
- **Chance de ganho por etapa** (`win_probability`): das negociações que passaram
  pela etapa e já fecharam até o fim do período, quantas foram ganhas.
- **Previsão de receita** (`forecast` no resumo): soma do valor das negociações
  abertas no fim do período vezes a chance da etapa em que estão. Sem histórico
  de fechamento, a chance é zero.
- **Receita e perdas** na evolução: `revenue`, `losses` e `lost_value` por dia; a
  tela agrupa por mês quando o período passa de 62 dias.

Coortes por semana, conversão por tempo de primeira resposta, distribuição do
ticket, meta mensal e custo por lead ficam para depois.

## Consequências

- A chance histórica é instável com poucos fechamentos; a ajuda do indicador diz
  isso e a taxa de ganho já mostra a amostra.
- A previsão depende de valores preenchidos nas negociações abertas.
