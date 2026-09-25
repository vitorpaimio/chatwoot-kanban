# Sessão 043 — Auditoria de UX do Pipeline

Antes de alterar o visual, o colaborador pediu uma revisão completa do Pipeline
contra o padrão de UX do Chatwoot, com cada tela analisada e documentada como
linha de base. Resultado em [auditoria de UX](../auditoria-ux-2026-09-25.md).
A primeira entrega (fluxo de ativação) está mais abaixo.

## Ambiente

- Chatwoot CE 4.18.0 oficial (mesmo digest de `deploy/lab/stack.yml`) em Docker
  no WSL, com o Kanban da `master` (`c21a271`) em recarga automática, atrás de
  um Nginx em `localhost:3080`. Configuração local em `.local/dev/`, fora do Git.
- Conta nova, loader instalado e ativação pela interface.

## Alterações

- `docs/auditoria-ux-2026-09-25.md`: padrão de referência do Chatwoot 4.18 com
  fonte no código (commit `9f920b5`), o que já está alinhado, análise das seis
  telas, 25 achados (`UX-01` a `UX-25`) com prioridade, glossário de textos,
  escopo não coberto, testes afetados e limitações.
- `docs/evidencias/auditoria-ux/antes/`: seis capturas da linha de base. Nas
  telas 3 e 5, a faixa do menu lateral foi recortada para não publicar dados da
  conta.

## Decisões

- A referência passa a ser o Chatwoot 4.18.0. Os ADRs 024 e 025 e
  `board-design.cjs` foram validados na 4.16.2, então a primeira alteração
  visual deve vir com um ADR (043) que atualize essa premissa.
- O contorno de foco de 2 px do Pipeline fica, por acessibilidade, mesmo sendo
  mais forte que o do Chatwoot.

## Fluxo de ativação (UX-01 e ativação)

Primeira entrega da auditoria, registrada no
[ADR-043](../adr/043-ativacao-e-referencia-chatwoot-418.md).

- `app/templates/kanban.html`: o cartão de ativação vira o painel `#activation`
  (título, texto, indicador de progresso, formulário com ajuda e erro, ações).
- `app/static/kanban.js`: `setupState` e `setup` escolhem o estado pelo
  `/session`; `init` só carrega o quadro e abre o tempo real (`connect`) com a
  conta pronta; a consulta a cada 5 s não se duplica e espera o fim da edição.
  O envio do token mostra "Ativando…" e trata 400 e 422 junto do campo. O quadro
  sem funil diz "Nenhum funil ativo nesta conta.", e a configuração passa a
  pedir "Novo token de acesso".
- `app/static/kanban.css`: `body.setup-mode` oculta barra, resumo, quadro e
  ponto; estilos do painel no padrão `Dialog`/`Input` do Chatwoot 4.18; o giro
  do indicador fica mais lento com `prefers-reduced-motion`.
- `tests/browser/activation.cjs` (novo) e `tests/browser/phase2.cjs`
  (atualizado para o painel).
- Capturas em `docs/evidencias/auditoria-ux/depois/`, nos temas claro e escuro.

### Validação

- `node --test tests/test_interface.cjs`: 4 aprovados; `node --check` sem falhas
  em `app/static/*.js` e `tests/browser/*.cjs`.
- Navegador com a API controlada (Chrome no Windows): `activation.cjs`,
  `phase2.cjs` e `authorization.cjs` aprovados. O teste novo pegou um defeito
  durante o desenvolvimento: `hidden` não existe em elementos SVG, e o indicador
  não aparecia (corrigido com `toggleAttribute`).
- `phase3.cjs` falha na linha 144 também na `master` sem alterações: é o
  problema previsto na auditoria, anterior a esta entrega.
- Sem mudança em Python; Ruff e pytest não foram rodados nesta entrega.
- Não validado: `board-design.cjs`, `sidebar.cjs`, `live.cjs` e `drag.cjs`, que
  exigem sessão no Chatwoot real, e o quadro pronto dentro do Chatwoot autenticado.

## Menu, reativação e filtros (segunda rodada)

O colaborador testou a primeira entrega e trouxe quatro pontos: o clique em
"Pipeline" só abria o submenu (UX-26); a reativação deveria ser só o token, e
apareceu "Conta não habilitada para o Kanban" (UX-27); o filtro de etiqueta
sem UX (UX-08); e dados demo para testar o quadro. Decisões nos ADRs 043
(atualizado) e [044](../adr/044-menu-e-filtros-chatwoot-418.md).

- `app/static/loader.js`: sem página aberta, o clique no grupo abre o Kanban.
- `app/static/kanban.js`:
  - a conta desativada mostra o formulário "Reativar Pipeline";
  - `init` fecha o tempo real fora do estado pronto;
  - `load` também ignora contas desativadas;
  - eventos que recebem 403 chamam `init` de novo;
  - `filterMenu` cobre Responsável, Etiqueta e Tarefa.
- `app/static/kanban.css`: gatilho, menu, opções, ponto de cor e estado vazio
  dos filtros.
