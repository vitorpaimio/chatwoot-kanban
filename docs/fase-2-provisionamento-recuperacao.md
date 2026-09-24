# Fase 2 — Provisionamento, autoridade e recuperação

Concluída no escopo do plano 0.2.0 em 23/09/2026. Decisões: ADR-033.

## Critérios e provas

| Critério | Implementação e evidência |
|---|---|
| Catálogo e manifesto por conta | `app/provisioning/attributes.py`, `kb_resources`; criação/reutilização, conflito prévio, IDs substituídos e falha parcial testados |
| Obrigatórios e opcionais | Tipo/modelo e lista validados; obrigatório bloqueia; opcional desliga com diagnóstico; definições alheias preservadas |
| Mapeamentos configuráveis | Administração por sessão humana; triggers de importação, cartões e snapshots; filtros de métricas respeitam chave configurada |
| Separação das operações | Provisionar não importa; habilitação independente; importação tem estado, estimativa, modo, destino e autor próprios |
| Importação retomável | Página persistida, recibo por contato confirmado na mesma transação; repetição recompõe resumo e não duplica cartões |
| Autoridade local e eco | Divergência reenfileira projeção; tarefa e etapa locais permanecem; eco não reenfileira; tarefa sem cartão incluída |
| Webhook perdido | Reconciliação periódica por cursor, independente da entrega; 404 preserva dados e avança o percurso |
| Falhas remotas | Diagnóstico sem segredos; 401/403 e 429 pausam conta sem bloquear outras; Retry-After limitado e retentativa |
| Limites por conta | Lote configurável de 1–100 por fila/ciclo, padrão 10; teste com duas contas e fila maior que o lote |
| Saúde e worker parado | Banco e estado da fila em `/health`; heartbeat expira em 120s; sonda do próprio worker mesmo sem fila |

## Uso

Em **Gerenciar funis → Configuração da conta**, consultar manifesto, diagnósticos,
progresso e limite por lote. Campo opcional vazio desliga a dimensão. Salvar novo
mapeamento agenda provisionamento e reconciliação; cartões são atualizados em lotes,
eventos históricos não são reescritos. **Repetir provisionamento** inventaria também
contas ativadas antes da Fase 2, classificando conservadoramente recursos existentes.

Em **Mais ações → Importar contatos**, conferir estimativa e escolher metadados ou
negociações ausentes no funil/etapa selecionados. Metadados é o padrão. Se houver
importação pendente/falha, a mesma ação oferece retomada. Falhas transitórias também
são retomadas automaticamente pelo worker. Desativar a conta pausa o trabalho sem
apagar os checkpoints.

API administrativa autenticada: `GET/PUT /kanban/provisioning`,
`GET /kanban/provisioning/plan` (somente leitura),
`POST /kanban/provisioning/retry`, `GET /kanban/import/estimate` e
`POST /kanban/import` (`mode`, `funnel_id`, `stage_id` ou `resume: true`).
Nunca enviar o token na URL.

## Validação executada

- Ruff e `git diff --check` aprovados.
- 107 testes Python no PostgreSQL exclusivo `kanban_test`, incluindo concorrência
  real entre importação e requisição aguardando contato; um teste opt-in omitido
  da execução comum e executado separadamente nas duas versões abaixo.
- Quatro testes Node e sintaxe de todos os JS/CJS da interface e navegador.
- Chrome com interface real e API controlada: estimativa, modos, destino,
  mapeamento, manifesto e retomada; regressão de revogação/expiração aprovada.
- Provisionador Python, importador e sincronização contra controllers Rails reais
  CE **4.16.2 e 4.18.0**: conta vazia, seis atributos e webhook, repetição sem
  duplicação, recibos, importação de metadados sem cartões, divergência corrigida
  e atributo alheio preservado. Fixtures remotas revertidas no fim, credencial
  em memória. Ponte em `tests/contracts/phase2_bridge.rb`; teste
  `tests/test_phase2_real.py`.
- Ambiente local: migrações 009–011 aplicadas preservando contagens de contatos,
  negociações e tarefas; API/worker reiniciados; `/health` e `/health/worker` 200,
  fila sem pendências/atrasos e sonda própria do worker aprovada.
- Navegação na sessão real do Chatwoot local: quadro, configuração e repetição do
  provisionamento; manifesto mostrou recursos criados e preexistentes, estado pronto.
  Estimativa real de oito contatos exibida com metadados como modo padrão;
  nenhuma nova importação iniciada nessa conferência.

O teste Rails usa Integration::Session em Rails test, autenticando os controllers
reais. Não simula respostas remotas; também não certifica rede/proxy, Sidekiq ou
Swarm. Os testes de falhas 401/403/429/404 e transporte usam respostas controladas.
A navegação local não substitui a certificação completa de navegador nas duas
versões, prevista no gate final. Carga e instalador permanecem nas Fases 3 e 4.

## Reprodução das provas Rails

Usar checkouts oficiais com gems/schema já preparados como na Fase 0. Definir
`PHASE2_CHATWOOT_DIR` para o checkout, `PHASE2_CHATWOOT_DATABASE` para o banco
exclusivo correspondente e executar:

```sh
.venv/bin/pytest -q tests/test_phase2_real.py
```

A ponte recusa bancos diferentes de `kanban_phase0_cw4162_test` e
`kanban_phase0_cw4180_test`, exige Rails test e Community Edition. O Kanban usa
`TEST_DATABASE_URL` com sufixo `_test` (padrão: `kanban_test`). Não executar as duas
versões simultaneamente usando o mesmo banco de testes do Kanban.
