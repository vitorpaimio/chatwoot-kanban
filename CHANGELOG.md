# Histórico de alterações

As alterações relevantes do projeto são registradas neste arquivo.
O formato segue [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
e as versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Alterado

- Quadro abre mais rápido: sessão em cache curto, funil padrão numa consulta,
  arquivos estáticos em cache, painel mantido ao navegar (ADR-041).
- Responsável do cartão vem da conversa aberta, não da resolvida mais recente.

## [0.2.0-rc.2] — 2026-09-25

Versão candidata com etapa editável pelo Chatwoot e melhorias na gestão do funil.

### Alterado

- "Funil / Etapa" passa a ser uma lista no contato do Chatwoot; escolher outra
  opção move ou cria a negociação no Kanban (ADR-039).
- Menu de etapa da janela da negociação com cor, etapa atual e tipo (Ganho/Perdido).
- Janela "Gerenciar funil" redesenhada: reordenar, editar, arquivar e criar etapas
  em uma lista, com paleta de cores e tipo da etapa.
- Ícone de engrenagem padrão no botão de gerenciar o funil.

### Atualização

- O comando `update` do instalador converte o atributo "Funil / Etapa" de texto
  para lista; em instalações já prontas, o worker também faz a conversão.

## [0.2.0-rc.1] — 2026-09-24

Versão candidata com assistente de instalação e correções de rede e webhook.
A certificação completa da versão estável 0.2.0 permanece em andamento.

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

### Corrigido

- Instalador Swarm: seleciona a rede comprovadamente compartilhada pelo Traefik e
  Rails, considerando a configuração do provedor e recusando estado incompatível.
- Webhooks Swarm usam a origem pública; atualização remove apenas o webhook
  interno legado comprovadamente criado pela instalação.
- Instalação e status verificam o loader pela URL pública. O loader é registrado
  depois dessa validação e usa `async` para não bloquear DOMContentLoaded.

- Instalador Swarm: encontra o PostgreSQL também quando o alias de rede está
  declarado só no serviço (`docker service inspect`), não no container.
- Instalador Swarm: com `FORCE_SSL` no Rails, usa a origem pública HTTPS como
  `chatwoot_url`; a URL interna HTTP recebia `301`, o worker não ativava a conta e a
  API era reiniciada em loop pela sonda de saúde.
- Instalador Swarm: recusa `FRONTEND_URL` HTTP com SSL forçado antes de instalar,
  evitando persistir uma configuração que repetiria o redirecionamento.

### Experiência de instalação

- Assistente no terminal com setas, seleção de várias contas e opção de marcar
  todas; confirmação antes de instalar e ativar.
- Resumo e progresso em português, com diagnóstico técnico separado em `--details`.
- Menu para retomar, verificar, atualizar e remover uma instalação existente;
  `--all-accounts` disponível para instalação sem interação.

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
