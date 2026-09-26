# Sessão 044 — Métricas: valor, conversão e datas reais

Um operador relatou métricas erradas na conta 8 depois de uma importação em massa
seguida de organização do funil. Decisões no
[ADR-047](../adr/047-metricas-valor-e-datas-reais.md).

## Alterações

- `app/metrics/queries.py`: valor da passagem pela etapa; ganho e perda pela
  entrada mais recente; conversão sem etapas de perda, com `loss_rate`.
- `migrations/versions/014_occurred_at.py` e `migrations/occurred_at.sql`:
  `kb_occurred_at()`, gatilhos com data real e `kb_contacts.first_seen_at`.
- `app/routers/workspace.py`: `PATCH /cards/{id}/value`, `occurred_at` no
  movimento e posições de etapa únicas.
- `app/services.py` e `app/recovery.py`: primeiro contato e data do lead na
  importação.
- `app/maintenance.py`: comando de reparo com simulação.
- `app/static/kanban.js` e `app/static/metricas.js`: valor sem reposicionar,
  coluna "Perda" e aviso de dimensão sem configuração.
- `tests/test_metrics_repair.py` e ajuste em `tests/test_metrics.py`.

## Validação

- Ruff, 220 testes Python e testes JavaScript aprovados; migração 014 com
  upgrade e downgrade no banco de teste.
- Chatwoot local: salvar só o valor pela janela do cartão chamou
  `/cards/80/value`, manteve posição e entrada na etapa e registrou
  `valor_atualizado`; Métricas exibiu a coluna "Perda".
- Os números da conta 8 não foram conferidos: a produção não está acessível
  nesta sessão.

## Próximos passos

- Na conta 8: rodar o reparo com `--dry-run`, conferir e aplicar; comparar o
  resumo e o funil com os números esperados do relato.
- Avaliar o avanço automático no primeiro diálogo (`message_created`).

## Segundo diagnóstico (PR de ajustes)

- `app/metrics/queries.py`: parada com mensagem do cliente; equipe pelo
  responsável no fechamento.
- `app/metrics/service.py`, `app/routers/metrics.py`, `app/routers/workspace.py`:
  remoção do bloco `service`, de `GET /reports` e de `app/reporting.py`.
- `app/static/metricas.js`: amostra na taxa de ganho e textos de ajuda.
- Testes: parada com mensagem do cliente, ganho após reatribuição; testes de
  `/reports` removidos com a rota.
- Validação: Ruff, 218 testes Python e JavaScript; Métricas no Chatwoot local
  mostrou "1 de 1 fechamento" e a tabela da equipe.

## Retorno da operação na conta 8

- `--won-at` recusou 23/09 e 25/09 porque os cartões foram movidos em massa depois;
  criado `--fit-moves`.
- Campanha "api.whatsapp.com" em 18 leads: título com cara de link passa a usar o
  texto do anúncio ou "Anúncio {id}", e `--ad-origin` corrige as já gravadas.
- "Sem resposta" como etapa aberta entra na ordem do funil. Recomendação: arquivar
  (a etiqueta cumpre o papel); mover para depois de "Perdido" faria a ida para ela
  contar como avanço.
- Tempo por etapa dos movimentos em massa segue aproximado; `occurred_at` ou o uso
  diário corrigem daqui em diante.
