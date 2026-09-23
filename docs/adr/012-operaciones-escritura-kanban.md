# ADR-012 — Escrita no Kanban e sistema de tarefas

- **Data:** 2026-07-15
- **Estado:** Aceito

- **Decidido na:** sessão 004.

## Contexto

A primeira versão apenas lia dados; a movimentação de cartões não passava
corretamente pelo servidor, impedindo atribuição das ações e consistência
com o banco local. Era necessário centralizar as escritas e implementar tarefas.

## Decisão

### Escritas mediadas pelo servidor

A interface chama apenas rotas próprias. O servidor identifica o autor,
registra a ação, chama o Chatwoot e registra falhas com `chatwoot_call_ok = false`.
A rota original era `PATCH /kanban/board/{conversation_id}/stage`.

### Uma tarefa por conversa no modelo original

Uma nova criação sobrescreve a tarefa existente. Qualquer agente pode criar,
editar ou encerrar tarefas. A sobrescrita usa `action='task_overwritten'`,
com os dados anteriores e a identificação de quem criou a tarefa.

O espelho inicialmente proposto usava `tarea_estado` (List) e
`tarea_vencimiento` (Date). O conteúdo principal fica na tabela `tareas`.
As chaves foram alteradas nas sessões posteriores; o ADR-016 adotou contatos.

### Sincronização

Gravar no banco, enviar ao Chatwoot e marcar `sync_pendiente` se houver falha,
com nova tentativa no agendamento seguinte ou na operação posterior.

### Execução agendada

`POST /kanban/cron/tick`, chamado externamente às 23h30, foi planejado para
promover tarefas a `tarea_hoy`, depois a `tarea_vencida`, e reenviar pendências.
A origem das transições deveria ser registrada como `cron`.

### Painel de agentes

`/kanban/dashboard`, com botão "Voltar ao Kanban", apresenta métricas do
registro de auditoria. Foram planejadas contagens de tarefas criadas,
encerradas e sobrescritas, taxa de encerramento no prazo, tempo médio de
resolução e histórico. Nem todas essas métricas foram implementadas.

## Fundamentação e consequências

O espelho permite consultar informações no Chatwoot mesmo quando o servidor
próprio está indisponível. O banco próprio permite atribuição e consultas
mais ricas. A unicidade evita múltiplas linhas por entidade; operações
concorrentes ainda precisam de tratamento transacional.

O agendamento externo mantém a operação simples e observável. O histórico
deve permitir reconstruir quem moveu cartões e criou, encerrou ou sobrescreveu
tarefas. A auditoria atual identifica divergências entre esse plano e o código.

## Alternativas descartadas

| Alternativa | Motivo |
|-------------|--------|
| APScheduler embutido | Mais complexidade que um agendamento externo |
| Webhooks como sincronização principal | Histórico de duplicação de eventos (#7402) |
| Várias tarefas por conversa | O negócio trabalha com uma missão por contato |
| Tudo em atributos do Chatwoot | Dificulta histórico próprio e métricas complexas |
