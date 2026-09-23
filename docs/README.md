# Documentação do projeto

Índice da documentação do Chatwoot-Kanban em português do Brasil.

- [Fase 1: autorização e ativação](fase-1-autorizacao.md)
- [Plano da release 0.2.0](plano-0.2.0.md)
- [Fase 0: contratos, evidências e decisões pendentes](fase-0-contratos-0.2.0.md)

- [Auditoria técnica de 23/09/2026](auditoria-2026-09-23.md)
- [Guia inicial](../README.md)
- [Convenções](format/README.md)
- [Demonstração visual](demo/README.md)

## Arquitetura

| Número | Estado | Decisão |
|--------|--------|---------|
| 001 | Aceito | [Dashboard App como ponto de integração com o Chatwoot](adr/001-dashboard-app-como-superficie-de-integracion.md) |
| 002 | Aceito | [Usuário de serviço único para autenticação na API do Chatwoot](adr/002-bot-user-unico-token-chatwoot.md) |
| 003 | Aceito | [Cloudflare Access como autenticação dos agentes](adr/003-cloudflare-access-auth-agentes.md) |
| 004 | Aceito | [Registro de auditoria próprio para atribuir ações](adr/004-audit-log-aplicativo-atribucion.md) |
| 005 | Aceito | [Modelo de tarefas: banco próprio e espelho no Chatwoot](adr/005-modelo-datos-tareas.md) |
| 006 | Substituído pelo ADR-016 | [Kanban sobre atributos personalizados de conversas](adr/006-kanban-pipeline-custom-attributes.md) |
| 007 | Aceito | [Tecnologias e estratégia de implantação](adr/007-stack-tecnico-y-deploy.md) |
| 008 | Aceito | [ADRs como registro de decisões](adr/008-adr-como-registro.md) |
| 009 | Aceito | [Estrutura do repositório](adr/009-estructura-del-repositorio.md) |
| 010 | Aceito | [Implantação e exposição da aplicação](adr/010-deploy-y-exposicion.md) |
| 011 | Aceito | [Integração com o Chatwoot por etapas](adr/011-integracion-con-chatwoot.md) |
| 012 | Aceito | [Escrita no Kanban e sistema de tarefas](adr/012-operaciones-escritura-kanban.md) |
| 013 | Aceito | [Branches e proteção da produção](adr/013-modelo-ramas-y-gate-proteccion.md) |
| 015 | Aceito | [Integração contínua e implantação](adr/015-pipeline-ci-cd.md) |
| 016 | Aceito | [Migração de conversas para contatos](adr/016-migracion-conversation-a-contact-based.md) |
| 017 | Aceito | [Independência do projeto e abertura do código](adr/017-desvinculacion-y-apertura-open-source.md) |
| 018 | Aceito | [Demonstração com API simulada do Chatwoot](adr/018-demo-mockup-chatwoot.md) |
| 019 | Aceito | [Português do Brasil como idioma do projeto](adr/019-localizacao-portugues-brasil.md) |

## Sessões

Os registros históricos descrevem o trabalho e os planos de cada data;
a auditoria distingue essas descrições da implementação presente.

| Sessão | Data | Assunto |
|--------|------|---------|
| 001 | 2026-07-09 | [Viabilidade técnica e arquitetura do Kanban e das tarefas](sesiones/001-2026-07-09-factibilidad-arquitectura-kanban-tareas.md) |
| 002 | 2026-07-09 | [Inicialização, Docker e documentação](sesiones/002-2026-07-09-inicializacion-docker-y-docs.md) |
| 003 | 2026-07-13 | [Correções de produção, testes e proteção da imagem Docker](sesiones/003-2026-07-13-fix-produccion-y-seguridad-docker.md) |
| 004 | 2026-07-15 | [Movimentação de cartões, tarefas e painel](sesiones/004-2026-07-15-drag-drop-tareas-dashboard.md) |
| 005 | 2026-07-16 | [Interface integrada ao Chatwoot e cliente HTTP robusto](sesiones/005-2026-07-16-frontend-tokens-y-client-robusto.md) |
| 005 | 2026-07-20 | [URL da conta, paginação e sincronização por webhook](sesiones/005-2026-07-20-fix-url-account-paginacion-webhook.md) |
| 006 | 2026-07-16 | [Sincronização com Chatwoot e indicação visual das tarefas](sesiones/006-2026-07-16-sync-chatwoot-badge-visual.md) |
| 007 | 2026-07-17 | [Datas, estados dinâmicos, cartões e atualização periódica](sesiones/007-2026-07-17-fix-fechas-estado-dragdrop-polling.md) |
| 008 | 2026-07-17 | [Integração contínua e ambiente de homologação](sesiones/008-2026-07-17-blindaje-ci-cd-staging.md) |
| 009 | 2026-07-23 | [Desempenho do quadro, chamadas HTTP e atualização periódica](sesiones/009-2026-07-23-performance-board-pooling-cache.md) |
| 010 | 2026-07-26 | [Migração de conversas para contatos](sesiones/010-2026-07-26-migracion-contact-based.md) |
| 011 | 2026-07-26 | [Operações em segundo plano e resposta da interface](sesiones/011-2026-07-26-non-blocking-optimizaciones.md) |
| 012 | 2026-07-31 | [Independência, limpeza e publicação do código](sesiones/012-2026-07-31-desvinculacion-limpieza-open-source.md) |
| 013 | 2026-08-30 | [Demonstração e capturas para o README](sesiones/013-2026-08-30-demo-mockup-readme.md) |
| 014 | 2026-09-23 | [Auditoria e tradução para português do Brasil](sesiones/014-2026-09-23-auditoria-traducao-pt-br.md) |

## Decisões vigentes da integração interna

- [ADR-020 — Interface interna e sessão](adr/020-integracao-nativa-sessao.md)
- [ADR-021 — Contas e migrações](adr/021-contas-migracoes.md)
- [ADR-022 — Sincronização transacional](adr/022-sincronizacao-transacional.md)
- [ADR-023 — Execução e publicação](adr/023-execucao-publicacao.md)

- [Instalação local](instalacao-local.md)
- [Validação da integração](validacao-integracao.md)
- [Sessão da entrega](sesiones/015-2026-09-23-integracao-chatwoot.md)
- [ADR-024 — Menu Pipeline nativo](adr/024-menu-pipeline-nativo.md)
- [Sessão do menu Pipeline](sesiones/016-2026-09-23-menu-pipeline.md)
- [ADR-025 — Design system do quadro](adr/025-design-system-quadro.md)
- [Sessão do visual do quadro](sesiones/017-2026-09-23-visual-quadro.md)
