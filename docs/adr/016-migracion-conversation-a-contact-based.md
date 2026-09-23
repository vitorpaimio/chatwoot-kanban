# ADR-016 — Migração de conversas para contatos

- **Data:** 2026-07-26
- **Estado:** Aceito

- **Autor(es):** sessão 010.
- **Substitui:** ADR-006 no modelo de dados do Kanban.

## Contexto

Os atributos `pipeline_01_etapas`, `kanban_view_mensaje` e
`kanban_view_fecha_termino` pertenciam às conversas. Pessoas com várias
conversas por WhatsApp, Instagram ou e-mail apareciam repetidamente.
Isso fragmentava tarefas e dificultava identificar a etapa real do contato.
Na análise, contatos como os de IDs 215 e 207 apareciam três vezes.

## Decisão

Usar `contact_attribute` e representar um contato por cartão, independentemente
da quantidade de conversas.

| Componente | Antes | Depois |
|------------|-------|--------|
| Modelo dos atributos | `conversation_attribute` | `contact_attribute` |
| Cartão | Conversa | Contato |
| Identificador | `conversation_id` | `contact_id` |
| Filtro | `/conversations/filter` | `/contacts/filter` |
| Escrita | `POST /conversations/{id}/custom_attributes` | `PATCH /contacts/{id}` |
| Unicidade de `tareas` | `conversation_id` | `contact_id` |
| Evento principal | `conversation_updated` | `contact_updated` |
| Link previsto na migração | `/conversations/{id}` | `/contacts/{id}/conversations` |

## Transição registrada

Os atributos antigos (IDs 1, 4 e 5) coexistiram temporariamente com os novos
(IDs 6, 7 e 9). A migração prevista em `POST /migrate/contact-attributes`
agrupava conversas por contato, escolhia a mais recente por `updated_at`,
copiava os atributos ao contato e associava as tarefas locais a `contact_id`.

No banco, `conversation_id` passou a aceitar nulo e permaneceu informativo.
Um índice parcial passou a garantir unicidade de `contact_id` não nulo.

## Consequências

- Um cartão por contato e tarefas associadas à pessoa.
- Na amostra histórica, 187 contatos substituíram 323 conversas.
- Perda da granularidade por conversa e de `last_message` diretamente no cartão.
- Necessidade de migrar dados; falhas parciais podem deixar contatos sem atributos.

## Alternativas descartadas

Manter conversas não resolveria duplicações. Um modelo híbrido com a última
conversa aumentaria a complexidade e as fontes de dados. Criar novas chaves
não era necessário, pois o mesmo nome podia existir em modelos distintos.

## Nota da auditoria de 2026-09-23

As rotas `/migrate/*` e `app/routers/migrate.py` descritas no histórico não
estão presentes nesta cópia. A migração automática atual adiciona colunas
e índices, mas não reconstrói a associação dos dados antigos.

## Exemplos técnicos registrados

```sql
-- Antes
CREATE TABLE tareas (
  conversation_id INTEGER NOT NULL UNIQUE,
  ...
);

-- Depois
CREATE TABLE tareas (
  contact_id      INTEGER,
  conversation_id INTEGER,  -- aceita nulo; informativo
  ...
);
CREATE UNIQUE INDEX idx_tareas_contact_id
  ON tareas (contact_id) WHERE contact_id IS NOT NULL;
```
