# ADR-045 — Páginas Tarefas e Configurações, ações do funil e rolagem do quadro

Estado: aceito em 25/09/2026.
Complementa os ADRs 024 (menu), 027 (acesso pelo menu Pipeline) e 041.

## Contexto

O colaborador pediu duas páginas no menu Pipeline: **Tarefas**, com uma lista
simples, e **Configurações**. A primeira versão de Configurações mostrava as notas
de versão; na revisão, o colaborador pediu para tirá-las e deixar na página só o
que é configuração de fato, ou seja, o que não precisa ficar no Kanban, em
Tarefas ou em Métricas. Pediu também para levar os botões de dentro de
"Gerenciar funil" para a barra superior do quadro (UX-37, UX-05).

A terceira rodada da [auditoria de UX](../auditoria-ux-2026-09-25.md) também
mostrou dois problemas de rolagem:

- **UX-39:** a página do quadro era cerca de 27 px mais alta que a janela.
  Qualquer giro da roda do mouse ou do touchpad rolava a página inteira,
  levando o cabeçalho e os filtros junto.
- **UX-52:** ao tornar as colunas roláveis, apareceu a barra nativa grossa do
  Windows, com setas.

## Decisão

**Menu.** O grupo Pipeline passa a ter quatro páginas, na ordem Kanban,
Tarefas, Métricas e Configurações. Cada uma abre no mesmo painel com iframe. Os
ícones seguem o desenho do Lucide: `list-checks` e `settings`.

**Tarefas** (`/kanban/tarefas`, `GET /kanban/tasks`):

- **O que lista:** as tarefas ativas cuja negociação o usuário pode ver, pela
  mesma `kb_visible_cards` do quadro. Agentes só veem tarefas de contatos das
  suas caixas.
- **Colunas:** tarefa, negociação (contato, funil e etapa), vencimento com
  estado (Vencida, Vence hoje, Agendada) e responsável.
- **Ordem:** pelo vencimento, da data mais antiga para a mais distante.
- **Filtro:** abas no padrão `TabBar` (Todas, Vencidas, Vencem hoje, Agendadas),
  com a contagem de cada uma.
- **Ação:** escolher uma linha, com clique, Enter ou Espaço, abre o cartão no
  Kanban pela mensagem `kanban:open-card`, que o loader já aceitava. A lista não
  edita nem conclui tarefas; isso continua no cartão.
- **Carga e atualização:** 100 linhas por página, com "Carregar mais". A lista
  se atualiza pelo mesmo canal de eventos do quadro.
- **Visual:** tabela no padrão `BaseTable`, com largura máxima de 1024 px, como
  as Configurações do Chatwoot.

**Configurações** (`/kanban/configuracoes`) reúne a configuração da conta, antes
espalhada pela janela "Configuração da conta", por "Motivos de perda" e pelo item
"Importar contatos" do menu "⋯" do quadro. Não há rota nova: a página usa
`/session`, `/provisioning`, `/provisioning/retry`, `/metrics/configuration`,
`/import/estimate`, `/import`, `/activate` e `/activation`.

- **Seções**, cada uma num cartão `CardLayout` com o próprio botão de salvar:
  Situação (selo pronto/configurando/precisa de atenção, contatos importados e
  fuso), Atributos do contato, Motivos de perda, Importação de contatos
  (situação, contatos por lote, importar e retomar), Token de acesso, Desativar o
  Pipeline e Detalhes técnicos (recolhido, com os recursos em nomes legíveis e
  "Reaplicar configuração").
- **Retorno:** erros ficam no próprio cartão; sucesso aparece num aviso no topo,
  escuro, por 2,5 s, como o Snackbar do Chatwoot.
- **Desativar** pede confirmação num `<dialog>` no padrão `Dialog type="alert"`
  (Cancelar e Desativar lado a lado, em ruby).
- **Acesso:** só administradores veem os cartões; agentes veem uma explicação.
  Sem ativação ou com a conta desativada, a página orienta a ativar pelo Kanban,
  com o botão "Abrir Kanban".
