# Sessão 007 — Datas, estados dinâmicos, cartões e atualização periódica

- **Data:** 2026-07-17
- **Natureza:** registro histórico, revisado em português do Brasil.

## Contexto

Foram relatadas datas exibidas um dia antes, perda da indicação de tarefa
ao mover cartões, estados desatualizados, título redundante do painel e
ausência de atualização entre agentes.

## Alterações

1. O envio do vencimento mudou de `T04:00:00.000Z` para `T23:59:59.999Z`
   no roteador, no agendamento e nos exemplos dos testes.
2. `computeTaskEstado()` passou a calcular o estado na interface pela data,
   com estados de ativa, vencimento hoje, vencida e encerrada. A proposta
   incluía ocultar tarefas encerradas após 24 horas.
3. `createCard()` passou a guardar `dataset.task`; a movimentação passou a
   restaurar esses dados para preservar a indicação da tarefa.
4. A consulta passou a incluir encerradas nas últimas 24 horas com
   `OR t.cerrado_en >= now() - interval '24 hours'`.
5. O título redundante do painel foi removido e seu teste ajustado.
6. A atualização automática a cada 30 segundos passou a chamar o quadro,
   pausando com modal aberto e retomando ao fechá-lo.

## Arquivos

Alterados `app/routers/kanban.py`, `app/database.py`, os dois modelos HTML,
os dados simulados e os testes do Kanban.

## Validação registrada

Ruff, verificação de formatação e 29 testes passaram na sessão original.
A validação seguinte deveria conferir datas no Chile e avaliar o custo da
atualização completa em comparação com uma atualização diferencial.

## Nota da revisão em português

A correção histórica do horário enviado não resolvia o uso de `new Date`
com datas sem horário na interface. Essa diferença de dia foi reproduzida
no fuso brasileiro na auditoria de 2026-09-23 e corrigida separadamente.