- Testes:
  - `tests/browser/filters.cjs` (novo);
  - `activation.cjs`: reativação e 403 vindo de outra aba;
  - `sidebar.cjs`: novo clique, ainda não executado.
- Capturas: `antes/08`, `antes/11` e `antes/12` (prints do autor); `depois/08`,
  `depois/12` e `depois/13` refeitas com o CSS real do Chatwoot 4.18.
- Dados demo no Chatwoot local: scripts em `.local/dev/seed/`, fora do Git.

### Validação

- `filters.cjs`, `activation.cjs`, `phase2.cjs` e `authorization.cjs` aprovados
  com a API controlada; `node --check` sem falhas.
- Não validado: o clique no menu dentro do Chatwoot autenticado (`sidebar.cjs`,
  `drag.cjs` e `live.cjs` exigem login).

## Tarefas, Configurações e rolagem (terceira rodada)

Com os dados demo, o colaborador pediu as páginas Configurações (com as notas de
versão da versão instalada) e Tarefas (lista simples). Também relatou que "o
hover movia tudo" e pediu a análise de todas as capturas do quadro com dados e
das Métricas. Decisão no [ADR-045](../adr/045-paginas-tarefas-configuracoes.md).

**Diagnóstico da rolagem.** Com o CSS real do Chatwoot e 40 negociações
simuladas:

- passar o mouse sobre os cartões não movia nada;
- a roda do mouse rolava o documento inteiro (`scrollY` 27, cabeçalho em -27);
- a causa era `#board` com `min-height: calc(100vh - 172px)` mais o padding;
- com a correção, `scrollY` fica em 0, a coluna rola sozinha (447 px) e o
  cabeçalho da etapa continua no topo.

Alterações:

- **Backend:**
  - `app/releases.py` e `app/routers/pages.py`, com as rotas `GET
    /kanban/tasks` e `GET /kanban/releases`;
  - páginas `/kanban/tarefas` e `/kanban/configuracoes` em `app/main.py`.
- **Frontend:**
  - templates `tarefas.html` e `configuracoes.html`;
  - scripts `tarefas.js` e `configuracoes.js`;
  - estilos `paginas.css` (`TabBar`, `BaseTable` e `CardLayout`);
  - `loader.js` com quatro páginas e ícones `list-checks` e `settings`;
  - `kanban.css` com a página de altura fixa, colunas roláveis e barra fina.
- **Build:** `Dockerfile` e `.dockerignore` distribuem o `CHANGELOG.md`. O
  compose local o monta em `/app`.
- **Testes:**
  - `tests/test_pages.py` e `tests/browser/pages.cjs` (novos);
  - `filters.cjs` confirma que a página do quadro não rola;
  - `sidebar.cjs` espera 5 ícones no menu.
- **Auditoria:** terceira rodada com UX-28 a UX-52, sendo UX-39 e UX-52
  atendidos e UX-37 parcial. Capturas `antes/17` a `antes/23` e `depois/14` a
  `depois/16`.
- **Dois defeitos pegos pelos testes antes da entrega:**
  - `configuracoes.js` usava o retorno de `append()`, que é `undefined`;
  - o script de captura carregava o iframe antes do CSS do Chatwoot.

### Validação

- **Python** (`.venv` com Python 3.12, banco `kanban_test` do compose local):
  - Ruff sem apontamentos;
  - `tests/test_pages.py`: 7 aprovados;
  - suíte: 129 aprovados e 1 pulado.
- **Falhas de ambiente, não do código:**
  - `test_legacy.py` precisa do `pg_dump`, que não existe no Windows;
  - os testes do instalador importam `curses`, que só existe no Linux, e foram
    ignorados.
- **Navegador:** `pages.cjs`, `filters.cjs`, `activation.cjs`, `phase2.cjs` e
  `authorization.cjs` aprovados; `node --check` e `test_interface.cjs`
  aprovados.
- **Não validado:** menu com cinco itens, arraste entre colunas roláveis e a
  barra fina no Chatwoot autenticado (`sidebar.cjs`, `drag.cjs`, `live.cjs`).

## Configurações, barra do funil, cartões e Métricas (quarta rodada)

O colaborador revisou a terceira rodada e pediu:

- tirar as notas de versão de Configurações e deixar lá só o que é configuração;
- levar os botões de "Gerenciar funil" para a barra superior;
- trabalhar a tela de Métricas;
- criar tarefas na base demo;
- revisar os cartões do quadro com dados (print sem texto: rolagem horizontal
  nas colunas).

Decisões no [ADR-045](../adr/045-paginas-tarefas-configuracoes.md), atualizado, e
no [ADR-046](../adr/046-metricas-padrao-chatwoot-418.md).

- **Configurações:**
  - `configuracoes.html`/`.js` refeitos com Situação, Atributos do contato,
    Motivos de perda, Importação, Token de acesso, Desativar e Detalhes técnicos;
  - aviso de sucesso no topo e confirmação no padrão `Dialog type="alert"`;
  - saíram `app/releases.py`, a rota `/releases`, os testes de notas de versão e
    a cópia do `CHANGELOG.md` no `Dockerfile` e no `.dockerignore`.