- **Navegação entre páginas:** a mensagem nova `kanban:open-page`
  (`{account, page}`) pede ao loader para abrir outra página do Pipeline no mesmo
  painel. O loader só aceita chaves de página conhecidas e só do iframe aberto,
  na mesma origem. O Kanban usa isso no botão "Abrir configurações" dos estados
  de falha da ativação.
- **Notas de versão:** saem da interface, com o parser, a rota `/releases` e a
  cópia do `CHANGELOG.md` no `Dockerfile`.

**Barra superior do quadro.** As ações de funil que ficavam dentro de "Gerenciar
funil" vão para a direita do cabeçalho, como no `ContactHeader` do Chatwoot:

- "Etapas" (`ghost` sm) abre só a lista de etapas do funil aberto;
- "⋯" abre "Editar funil" e "Arquivar funil" (este oculto no funil principal);
- um separador `w-px h-4` em `border-strong`;
- "Novo funil" (`faded` sm) por último.

O ponto de status passa para o lado do título. "Motivos de perda" e
"Configuração da conta" saem da janela e vão para Configurações. Só
administradores veem as ações.

**Componente compartilhado.** O menu de filtro (`filterMenu`, ADR-044) sai do
`kanban.js` para `app/static/ui.js` (`window.PipelineUI`), para Métricas usar o
mesmo componente.

**Rolagem do quadro.**

- **Página:** a página do quadro (`body.board-page`) tem altura fixa. Cabeçalho,
  barra e resumo não rolam.
- **Quadro e colunas:** o `#board` rola na horizontal, e cada coluna rola na
  vertical, com o cabeçalho da etapa fixo no topo (`position: sticky`).
- **Barras:** quadro e colunas usam `scrollbar-width: thin` com a cor
  `slate-6`.
- **Modo de ativação:** a página volta a ter altura livre, para o painel caber
  em telas baixas.

**Cartões nas colunas roláveis (UX-53).** Com valores e tarefas, a linha de baixo
do cartão ficou mais larga que a coluna e gerou rolagem horizontal. O cartão
passa a mostrar uma única marcação de tempo (a última atividade); o tempo na
etapa fica na dica dela. As colunas cortam qualquer excesso na horizontal em vez
de rolar. A tarefa saiu do cartão na rodada seguinte (UX-54, abaixo).

**Barra do quadro e ponto de status (UX-18, UX-14, UX-06).**

- **Barra:** segue as listas do Chatwoot (Contatos, Caixas de Entrada). A busca
  "Pesquisar..." tem 240 px e fica à esquerda; Responsável, Etiqueta, Tarefa e
  "⋯" ficam à direita; depois vêm um separador e "Adicionar negociação" no fim.
- **Ponto de status:** vira um botão. Para administradores, abre Configurações,
  onde está a Situação da conta; o estado do tempo real fica na dica.

**Tarefa fora do cartão (UX-54).** O cartão mostra só um indicador de tarefa:
cinza se agendada, âmbar se vence hoje e ruby se vencida, com o detalhe na dica.
O texto, o vencimento e o responsável da tarefa aparecem ao abrir a negociação,
numa seção "Tarefa". Isso elimina o avatar repetido do responsável. Na mesma
janela, a sincronização só aparece quando não está em dia (UX-34).

## Consequências

- Novo roteador `app/routers/pages.py` (`GET /kanban/tasks`), testado em
  `tests/test_pages.py`: rota, visibilidade por caixa e conta desativada.
- `tests/browser/pages.cjs` cobre Tarefas e todas as seções de Configurações.
  `tests/browser/phase2.cjs` passa a cobrir a barra superior do quadro e os
  estados da conta, e `filters.cjs` confirma que a página do quadro não rola.
- `tests/browser/sidebar.cjs` espera cinco ícones no menu (o grupo e quatro
  páginas); `board-design.cjs` e `live.cjs` foram ajustados para a janela
  "Etapas" e o botão "Novo funil" no cabeçalho. Os três exigem o Chatwoot real
  com login e ainda não foram executados nesta versão.
- O arraste de cartões entre colunas passa a acontecer dentro de colunas
  roláveis. O Chrome rola a coluna automaticamente perto das bordas, mas isso
  ainda precisa ser validado com `drag.cjs` no Chatwoot real.

Ver [sessão 043](../sesiones/043-2026-09-25-auditoria-ux-pipeline.md).
