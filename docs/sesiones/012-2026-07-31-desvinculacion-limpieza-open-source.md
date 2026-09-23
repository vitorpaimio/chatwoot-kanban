# Sessão 012 — Independência, limpeza e publicação do código

- **Data:** 2026-07-31
- **Natureza:** registro histórico, revisado em português do Brasil.

## Objetivo e estado registrado

Preparar `chatwoot-kanban` para publicação no GitHub, removendo configuração
vinculada à empresa anterior e adotando a intenção de licença MIT (ADR-017).
A sessão declarou o projeto pronto para publicação.

## Código

- `postgres_host` passou a `postgres`.
- Criados `chatwoot_bot_email` e `chatwoot_frontend_url`.
- Título da aplicação alterado para `Chatwoot-Kanban`.
- Quatro usos do e-mail fixo no banco passaram a usar configuração.
- O roteador passou a usar o bot configurado e retornar a URL da interface.
- Links do HTML passaram a usar a URL fornecida pela configuração.
- Oito ocorrências de e-mail nos testes passaram a `bot@example.com`.

## Infraestrutura

Os serviços foram renomeados para `chatwoot-kanban-db` e
`chatwoot-kanban-app`, com rede `chatwoot_shared` e imagem
`ghcr.io/crisalva1414/chatwoot-kanban:main`. Homologação usa `:develop`.
`.env.example` ganhou os novos campos e o nome de host do serviço.
`pyproject.toml` passou a usar `chatwoot-kanban`.
Os workflows usam `${{ github.repository }}` para obter o proprietário.

## Documentação

A sessão relatou cerca de cinquenta substituições em AGENTS.md, nove ADRs
e onze sessões: nomes da empresa e domínios foram trocados por referências
genéricas e `example.com`.

Foram registrados como novos README, CONTRIBUTING, LICENSE, SECURITY,
CODE_OF_CONDUCT, CHANGELOG, ADR-017 e esta sessão. O objetivo era documentar
recursos, arquitetura, configuração, rotas e contribuições.

## Decisões

Manter o histórico arquitetural, substituir referências operacionais e
configurar e-mail e URL pelo ambiente. A sessão declarou MIT como licença.
Na cópia auditada em 2026-09-23, README e LICENSE estavam ausentes; o README
foi recriado, mas a licença não foi inventada ou atribuída novamente.

## Próximos passos registrados

Atualizar o remoto para `CrisAlva1414/chatwoot-kanban`, enviar o código,
configurar descrição, tópicos, visibilidade e proteção de branch e anunciar
o projeto no GitHub Discussions. Este documento registra a intenção;
não confirma que essas ações externas ocorreram.
