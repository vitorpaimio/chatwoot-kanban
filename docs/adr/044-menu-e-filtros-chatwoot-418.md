# ADR-044 — Clique no menu Pipeline e filtros no padrão do Chatwoot 4.18

Estado: aceito em 25/09/2026.
Complementa o ADR-024 (menu) e o ADR-043 (referência 4.18).

## Contexto

A segunda rodada da [auditoria de UX](../auditoria-ux-2026-09-25.md) trouxe dois
achados:

- **UX-26:** clicar em "Pipeline" no menu lateral só abria e fechava o submenu.
  Era preciso um segundo clique em "Kanban".
- **UX-08 e UX-14:** os filtros Responsável, Etiqueta e Tarefa usavam `<select>`
  nativo. A lista aberta tinha o visual do sistema operacional, e o nome do
  filtro aparecia também como opção. Numa conta sem etiquetas, a lista mostrava
  uma única opção sem explicação.

## Decisão

**Menu.** O cabeçalho do grupo segue o `SidebarGroup` do Chatwoot 4.18
(`SidebarGroup.vue:203-216`), que navega para o primeiro item quando o grupo não
tem página ativa:

- sem página do Pipeline aberta, o clique (ou Enter/Espaço) expande o grupo e
  abre o Kanban;
- com uma página do Pipeline aberta, o clique só recolhe o grupo, e o painel
  continua aberto;
- no menu recolhido, o clique continua abrindo o menu flutuante com Kanban e
  Métricas.

**Filtros.** `filterMenu` em `app/static/kanban.js` põe um gatilho e um menu
próprios por cima de cada `<select>` da barra:

- **Valor e eventos:** o `<select>` continua sendo a fonte do valor e dos
  eventos `input` e `change`. Fica invisível, fora da ordem de tabulação e com
  `aria-hidden`. A carga do quadro, a montagem das opções e os testes que usam
  `selectOption` não mudam.
- **Gatilho:** no estilo `Select` do Chatwoot (32 px, contorno `border-weak`,
  chevron Lucide). Com filtro aplicado, mostra o valor, com o fundo azul
  translúcido do botão `faded` azul.
- **Menu:** no estilo `DropdownMenu` (`alpha-3` com desfoque,
  `border-container`, raio de 12 px, `shadow-lg`, itens de 32 px, opção
  escolhida marcada com check), alinhado pela direita como os menus do cabeçalho
  do Chatwoot.
- **Opções:** a primeira vira "Todos os responsáveis", "Todas as etiquetas" ou
  "Todas as tarefas". Etiquetas mostram a cor da conta. Com mais de 8 opções,
  aparece o campo "Pesquisar...". Sem opções, uma frase explica ("Nenhuma
  etiqueta nesta conta.").
- **Teclado:** setas abrem e navegam, Enter e Espaço escolhem, Esc fecha e
  devolve o foco ao gatilho sem fechar o painel do Pipeline, e Tab ou clique
  fora fecham.

## Consequências

- Os `<select>` das janelas e da página de Métricas continuam nativos; UX-08
  segue parcial.
- `tests/browser/filters.cjs` cobre menus, pesquisa, teclado, estado vazio e a
  compatibilidade com `selectOption`.
- `tests/browser/sidebar.cjs` foi atualizado para o novo clique, mas precisa do
  Chatwoot real com login e ainda não foi executado nesta versão.

Ver [sessão 043](../sesiones/043-2026-09-25-auditoria-ux-pipeline.md).
