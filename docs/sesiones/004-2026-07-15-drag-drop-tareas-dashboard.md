# Sessão 004 — Movimentação de cartões, tarefas e painel

- **Data:** 2026-07-15
- **Natureza:** registro histórico, revisado em português do Brasil.

## Contexto

O quadro mostrava conversas, mas a movimentação não passava corretamente
pelo servidor. A atualização visual podia apagar o cartão e deixá-lo vazio
sem recuperação em caso de erro. As tarefas do ADR-005 ainda não tinham interface.

## Alterações

### Movimentação

Criada `PATCH /kanban/board/{conversation_id}/stage`, com validação da etapa,
registro `stage_change` e escrita no Chatwoot. A interface passou a mover o
cartão apenas após o sucesso e exibir aviso quando houvesse falha.

### Tarefas

| Rota | Finalidade |
|------|------------|
| `POST /kanban/tasks` | Criar ou sobrescrever tarefa |
| `PATCH /kanban/tasks/{id}` | Editar mensagem e vencimento |
| `PATCH /kanban/tasks/{id}/close` | Encerrar |
| `GET /kanban/tasks` | Consultar tarefa da conversa |

Uma conversa mantinha uma tarefa; nova criação sobrescrevia a anterior.
`task_overwritten` guardava o estado anterior e o criador. O banco próprio
era a referência e `tarea_estado` e `tarea_vencimiento` formavam o espelho
inicial no Chatwoot.

O quadro passou a incluir `task` com `id`, `estado`, `mensaje`,
`fecha_vencimiento` e `creado_por`. Os indicadores usavam azul para ativa,
âmbar para vencimento no dia e vermelho para vencida.

### Agendamento e painel

`POST /kanban/cron/tick` foi planejado para as 23h30, com transições para
`tarea_hoy` e `tarea_vencida`, reenvio de pendências e auditoria `source='cron'`.

O painel `/kanban/dashboard` passou a apresentar tarefas criadas,
encerradas e sobrescritas, agentes com atividade e histórico recente.
As consultas usam `/kanban/stats` e `/kanban/stats/history` (50 eventos).

### Banco e arquivos

`database.py` recebeu funções para agentes, auditoria, criação, edição,
encerramento, consultas, agendamento e estatísticas. Foram alterados o
roteador Kanban, seu HTML e os testes; foram criados `dashboard.html` e
ADR-012. O índice da documentação foi atualizado.

## Validação registrada

29 testes passaram: os 17 anteriores e 12 novos para movimentação, tarefa,
estatísticas, agendamento e painel. O ADR-005 ainda mantinha o esquema
original com unicidade por conversa.

## Próximos passos registrados

Configurar o agendamento no NAS, integrar Cloudflare Access para atribuição
real e avaliar criação de tarefas diretamente pelos cartões.
