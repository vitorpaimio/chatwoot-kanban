# ADR-018 — Demonstração com API simulada do Chatwoot

- **Data:** 2026-08-30
- **Estado:** Aceito

- **Autor(es):** opencode, com assistência.

## Contexto

A interface incorporada ao Chatwoot depende da API externa e de PostgreSQL.
Uma demonstração não deveria exigir uma instância real, contatos e token.

## Decisão registrada

Criar ferramentas locais de demonstração em `demo/`, sem modificar a
aplicação, apontando `CHATWOOT_BASE_URL` para uma API simulada:

- `demo/mock_chatwoot.py`: servidor FastAPI com definições de atributos,
  filtro e leitura/atualização de contatos; dados mantidos em memória.
- `demo/seed_db.py`: população idempotente de agentes e auditoria no banco.
- `docker-compose.demo.yml`: PostgreSQL, API simulada na porta 8095,
  serviço de população do banco e aplicação na porta 8000.
- `demo/screenshot.py`: capturas com Playwright em `docs/demo/`.

As datas dos exemplos são relativas ao dia atual para mostrar tarefas
futuras, do dia e vencidas. Os avatares são gerados localmente.

## Distribuição

`demo/` e `docker-compose.demo.yml` foram incluídos no `.gitignore` como
ferramentas locais. Apenas as capturas eram versionadas. Portanto, a cópia
publicada não contém as ferramentas necessárias para reproduzir aquela
demonstração completa.

## Consequências

O ambiente local original exercitava FastAPI, asyncpg e PostgreSQL sem
credenciais reais. Reiniciar o servidor simulado perdia alterações em
memória. A demonstração tinha 28 contatos, não cobria paginação extensa
nem eventos `contact_updated` e `conversation_updated`.

Mudanças nas chaves dos atributos exigem atualizar os dados simulados.
A alegação de execução sem internet pressupõe imagens e dependências já
presentes no ambiente.

## Alternativas descartadas

Um modo de demonstração dentro da aplicação alteraria cliente, banco e rotas.
SQLite exigiria adaptar recursos PostgreSQL como JSONB e índices parciais.
Uma instância real do Chatwoot exigiria mais recursos, configuração e migrações.
