# Sessão 008 — Integração contínua e ambiente de homologação

- **Data:** 2026-07-17
- **Natureza:** registro histórico, revisado em português do Brasil.

## Contexto

A produção em `kanban.example.com` recebia alterações diretamente em `main`,
com implantação manual no Arcane. Faltavam proteção de branch, testes
em PRs e ambiente separado para validação.

## Decisões e alterações

ADR-013 definiu `main` protegida por verificação `test` e uma aprovação,
`develop` como base diária e `feat/<nome>` para mudanças maiores.

`developer-compose.yml` foi criado como configuração completa para outro
projeto no Arcane:

| Item | Produção | Homologação |
|------|----------|-------------|
| Imagem | `:main` | `:develop` |
| Banco | `chatwoot-kanban-db` | `chatwoot-kanban-staging-db` |
| Aplicação | `chatwoot-kanban-app` | `chatwoot-kanban-staging-app` |
| Volume | `kanban_pgdata` | `kanban_staging_pgdata` |
| Nome do banco | `kanban` | `kanban_staging` |

A sessão mencionou um ADR-014 para homologação, mas esse arquivo não está
presente. Os ADRs criados e disponíveis são 013 e 015.

ADR-015 definiu `test.yml` em PRs para `main` e `develop`, com Ruff e pytest,
e `docker_publish_develop.yml` para publicar arm64 em `:develop`.
A publicação de produção também passou a arm64, arquitetura do OrangePi5.
O Arcane ficou responsável por baixar e reimplantar, sem SSH pelo CI.

Foram atualizados AGENTS.md, convenções Git e índices de ADRs.

## Pendências registradas

- Autenticar a CLI `gh`.
- Criar e enviar `develop`.
- Configurar proteção de `main` no GitHub.
- Criar homologação no Arcane e habilitar sincronização automática.
- Configurar o túnel para `devkanban.example.com`.
- Validar o fluxo completo de envio, construção e implantação.

## Nota da auditoria

O `.env` de homologação precisa apontar para seu próprio banco e host;
compartilhar cegamente o arquivo de produção pode conectar ao ambiente errado.
A existência dos workflows não comprova a configuração externa do Arcane
nem das regras de proteção do GitHub.
