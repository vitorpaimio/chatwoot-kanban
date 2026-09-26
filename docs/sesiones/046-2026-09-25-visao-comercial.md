# Sessão 046 — Visão comercial nas métricas

Terceira parte do diagnóstico da conta 8. Decisão no
[ADR-049](../adr/049-visao-comercial-metricas.md).

## Alterações

- `app/metrics/queries.py`: `PROBABILITIES`, `forecast` no resumo,
  `win_probability` no funil, consulta `FLOW` e valores na evolução.
- `app/routers/metrics.py`: `flow` no bloco `funnel`.
- `app/static/metricas.js`: "Previsão de receita", "Passagem entre etapas",
  coluna "Chance de ganho" e "Receita e perdas".
- `tests/test_metrics.py`: previsão, passagem, chance e dinheiro na evolução.

## Validação

- Ruff, 224 testes Python e JavaScript.
- Chatwoot local (página de Métricas): passagem "Novo 2 → Em atendimento 50% →
  Proposta enviada 100% → Ganho 100%", previsão e painel de receita presentes.
- Achado fora do escopo: com a barra lateral do Chatwoot recolhida desde o
  carregamento, o menu Pipeline não é montado; registrado como tarefa separada.
