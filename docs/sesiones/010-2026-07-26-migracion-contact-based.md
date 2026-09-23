# Sessão 010 — Migração de conversas para contatos

- **Data:** 2026-07-26
- **Natureza:** registro histórico, revisado em português do Brasil.

## Contexto

Pessoas com várias conversas apareciam repetidamente e tinham tarefas
fragmentadas. A integração foi migrada para atributos de contato, conforme
ADR-016, mantendo um cartão por pessoa.

## Verificações históricas da API

| Operação | Resultado relatado |
|----------|--------------------|
| Consultar definições | Sete atributos: três de conversa e quatro de contato |
| `POST /contacts/filter` | Paginação e dados diretos de nome e imagem |
| `PATCH /contacts/{id}` | Combinação de atributos personalizados |
| `POST /contacts/{id}/custom_attributes` | 404; rota inexistente |
| `GET /contacts/{id}/conversations` | Conversas do contato |

Os atributos de contato 6, 7 e 9 já existiam, vazios; os de conversa 1, 4 e 5
continuavam ativos. A amostra tinha cerca de 323 conversas em seis etapas,
representando 187 contatos.

## Alterações

O cliente ganhou `filter_contacts`, `get_contact`, `get_contact_conversations`,
`update_contact_custom_attributes` e `safe_update_contact_custom_attributes`.

O banco ganhou `contact_id`, unicidade parcial por contato e
`conversation_id` opcional. `_migrate_schema()` foi introduzida na
inicialização; auditoria, tarefas, consultas e sincronização passaram a usar
contatos. `get_tasks_for_contacts()` substituiu a consulta por conversas.

O roteador passou a usar `_normalize_contact`, `filter_contacts` e
`/board/{contact_id}/stage`. O corpo de criação passou a exigir `contact_id`;
a resposta do quadro passou a usar `contacts`. A definição de atributo de
contato ganhou prioridade sobre a de conversa.

Foram adicionados `/webhooks/contact-updated` e
`/api/contacts/{contact_id}/custom-attributes`. O evento de conversa foi
mantido por compatibilidade, sem sincronização de tarefas.

A interface passou a usar `data-contact-id`, `last_activity_at`, nome e
imagem diretamente do contato. `last_message` foi removido. O link previsto
na sessão era `/contacts/{id}/conversations`.

## Ferramentas de migração registradas

A sessão relatou `app/routers/migrate.py`, incluído em `main.py`, com:

- `POST /migrate/contact-attributes`.
- `POST /migrate/db-tasks-only`.
- `GET /migrate/status`.

Essas ferramentas **não estão presentes nesta cópia**. O registro histórico
não deve ser usado como instrução executável sem recuperar e revisar o código.

## Testes e decisões

Os dados simulados e testes foram migrados para contatos, incluindo eventos
novos e antigos. A sessão registrou 31 testes aprovados. As chaves dos
atributos foram reutilizadas em outro modelo; os dois conjuntos coexistiram
durante a migração, e `conversation_id` permaneceu informativo.

## Próximos passos registrados

Implantar em homologação, migrar atributos e tarefas, consultar o estado,
validar cartões e operações e então promover para produção. Somente após
validação, remover os atributos antigos de conversa.
