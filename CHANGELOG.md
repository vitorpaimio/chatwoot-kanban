# Histórico de alterações

As alterações relevantes do projeto são registradas neste arquivo.
O formato segue [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
e as versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

Preparação da 0.2.0; nenhuma nova tag ou release publicada nesta etapa.

### Integração e operação

- Comando de instalação na VPS com descoberta de Chatwoot e imagem de ferramentas.
- Repositório e imagem públicos; canal privado de vulnerabilidades habilitado.

- Sessão humana e autorização por conta/caixa em cartões, histórico, métricas e SSE.
- Negociações múltiplas, exclusão recuperável e tarefa compartilhada por contato.
- Catálogo de atributos, importação retomável, reconciliação e sondas operacionais.
- Quadro com paginação e filtros no servidor; capacidade medida na referência local.
- Instaladores Swarm/Traefik e Compose/Nginx com backup, restore e remoção seletiva.
- CI cobre instalador e JavaScript próprio; registra digest da imagem e commit testado.
- Licença MIT confirmada pelo mantenedor para a 0.2.0.

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

Nota histórica: a auditoria anterior encontrou ausência de `LICENSE` e publicação
apenas ARM64. A licença MIT foi restaurada; a CI configura duas arquiteturas, cuja
compilação não equivale a certificação operacional. A autenticação vigente usa a
sessão do Chatwoot, sem validação JWT do Cloudflare.

[0.1.0]: https://github.com/CrisAlva1414/Chatwoot-Kanban/releases/tag/v0.1.0
