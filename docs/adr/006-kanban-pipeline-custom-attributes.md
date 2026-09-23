# ADR-006 — Kanban sobre atributos personalizados de conversas

- **Data:** 2026-07-09
- **Estado:** Substituído pelo ADR-016

- **Substituído por:** ADR-016, em 2026-07-26.

## Contexto

A proposta inicial era agrupar conversas por etapa de um funil e mover os
cartões por arrastar e soltar. A análise não identificou essa visualização
nativamente no Chatwoot.

## Decisão original

Usar atributos `List` das conversas: `pipeline` para escolher o funil e
`pipeline_stage` para a etapa. Consultar `/conversations/filter` com os
filtros de funil, etapa e, opcionalmente, `tarea_estado` na mesma requisição.

## Operações

| Operação | Rota ou evento |
|----------|----------------|
| Definições de atributos | `GET /api/v1/accounts/{id}/custom_attribute_definitions` |
| Filtrar conversas | `POST /api/v1/accounts/{id}/conversations/filter` |
| Mover cartão | `POST /api/v1/accounts/{id}/conversations/{id}/custom_attributes` |
| Sincronizar agentes | Webhook `conversation_updated` |

As definições seriam armazenadas em cache, confirmando chaves e valores.

## Limitações identificadas na análise original

1. Duplicação de webhooks (issue #7402): prever idempotência por
   `conversation.id + updated_at`.
2. Variação no formato dos eventos (issue #13993): validar campos opcionais
   defensivamente com Pydantic.
3. Paginação convencional: volumes altos poderiam exigir cache ou
   carregamento gradual das colunas.
4. Listas sem valores condicionados por outro atributo: manter a relação
   entre funil e etapas na configuração da própria aplicação.

## Consequências

A interação de arrastar e soltar pertence à interface; a escrita passa pelo
servidor e pela API do Chatwoot. O Chatwoot é a referência para a etapa do
contato; o banco próprio não mantém uma cópia persistida dessa etapa.
A visualização das tarefas seria um filtro do mesmo quadro, não outro Kanban.
