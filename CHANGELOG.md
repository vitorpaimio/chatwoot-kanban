# Integração interna — 23/09/2026

- Menu e quadro incorporado ao Chatwoot, com sessão existente e visão por conversa.
- Múltiplas contas/funis, tarefas compartilhadas, valores, histórico e relatórios.
- Alembic, fila transacional, worker, webhooks assinados e atualização SSE.
- Execução local em localhost:3000, preservação do código do Chatwoot e stack futura Swarm.
- Testes com PostgreSQL e Chatwoot reais; licença MIT original restaurada.

# Histórico de alterações

As alterações relevantes do projeto são registradas neste arquivo.
O formato segue [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
e as versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Alterado

- Interface, mensagens próprias, instruções e documentação em português do Brasil.
- Idioma HTML e formatação de datas definidos como `pt-BR`.
- Documentação de segurança corrigida para explicitar a ausência de validação JWT.

### Corrigido

- Proteção de textos e atributos HTML nos cartões e no painel.
- Interpretação de datas sem horário no fuso brasileiro.
- Tratamento de falhas no carregamento da configuração e do painel.
- Remoção de segredo da documentação histórica e do CDN Tailwind sem uso.

### Adicionado

- Testes JavaScript de datas e proteção HTML, incluídos no CI.
- Auditoria técnica, ADR de localização e registro da sessão de 2026-09-23.
- README na raiz com instruções e limitações verificadas nesta cópia.

## [0.1.0] — 2026-07-31

### Adicionado

- Primeira versão pública, declarada no histórico como código aberto sob licença MIT.
- Quadro Kanban com movimentação de cartões entre etapas por arrastar e soltar,
  usando atributos personalizados do Chatwoot.
- Gestão de tarefas com transições automáticas de estado.
- Sincronização bidirecional pelos atributos `kanban_view_mensaje` e
  `kanban_view_fecha_termino`.
- Recepção de eventos `contact_updated` e `conversation_updated`, com HMAC opcional.
- Painel com estatísticas por agente e histórico de auditoria.
- Integração por iframe com Dashboard Apps do Chatwoot.
- Tema escuro por `prefers-color-scheme`.
- Construção Docker em múltiplas etapas e execução sem usuário administrador.
- GitHub Actions para testes e publicação de imagens no GHCR.
- Configurações preparatórias para Cloudflare Access.

Nota da auditoria: esta cópia não contém `LICENSE`; os workflows publicam apenas
`linux/arm64`, e a aplicação não implementa a validação JWT. Declarações antigas
sobre esses recursos não comprovam sua implementação.

[0.1.0]: https://github.com/CrisAlva1414/Chatwoot-Kanban/releases/tag/v0.1.0
