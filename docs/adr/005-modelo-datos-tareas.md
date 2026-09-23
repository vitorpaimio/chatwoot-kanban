# ADR-005 — Modelo de tarefas: banco próprio e espelho no Chatwoot

- **Data:** 2026-07-09
- **Estado:** Aceito

## Contexto

Uma tarefa precisa de mensagem, criação, vencimento, estado e autoria de
criação e encerramento. Foram comparados dois modelos:

- Todos os campos em atributos personalizados do Chatwoot: `tarea_mensaje`,
  `tarea_vencimiento`, `tarea_creada_en`, `tarea_creador` e `tarea_estado`.
- Conteúdo no banco próprio e apenas o estado espelhado no Chatwoot.

## Decisão original

Escolher o banco próprio como fonte principal e espelhar `tarea_estado`,
do tipo `List`. O servidor já era necessário pelos ADRs 002–004; adicionar
uma tabela teria custo baixo. Cinco atributos aumentariam o acoplamento,
mesmo podendo ser enviados em uma única chamada. O estado atenderia ao
filtro de conversas.

## Regras de negócio originais

- Uma tarefa ativa por conversa; inicialmente, uma nova criação deveria ser
  rejeitada se já houvesse tarefa não encerrada.
- Qualquer agente poderia criar ou encerrar tarefas de qualquer conversa.
- Transições: `null → tarea_activa → tarea_hoy → tarea_vencida`.
  O encerramento manual produz `tarea_cerrada`.
- A passagem para vencida foi planejada para as 23h30, sem gerar nota.

## Notas privadas descartadas

Usar uma nota com prefixo `[TAREA]` acrescentaria uma chamada por operação,
aumentaria a janela de inconsistência e exigiria guardar `message_id`.
O registro próprio do ADR-004 já resolveria o histórico.

## Consistência e recuperação

A gravação local e a atualização externa não são atômicas. O projeto prevê
novas tentativas com espera crescente e marcação `sync_pendiente = true`
para reconciliação quando o envio falhar.

## Evolução

Este ADR registra o modelo inicial. O ADR-012 passou a permitir sobrescrita;
as sessões posteriores adotaram `kanban_view_mensaje` e
`kanban_view_fecha_termino`, e o ADR-016 mudou a associação para contatos.
O esquema original abaixo não deve ser usado como migração atual.

## Exemplos técnicos registrados

```sql
CREATE TABLE tareas (
  id               BIGSERIAL PRIMARY KEY,
  conversation_id  INTEGER NOT NULL UNIQUE,  -- UNIQUE: garante uma tarefa por conversa
  mensaje          TEXT NOT NULL,
  fecha_vencimiento DATE NOT NULL,
  estado           TEXT NOT NULL DEFAULT 'tarea_activa',
  creado_por       INTEGER NOT NULL REFERENCES agentes(id),
  cerrado_por      INTEGER REFERENCES agentes(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  cerrado_en       TIMESTAMPTZ,
  sync_pendiente   BOOLEAN NOT NULL DEFAULT false  -- true se o envio ao Chatwoot falhou
);
```
