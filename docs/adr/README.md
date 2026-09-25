# Registros de decisões arquiteturais

Este diretório usa o [modelo de ADR](000-template.md) para registrar contexto,
decisão e consequências. "Aceito" registra uma decisão; não comprova que
todos os controles planejados estejam implementados.

| Número | Estado | Decisão |
|--------|--------|---------|
| 001 | Aceito | [Dashboard App como ponto de integração com o Chatwoot](001-dashboard-app-como-superficie-de-integracion.md) |
| 002 | Aceito | [Usuário de serviço único para autenticação na API do Chatwoot](002-bot-user-unico-token-chatwoot.md) |
| 003 | Aceito | [Cloudflare Access como autenticação dos agentes](003-cloudflare-access-auth-agentes.md) |
| 004 | Aceito | [Registro de auditoria próprio para atribuir ações](004-audit-log-aplicativo-atribucion.md) |
| 005 | Aceito | [Modelo de tarefas: banco próprio e espelho no Chatwoot](005-modelo-datos-tareas.md) |
| 006 | Substituído pelo ADR-016 | [Kanban sobre atributos personalizados de conversas](006-kanban-pipeline-custom-attributes.md) |
| 007 | Aceito | [Tecnologias e estratégia de implantação](007-stack-tecnico-y-deploy.md) |
| 008 | Aceito | [ADRs como registro de decisões](008-adr-como-registro.md) |
| 009 | Aceito | [Estrutura do repositório](009-estructura-del-repositorio.md) |
| 010 | Aceito | [Implantação e exposição da aplicação](010-deploy-y-exposicion.md) |
| 011 | Aceito | [Integração com o Chatwoot por etapas](011-integracion-con-chatwoot.md) |
| 012 | Aceito | [Escrita no Kanban e sistema de tarefas](012-operaciones-escritura-kanban.md) |
| 013 | Aceito | [Branches e proteção da produção](013-modelo-ramas-y-gate-proteccion.md) |
| 015 | Aceito | [Integração contínua e implantação](015-pipeline-ci-cd.md) |
| 016 | Aceito | [Migração de conversas para contatos](016-migracion-conversation-a-contact-based.md) |
| 017 | Aceito | [Independência do projeto e abertura do código](017-desvinculacion-y-apertura-open-source.md) |
| 018 | Aceito | [Demonstração com API simulada do Chatwoot](018-demo-mockup-chatwoot.md) |
| 019 | Aceito | [Português do Brasil como idioma do projeto](019-localizacao-portugues-brasil.md) |

Estados: proposto, aceito, descontinuado ou substituído. Preserve o histórico
quando uma decisão for substituída. O número 014 está ausente nesta cópia.

## Decisões vigentes da integração interna

- [ADR-020 — Interface interna e sessão](020-integracao-nativa-sessao.md)
- [ADR-021 — Contas e migrações](021-contas-migracoes.md)
- [ADR-022 — Sincronização transacional](022-sincronizacao-transacional.md)
- [ADR-023 — Execução e publicação](023-execucao-publicacao.md)
- [ADR-024 — Menu Pipeline nativo](024-menu-pipeline-nativo.md)
- [ADR-025 — Design system do quadro](025-design-system-quadro.md)
- [ADR-026 — Métricas visuais](026-metricas-visuais.md)
- [ADR-027 — Negociação e menu lateral](027-negociacao-menu-lateral.md)

- [ADR-028 — Métricas temporais e motivos de perda](028-metricas-temporais.md)
- [ADR-029 — Contratos e plano da release 0.2.0](029-plano-release-0.2.0.md)

- [ADR-030 — Autorização por caixa e ativação](030-autorizacao-caixas-ativacao.md)
- [ADR-031 — Negociações múltiplas e estabilidade da edição](031-negociacoes-multiplas-edicao.md)
- [ADR-032 — Exclusão recuperável de negociações](032-exclusao-recuperavel-negociacoes.md)
- [ADR-033 — Provisionamento e recuperação por conta](033-catalogo-atributos.md)
- [ADR-034 — Quadro paginado, tarefas e capacidade local](034-quadro-paginado-capacidade.md)

- [ADR-035 — Instalador Swarm e ciclo de vida](035-instalador-swarm.md)
- [ADR-036 — Instalador Compose/Nginx](036-instalador-compose-nginx.md)

- [ADR-037 — Gate da release 0.2.0](037-gate-release.md)

- [ADR-038 — Instalação na VPS](038-instalacao-vps.md)

- [ADR-039 — Funil / Etapa como lista editável](039-etapa-lista-editavel.md)

- [ADR-041 — Carregamento rápido do quadro](041-carregamento-quadro.md)
- [ADR-040 — Criação automática de negociações](040-criacao-automatica-negociacoes.md)
