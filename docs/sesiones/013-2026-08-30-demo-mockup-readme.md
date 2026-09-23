# Sessão 013 — Demonstração e capturas para o README

- **Data:** 2026-08-30
- **Natureza:** registro histórico, revisado em português do Brasil.

## Objetivo e resultado histórico

Mostrar quadro e painel com dados simulados, sem instância real do Chatwoot.
A sessão registrou demonstração em execução, capturas verificadas e README
atualizado.

## Ferramentas locais registradas

`demo/mock_chatwoot.py` implementava definições de atributos, filtro de
contatos, leitura e atualização de contatos e `/avatars/{seed}.svg`.
Tinha 28 contatos em sete etapas, de potencial a perdido, com datas relativas
ao dia atual e avatares locais com iniciais.

`demo/seed_db.py` criava cinco agentes e sessenta eventos de auditoria,
identificados por `source='seed'` para evitar duplicação. Era executado
pelo serviço `db-seed`, com `PYTHONPATH=/code` e `get_pool()` em vez de
capturar uma referência ainda nula do pool.

`docker-compose.demo.yml` iniciava PostgreSQL na porta 5433, servidor
simulado na 8095, aplicação na 8000 e população do banco. Bastava apontar
`CHATWOOT_BASE_URL` para a simulação; a aplicação não foi modificada.

`demo/screenshot.py` usava Playwright e Chromium para capturar quadro,
modal e painel nos temas claro e escuro. Os arquivos ficavam em `docs/demo/`.

## Documentação e decisões

README recebeu exemplos e instruções; foram criados `docs/demo/README.md`,
ADR-018 e esta sessão. Os índices foram atualizados. A simulação HTTP externa,
as datas relativas e os avatares locais evitavam alterar o código de produção.

## Validação registrada

Ruff passou. Foram consultadas as rotas simuladas e `/health`,
`/kanban/config`, `/kanban/board`, `/kanban/stats` e `/kanban/stats/history`.
O quadro tinha sete colunas com contatos e tarefas. As capturas tinham conteúdo.

Na máquina da sessão, foi necessário `DOCKER_API_VERSION=1.44`, pois o
cliente negociava uma versão anterior à do serviço Docker.

## Próximos passos registrados

Revisar visualmente as capturas e enviar as alterações por `develop`,
seguindo o fluxo de revisão antes da integração em `main`.

## Disponibilidade nesta cópia

As ferramentas `demo/` e `docker-compose.demo.yml` eram ignoradas pelo Git
e não estão presentes. As capturas foram atualizadas em português durante
a auditoria, usando dados simulados no navegador; isso não reproduz a
verificação histórica de PostgreSQL e Chatwoot.
