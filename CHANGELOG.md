# Histórico de alterações

As alterações relevantes do projeto são registradas neste arquivo.
O formato segue [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
e as versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Alterado

- O quadro fica oculto até a conta estar pronta; um painel único conduz a
  ativação, mostra o progresso da configuração, falhas com nova tentativa e
  conta desativada (ADR-043).
- "Token de serviço" passa a se chamar "Token de acesso", com ajuda para
  encontrá-lo no Chatwoot; o erro de token aparece junto do campo (ADR-043).
- A conexão em tempo real só abre depois da ativação (ADR-043).
- Conta desativada é reativada só com o token de acesso; o quadro não mostra
  mais "Conta não habilitada para o Kanban" (ADR-043).
- Clicar em "Pipeline" no menu lateral abre o Kanban direto, como os grupos
  nativos do Chatwoot (ADR-044).
- Filtros Responsável, Etiqueta e Tarefa com menu no padrão do Chatwoot:
  opção "todas", cor da etiqueta, pesquisa, teclado e estado vazio (ADR-044).
- A página do quadro não rola mais inteira: cabeçalho e filtros ficam fixos,
  cada coluna rola com a etapa visível e as barras de rolagem são finas (ADR-045).
- "Novo funil", "Editar funil" e "Arquivar funil" ficam na barra superior do
  quadro; "Gerenciar funil" vira a janela "Etapas"; motivos de perda,
  importação e configuração da conta vão para Configurações (ADR-045).
- Cartões mais compactos: uma marcação de tempo e um indicador de tarefa, sem
  rolagem horizontal nas colunas; texto, vencimento e responsável da tarefa
  aparecem ao abrir a negociação (ADR-045).
- Barra do quadro no padrão das listas do Chatwoot: busca "Pesquisar..." de
  largura fixa, filtros à direita e "Adicionar negociação" no fim; o ponto de
  status abre Configurações (ADR-045).
- Métricas no padrão do Chatwoot: filtros por menu, comparações só com período
  anterior, "—" sem base, estado vazio de origem com atalho para Configurações,
  cor das etapas e gráficos mais legíveis (ADR-046).

### Adicionado

- Página Tarefas no menu Pipeline: lista das tarefas abertas por vencimento,
  com abas Vencidas, Vencem hoje e Agendadas, que abre a negociação no Kanban
  (ADR-045).
- Página Configurações no menu Pipeline com a configuração da conta: situação,
  atributos do contato, motivos de perda, importação de contatos, token de
  acesso, desativação e detalhes técnicos (ADR-045).
- Auditoria de UX do Pipeline contra o Chatwoot 4.18, com capturas de antes e
  depois em `docs/evidencias/auditoria-ux/`.
- Testes de navegador `tests/browser/activation.cjs` (estados da ativação),
  `tests/browser/filters.cjs` (menus de filtro), `tests/browser/pages.cjs`
  (Tarefas e Configurações) e `tests/browser/metrics.cjs` (Métricas).

## [0.2.0-rc.3] — 2026-09-25

Versão candidata com criação automática de negociações e carregamento mais rápido.

### Adicionado

- Entrada automática por funil: lead novo no Chatwoot vira negociação na etapa
  escolhida, só no primeiro contato e com filtro por caixa de entrada (ADR-040).

### Alterado

- Quadro abre mais rápido: sessão em cache curto, funil padrão numa consulta,
  arquivos estáticos em cache, painel mantido ao navegar (ADR-041).
- Responsável do cartão vem da conversa aberta, não da resolvida mais recente.
- Branch principal renomeada para `main` e protegida; instalador em
  `installer-main` (ADR-042).

### Atualização

- A migração 013 adiciona a configuração de entrada automática aos funis; o
  serviço de migração aplica na implantação.

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
