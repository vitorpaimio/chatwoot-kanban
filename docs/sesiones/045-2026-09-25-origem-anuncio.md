# Sessão 045 — Origem pelo anúncio

Segundo diagnóstico da conta 8: a maior parte dos leads veio de anúncio de
Click-to-WhatsApp, com a origem já gravada no Chatwoot. Decisão no
[ADR-048](../adr/048-origem-por-anuncio.md).

## Alterações

- `migrations/versions/015_ad_origin.py` e `migrations/ad_origin.sql`: colunas de
  anúncio no contato e gatilhos de dimensões com o anúncio como alternativa.
- `app/services.py`: `ad_referral`, `first_ad` e `apply_ad_origin`.
- `app/worker.py`: anúncio lido em `conversation_created`, antes da entrada
  automática.
- `app/routers/metrics.py`: origem e campanha configuradas quando há anúncio.
- `app/maintenance.py`: `--ad-origin`.
- `tests/test_ad_origin.py`.

## Validação

- Ruff, 222 testes Python e JavaScript; migração 015 com upgrade e downgrade.
- Chatwoot local: uma mensagem de teste marcada com `referral` de anúncio foi
  encontrada pela API real (`?after=0`) na simulação de `--ad-origin`, sem gravar;
  a marcação foi removida depois.

## Próximos passos

- Na conta 8: `--ad-origin` em simulação e depois aplicado.
- Visão comercial: funil decrescente, previsão ponderada e receita por mês.
