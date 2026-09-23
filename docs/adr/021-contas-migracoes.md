# ADR-021 — Contas isoladas e migrações explícitas

Estado: aceito em 23/09/2026.

Alembic cria tabelas `kb_*` sem alterar tabelas legadas. Todo recurso e consulta usa
`account_id`; referências compostas impedem cartões vinculados a etapas de outra conta.
Agentes são identificados pela conta e pelo ID de usuário no Chatwoot.
Há um cartão por contato/funil e uma tarefa ativa por contato/conta, com índice parcial.

Migração legada exige conta, backup, validação de identidades e contatos. A cópia
transacional é rastreada por origem/ID; ambiguidade causa interrupção. O esquema
antigo permanece disponível. Downgrade destrutivo automático não é oferecido.