- **Kanban:**
  - `accountSettings`, `lossReasons` e a importação saíram de `kanban.js`;
  - "Etapas", "⋯" (Editar e Arquivar funil) e "Novo funil" foram para o
    cabeçalho;
  - o menu "⋯" da barra ficou só com Histórico, com ícone SVG;
  - a mensagem `kanban:open-page` leva às Configurações;
  - o `filterMenu` foi para `app/static/ui.js`.
- **Cartões (UX-53):**
  - uma marcação de tempo por cartão, com o tempo na etapa na dica;
  - o responsável da tarefa aparece como avatar;
  - `.column` com `overflow-x: hidden`;
  - um conflito de nome de classe (`.card-actions`, já usada na janela da
    negociação) deixava os botões de Configurações sem estilo e foi renomeado
    para `.settings-actions`.
- **Métricas (UX-40 a UX-51):**
  - `metricas.html`/`.js`/`.css`: filtros por menu, variações com rótulo, nota
    única sem período anterior, exportar com ícone, ordenação e dicas, estado
    vazio de origem com ação, cor da etapa, gráfico reto, cabeçalho e rodapé;
  - `app/metrics/queries.py`: `on_time_rate` nulo sem concluídas e cor/tipo da
    etapa no funil;
  - `app/routers/metrics.py`: `dimensions` em `/options`.
- **Testes:**
  - `pages.cjs` cobre todas as seções de Configurações;
  - `phase2.cjs` cobre a barra do funil e os estados da conta;
  - `metrics.cjs` (novo) usa fixtures da base demo, com o nome do agente
    trocado;
  - `board-design.cjs` e `live.cjs` foram ajustados à janela "Etapas";
  - `test_pages.py` perdeu os testes de notas de versão;
  - `test_metrics.py` foi ampliado.
- **Base demo** (`.local/dev/seed/03_tarefas_valores.py`, fora do Git):
  - dados gravados pelas funções das rotas (`save_task`, `close_task`, `move`),
    com histórico e sincronização;
  - 18 tarefas ativas (5 vencidas, 4 para hoje, 9 futuras) e 4 concluídas;
  - valor em 20 negociações;
  - 3 movimentações para dar receita e perda às Métricas.
- **Ambiente de dev:** o `uvicorn --reload` ficava preso esperando as conexões
  SSE abertas; o compose local ganhou `--timeout-graceful-shutdown 3`.
- **Capturas:** `depois/15`, `16`, `24` (Métricas), `25` (Etapas), `26` (menu do
  funil) e `27` (cartões), nos dois temas.

### Validação

- Ruff sem apontamentos; pytest 126 aprovados e 1 pulado, sem os arquivos que
  dependem de `curses` e de `pg_dump`, indisponíveis no Windows.
- `test_interface.cjs` 4/4, `node --check` sem falhas e, com a API controlada:
  `activation`, `filters`, `phase2`, `pages`, `metrics` e `authorization`
  aprovados.
- Não validado: `sidebar`, `board-design`, `live` e `drag` no Chatwoot real com
  login.

## Tarefa na negociação, barra e ponto de status (quinta rodada)

O colaborador apontou quatro coisas:

- o responsável da tarefa aparecia duplicado no cartão;
- os dados da tarefa devem aparecer ao abrir a negociação, e não no cartão;
- a busca deve ter o tamanho da do Chatwoot;
- o ponto verde de status deve levar a Configurações.

As decisões estão no ADR-045.

- **`kanban.js`:**
  - o bloco da tarefa saiu do cartão e ficou um indicador `.task-flag`;
  - nova função `taskSummary` na janela da negociação;
  - a sincronização só aparece quando pendente ou com falha;
  - `#status-link` abre Configurações para administradores.
- **`kanban.html`/`kanban.css`:**
  - busca com 240 px e texto "Pesquisar...";
  - espaçador entre a busca e os filtros;
  - separador e "Adicionar negociação" no fim da barra.
- **Testes:**
  - `phase2.cjs` cobre o indicador, a seção da tarefa, a largura da busca, a
    ordem da barra e o atalho do status;
  - `live.cjs` e `board-design.cjs` foram ajustados ao indicador e ainda não
    foram executados.
- **Capturas:** `depois/27` (cartões) e `depois/28` (barra), nos dois temas.

## Próximos passos

- Rodar os testes com o Chatwoot real 4.18 (`board-design`, `sidebar`, `live`,
  `drag`), principalmente o arraste entre colunas roláveis.
- Pendentes: UX-07, UX-09, UX-18 a UX-25 e UX-28 a UX-36 (detalhe da negociação,
  janelas, rótulos). Parciais: UX-02, UX-06, UX-08 (selects das janelas), UX-14
  e UX-17 (seta do funil e "×").
- Métricas: decidir se `win_rate` e as conversões também devem ser nulas sem
  base (hoje 0, travado por `test_empty_period_zero_division_and_csv`).
- Cores padrão por tipo de etapa (UX-19), para as barras de Métricas e as
  colunas não ficarem todas índigo.
- Corrigir `tests/browser/phase3.cjs:144`, quebrado desde o menu de etapa da
  sessão 040.
