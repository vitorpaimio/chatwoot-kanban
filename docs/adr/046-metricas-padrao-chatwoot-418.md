# ADR-046 — Métricas no padrão do Chatwoot 4.18

Estado: aceito em 25/09/2026.
Atualiza o visual dos ADRs 026 e 028; mantém cálculos e rotas, exceto o indicador
de tarefas no prazo.

## Contexto

A terceira rodada da [auditoria de UX](../auditoria-ux-2026-09-25.md) listou doze
achados na página Métricas (UX-40 a UX-51):

- filtros com `<select>` nativo;
- textos colados e comparações repetidas sem período anterior;
- "0%" de tarefas no prazo sem nenhuma tarefa concluída;
- links sublinhados para exportar;
- caracteres como ícones;
- estado vazio técnico para origem e campanha;
- gráficos com curvas suavizadas e datas inclinadas;
- o termo "card" na ajuda.

Com a base demo, o colaborador pediu para trabalhar essa tela.

## Decisão

**Filtros.** Funil, Período, Responsável e Caixa usam o `filterMenu` compartilhado
(`app/static/ui.js`, ADR-044/042). As datas De/Até continuam `input type=date`,
no estilo `Input` do Chatwoot (40 px, fundo `black-alpha-2`), numa linha própria
quando o período é "Personalizado".

**Comparações.**

- Sem valor no período anterior (nulo ou zero), a variação não aparece.
- No lugar das repetições, uma única nota informa que não há período anterior
  para comparar.
- O cartão "Ganhos e receita" mostra uma linha por variação, com rótulo.
- As setas viram ícones Lucide com sinal.

**Indicadores sem base.** `on_time_rate` passa a ser nulo quando nenhuma tarefa
foi concluída no período (`app/metrics/queries.py`). A interface mostra "—" com
dica, como também em ticket médio e ciclo médio sem ganhos.

**Origem e campanha.**

- `GET /kanban/metrics/options` passa a informar em `dimensions` se há atributo
  configurado.
- Sem configuração, um estado vazio único explica. O administrador vê "Abrir
  configurações", que usa `kanban:open-page` (ADR-045), e o agente vê a
  orientação.

**Tabelas e gráficos.**

- **Ordenação:** o ícone aparece só na coluna ordenada, com `aria-sort`. A
  definição do indicador vai para a dica do cabeçalho.
- **Exportar CSV:** botão `ghost` sm com ícone de download.
- **Barras:** usam a cor de cada etapa. O nome do funil aparece só quando há
  mais de um funil.
- **Evolução:** linhas retas e datas "dd/mm" sem inclinação.

**Página.**

- O cabeçalho tem só o título. "Atualizar" é um botão `ghost` com ícone, que gira
  enquanto carrega.
- Os cartões seguem o `CardLayout` e os avisos seguem o `Banner`.
- Os tamanhos de texto seguem a escala do Chatwoot (12, 14, 16 e 24 px).
- A ajuda fala em "negociação".
- A nota sobre indicadores de atendimento vai para o rodapé.

## Consequências

- `tests/test_metrics.py` cobre o "no prazo" nulo, a cor e o tipo da etapa no
  funil e as dimensões configuradas. O novo `tests/browser/metrics.cjs` usa
  fixtures geradas da base demo (`tests/browser/fixtures/metricas.json`, com o
  nome do agente trocado).
- `win_rate`, `conversion` e `next_conversion` ainda devolvem 0 sem base. Mudar
  isso quebra `test_empty_period_zero_division_and_csv` e fica para uma próxima
  decisão.
- A receita usa o valor gravado quando a negociação entra em Ganho. Valores
  editados depois não mudam a receita daquele ganho; isso não mudou.

Ver [sessão 043](../sesiones/043-2026-09-25-auditoria-ux-pipeline.md).
