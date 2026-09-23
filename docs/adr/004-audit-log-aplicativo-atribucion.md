# ADR-004 — Registro de auditoria próprio para atribuir ações

- **Data:** 2026-07-09
- **Estado:** Aceito

## Contexto

Todas as chamadas usam o token do usuário de serviço (ADR-002). Assim, o
Chatwoot não identifica o agente humano responsável. Na análise original,
os registros nativos de auditoria não atendiam à atribuição das ações
realizadas pela integração via API.

O negócio precisava identificar quem criou e quem encerrou cada tarefa,
inclusive para métricas por agente, como `COUNT(*) GROUP BY cerrado_por`.

## Decisão

Manter `task_audit_log` no banco próprio como fonte de atribuição. O fluxo
planejado registra a ação recebida da sessão autenticada antes da chamada
ao Chatwoot, preservando também as tentativas malsucedidas.

## Fluxo planejado

1. Receber a requisição de uma sessão autenticada pelo Cloudflare Access.
2. Obter a identidade verificada e associá-la à tabela `agentes`.
3. Registrar autor, ação, estado anterior, novo estado e origem.
4. Chamar o Chatwoot com o token do usuário de serviço.
5. Registrar o resultado, inclusive `chatwoot_call_ok = false` em falhas.

## Decisões do esquema

- `actor_name` guarda o nome no momento da ação, preservando a leitura mesmo
  se o cadastro do agente deixar de existir.
- `source = 'cron'` distingue ações agendadas das ações humanas.
- `chatwoot_call_ok` permite identificar divergências do espelho no Chatwoot.
- `previous_state` e `new_state` usam JSONB para acomodar a evolução dos dados.

## Consequências

O histórico das últimas cem tarefas e as métricas podem ser consultados
sem interpretar notas ou consultar a API externa. O registro foi concebido
para receber novas linhas, sem modificar eventos anteriores.

A descrição acima é arquitetural: a auditoria atual deve verificar a ordem
real de gravação, a autenticação do autor e a durabilidade da sincronização.

## Exemplos técnicos registrados

```sql
CREATE TABLE task_audit_log (
  id               BIGSERIAL PRIMARY KEY,
  conversation_id  INTEGER NOT NULL,
  contact_id       INTEGER,
  actor_agent_id   INTEGER NOT NULL,
  actor_name       TEXT NOT NULL,          -- registro do nome independente da existência futura do agente
  action           TEXT NOT NULL,          -- 'create' | 'reassign' | 'close' | 'auto_expire' | 'edit_message'
  previous_state   JSONB,
  new_state        JSONB,
  source           TEXT NOT NULL DEFAULT 'manual',  -- 'manual' | 'cron'
  chatwoot_call_ok BOOLEAN,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_conversation ON task_audit_log (conversation_id);
CREATE INDEX idx_audit_actor        ON task_audit_log (actor_agent_id);
```
