# ADR-024 — Pipeline com componentes clonados do menu nativo

Data: 23/09/2026. Estado: aceito. Complementa o ADR-020.

O loader anterior acrescentava um botão com estilos próprios ao fim do menu.
Agora ele clona o DOM dos componentes SidebarGroup, SidebarGroupHeader e
SidebarGroupLeaf do Chatwoot 4.16.2. Preserva classes e atributos `data-v-*`,
remove destinos do roteador, contadores e identidade dos itens originais, e
cria os SVGs Lucide com a mesma dimensão e traço. Não altera o código do Chatwoot,
nem seu roteador ou histórico. Os únicos destinos são iframes da mesma origem.

## Seletores e compatibilidade

- Menu: `aside nav`, seguido de `:scope > ul`.
- Posição: `a[href*="/contacts"]`, ascendendo até o `li` direto da lista;
  inserir depois. Fallbacks: antes de `a[href*="/reports"]`, depois antes de
  `a[href*="/settings"]`. Nunca procurar rótulos traduzidos.
- Modelo de grupo: `:scope > ul > li a[href] .size-4` em um `li` nativo;
  cabeçalho: `:scope > [role="button"]`; folha: `:scope > ul > li` com ícone.
- Estado ativo: `li.child-item > a[aria-current="page"]`, comparado com folha
  inativa. Os tokens de 4.16.2 são fallback quando a rota atual não tem folha ativa.
- Recolhido: `:scope > div.relative > button`. Nessa versão, o Vue desmonta
  as folhas e os href dos grupos. Reutilizamos o `li` localizado anteriormente;
  na primeira carga recolhida, usamos os ícones nativos `i-lucide-contact`,
  `i-lucide-chart-spline` e `i-lucide-bolt`, sem depender do idioma.
- Na primeira carga recolhida sem folhas disponíveis, os dois itens do popover
  clonam um botão nativo. Assim que o menu expande, passam a clonar folhas nativas.
- Tema: `body.dark`, conforme o helper de tema da instalação local.

`bee-pipeline-open` guarda a expansão; sem acesso ao armazenamento, o estado
continua em memória. A seta mantém a regra nativa desta versão: visível para cima
quando aberto, oculta quando fechado. O recolhido mostra só o ícone; um clique
abre os dois destinos em um popover. Enter, espaço e Escape são suportados.

Ao abrir um painel, o loader preserva e suspende os destaques nativos. Ao fechar,
restaura somente atributos que ainda correspondem ao valor aplicado pelo loader,
sem sobrescrever mudanças posteriores do Vue. O MutationObserver acompanha filhos,
classes, href e aria-current; durante a reconciliação, fica desconectado para evitar
ciclos. Também reposiciona o grupo se permissões ou carregamento assíncrono mudarem
a lista. Não modifica formulários ou dados do quadro.

`/kanban/metricas?account=N` oferece somente uma página de título, fechamento e
tema, conforme o escopo solicitado. O endpoint autenticado de relatórios existente
continua independente. A atualização exige recarregar a aba para executar o loader novo.

Um ResizeObserver do `aside` mantém a borda do iframe alinhada durante o
redimensionamento nativo, sem polling nem alterações no componente Vue.
