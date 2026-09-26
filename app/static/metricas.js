(() => {
  const $ = (id) => document.getElementById(id),
    { money, dateBR } = window.KanbanHelpers,
    { filterMenu } = window.PipelineUI;
  const url = new URL(location.href),
    account = url.searchParams.get("account");
  const names = {
    summary: "Resumo",
    funnel: "Funil",
    losses: "Motivos de perda",
    sources: "Origem e campanha",
    team: "Equipe",
    tasks: "Tarefas",
    timeline: "Evolução",
  };
  // Glossário do Pipeline: "negociação" é o cartão do quadro (UX-50).
  const definitions = {
    leads:
      "Negociações criadas no período: manuais, importadas (na data do primeiro contato) e criadas pela entrada automática, conforme as caixas de cada funil.",
    ongoing: "Negociações em etapas abertas no fim do período.",
    wins: "Negociações que entraram numa etapa de ganho no período. Na tabela da equipe, o ganho fica com quem era responsável ao fechar.",
    revenue:
      "Soma do valor das negociações ganhas no período: o valor registrado enquanto estavam na etapa de ganho.",
    losses: "Negociações que entraram numa etapa de perda no período.",
    win_rate: "Ganhos divididos por ganhos mais perdidos no período.",
    average_ticket: "Receita dividida pelo número de ganhos.",
    open_value: "Soma do valor das negociações em etapas abertas.",
    cycle_days:
      "Tempo médio entre a criação da negociação e o ganho, nos ganhos do período.",
    conversion:
      "Das negociações que entraram na etapa no período, quantas passaram depois por uma etapa seguinte do mesmo funil, até hoje. Etapas de perda não contam como avanço.",
    loss_rate:
      "Das negociações que entraram na etapa no período, quantas foram depois para uma etapa de perda, até hoje.",
    next_conversion:
      "Das negociações que entraram na etapa no período, quantas passaram depois pela etapa seguinte.",
    dwell_days:
      "Tempo médio que as negociações ficaram na etapa, nas saídas do período.",
    forecast:
      "Valor em aberto ponderado pela chance de ganho da etapa em que cada negociação está. A chance vem do histórico: das negociações que passaram pela etapa e já fecharam, quantas foram ganhas.",
    win_probability:
      "Das negociações que passaram pela etapa e já fecharam, quantas foram ganhas. Com poucos fechamentos, a chance é instável.",
    flow: "Dos leads novos do período, quantos chegaram a cada etapa ou além. Perdas não contam como avanço; a porcentagem compara com a etapa anterior.",
    stale:
      "Negociações sem movimento, tarefa concluída ou mensagem do cliente há mais dias que o limite do funil (padrão: 7).",
    open: "Tarefas abertas no fim do período.",
    overdue: "Tarefas abertas com vencimento já passado, no horário de Brasília.",
    on_time_rate:
      "Tarefas concluídas até o vencimento, divididas pelas tarefas concluídas no período.",
    completed: "Tarefas concluídas no período.",
  };
  // Traços do Lucide (download, info, arrow-up, arrow-down, trending).
  const ICONS = {
    download: ["M12 15V3", "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "m7 10 5 5 5-5"],
    info: ["M2 12a10 10 0 1 0 20 0a10 10 0 1 0-20 0", "M12 16v-4", "M12 8h.01"],
    up: ["m5 12 7-7 7 7", "M12 19V5"],
    down: ["M12 5v14", "m19 12-7 7-7-7"],
    rise: ["M16 7h6v6", "m22 7-8.5 8.5-5-5L2 17"],
    fall: ["M16 17h6v-6", "m22 17-8.5-8.5-5 5L2 7"],
  };
  const lowerIsBetter = new Set([
    "losses",
    "cycle_days",
    "overdue",
    "overdue_tasks",
    "dwell_days",
  ]);
  const charts = new Map(),
    loaded = new Map(),
    // Comparações exibidas e omitidas por bloco, para a nota única (UX-42).
    comparisons = new Map();
  let generation = 0,
    configuration = {},
    administrator = false,
    source,
    debounce;
  const el = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text != null) n.textContent = String(text);
    if (cls) n.className = cls;
    return n;
  };
  const icon = (name, cls = "icon") => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", cls);
    svg.setAttribute("aria-hidden", "true");
    for (const d of ICONS[name]) {
      const path = document.createElementNS(svg.namespaceURI, "path");
      path.setAttribute("d", d);
      svg.append(path);
    }
    return svg;
  };
  const num = (n) =>
    n == null
      ? "—"
      : Number(n).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  const PERCENT = [
    "win_rate",
    "on_time_rate",
    "conversion",
    "next_conversion",
    "loss_rate",
    "win_probability",
  ];
  const format = (key, value) =>
    value == null
      ? "—"
      : ["revenue", "average_ticket", "open_value", "value", "forecast", "lost_value"].includes(key)
        ? money(value)
        : PERCENT.includes(key)
          ? num(value) + "%"
          : key.endsWith("_days")
            ? Number(value) > 0 && Number(value) < 1
              ? num(Number(value) * 1440) + " min"
              : num(value) + " dias"
            : num(value);
  const color = (token) =>
    `rgb(${getComputedStyle(document.documentElement)
      .getPropertyValue("--" + token)
      .trim()})`;
  const stageColor = (row) =>
    /^#[\da-f]{6}$/i.test(row.color || "") ? row.color : color("blue-9");
  function help(key, label) {
    const b = el("button", null, "definition");
    b.type = "button";
    b.title = definitions[key] || key;
    b.setAttribute("aria-label", `${label}: ${b.title}`);
    b.append(icon("info"));
    return b;
  }
  // Variação percentual; sem valor anterior (nulo ou zero) não há comparação.
  function delta(current, previous) {
    if (current == null || previous == null || Number(previous) === 0)
      return null;
    return ((current - previous) / Math.abs(previous)) * 100;
  }
  function tally(block, shown) {
    const count = comparisons.get(block) || { shown: 0, omitted: 0 };
    count[shown ? "shown" : "omitted"]++;
    comparisons.set(block, count);
  }
  function compare(block, current, previous) {
    if (current == null) return null;
    const value = delta(current, previous);
    tally(block, value != null);
    return value;
  }
  function changeText(value) {
    return value === 0
      ? "Sem variação vs. anterior"
      : `${value > 0 ? "+" : "−"}${num(Math.abs(value))}% vs. anterior`;
  }
  function change(value, key, label) {
    const n = el("p", null, "change");
    if (value) {
      n.classList.add(value > 0 !== lowerIsBetter.has(key) ? "good" : "bad");
      n.append(icon(value > 0 ? "rise" : "fall"));
    }
    n.append((label ? label + ": " : "") + changeText(value));
    return n;
  }
  function updateCaption() {
    const period = [...loaded.values()][0]?.period;
    if (!period) return;
    let shown = 0,
      omitted = 0;
    for (const count of comparisons.values()) {
      shown += count.shown;
      omitted += count.omitted;
    }
    const current = `${dateBR(period.start)} a ${dateBR(period.end)}`,
      previous = `${dateBR(period.previous_start)} a ${dateBR(period.previous_end)}`;
    $("period-caption").textContent = shown
      ? `${current}, comparado com ${previous}.`
      : `${current}.`;
    $("comparison-note").hidden = !omitted;
    $("comparison-note").textContent = shown
      ? "Indicadores sem variação não têm valor no período anterior."
      : `Sem dados no período anterior (${previous}) para comparar.`;
  }
  function query() {
    const p = new URLSearchParams({
      account,
      start: $("start").value,
      end: $("end").value,
    });
    for (const [id, key] of [
      ["funnel-filter", "funnel_id"],
      ["assignee-filter", "assignee_id"],
      ["inbox-filter", "inbox_id"],
    ])
      if ($(id).value) p.set(key, $(id).value);
    return p;
  }
  async function api(path) {
    const r = await fetch("/kanban/" + path, {
      credentials: "same-origin",
    });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      throw new Error(j.detail || "Não foi possível carregar este bloco.");
    }
    return r.json();
  }
  function clearRestrictedData() {
    generation++;
    clearTimeout(debounce);
    for (const chart of charts.values()) chart.destroy();
    charts.clear();
    loaded.clear();
    comparisons.clear();
    for (const block of Object.keys(names)) $(block).replaceChildren();
  }
  function clearCharts(block) {
    for (const [id, chart] of charts)
      if (id.startsWith(block + ":")) {
        chart.destroy();
        charts.delete(id);
      }
  }
  function chart(block, target, labels, series, options = {}) {
    const { type = "bar", horizontal = true, titles } = options;
    const wrap = el("div", null, "chart-wrap"),
      canvas = el("canvas");
    canvas.setAttribute("role", "img");
    canvas.setAttribute(
      "aria-label",
      (titles || labels)
        .map(
          (label, i) =>
            label +
            ": " +
            series.map((s) => (s.data[i] == null ? "sem dados" : num(s.data[i]))).join(", "),
        )
        .join("; "),
    );
    wrap.append(canvas);
    target.append(wrap);
    const palette = ["blue-9", "teal-9", "amber-9", "ruby-9", "iris-9", "slate-9"];
    Chart.defaults.color = color("slate-11");
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    const datasets = series.map(({ colors, ...s }, i) => ({
      ...s,
      backgroundColor:
        colors ||
        (type === "doughnut"
          ? labels.map((_, j) => color(palette[j % palette.length]))
          : color(palette[i % palette.length])),
      borderColor: type === "doughnut" ? color("solid-2") : color(palette[i % palette.length]),
      borderWidth: type === "line" ? 2 : type === "doughnut" ? 2 : 0,
      // Linhas retas: a curva sugeria valores entre um dia e outro (UX-48).
      tension: 0,
      pointRadius: type === "line" ? 2 : 0,
      pointHoverRadius: 4,
      borderRadius: type === "bar" ? 4 : 0,
      maxBarThickness: 28,
    }));
    const axisTicks = { color: color("slate-11"), maxRotation: 0 };
    const instance = new Chart(canvas, {
      type,
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: horizontal ? "y" : "x",
        interaction: type === "line" ? { mode: "index", intersect: false } : undefined,
        animation: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? false
          : { duration: 250 },
        plugins: {
          legend: {
            display: series.length > 1 || type === "doughnut",
            align: "start",
            labels: {
              color: color("slate-11"),
              usePointStyle: true,
              pointStyle: "circle",
              boxWidth: 8,
              boxHeight: 8,
            },
          },
          tooltip: {
            backgroundColor: color("solid-2"),
            titleColor: color("slate-12"),
            bodyColor: color("slate-12"),
            borderColor: color("slate-6"),
            borderWidth: 1,
            callbacks: {
              title(items) {
                const i = items[0]?.dataIndex;
                return titles && i != null ? titles[i] : items[0]?.label;
              },
              label(context) {
                const s = context.dataset;
                const value = s.data[context.dataIndex];
                const text = `${s.label}: ${s.money ? money(value * 100) : num(value)}`;
                if (!s.previous) return text;
                const variation = delta(value, s.previous[context.dataIndex]);
                return variation == null ? text : [text, changeText(variation)];
              },
            },
          },
        },
        scales:
          type === "doughnut"
            ? {}
            : {
                x: {
                  beginAtZero: true,
                  grid: { color: color("slate-3"), display: horizontal },
                  ticks: horizontal
                    ? { ...axisTicks, precision: 0 }
                    : { ...axisTicks, autoSkip: true, autoSkipPadding: 16, maxTicksLimit: 8 },
                },
                y: {
                  beginAtZero: true,
                  grid: { color: color("slate-3"), display: !horizontal },
                  ticks: horizontal ? axisTicks : { ...axisTicks, precision: 0 },
                },
              },
      },
    });
    charts.set(block + ":" + charts.size, instance);
  }
  function panel(title, definition) {
    const n = el("div", null, "metric-panel"),
      h = el("h3", title);
    if (definition) h.append(help(definition, title));
    n.append(h);
    return n;
  }
  function empty(target, text = "Sem dados neste período.") {
    target.append(el("p", text, "chart-empty"));
  }
  function kpis(block, target, rows, result) {
    const grid = el("div", null, "kpi-grid");
    const { current, previous } = result;
    for (const [key, label, hint] of rows) {
      const n = el("article", null, "metric-kpi"),
        title = el("p", label, "kpi-label");
      title.append(help(key, label));
      n.append(title, el("p", format(key, current[key]), "kpi-value"));
      if (current[key] == null && hint) n.append(el("p", hint, "kpi-hint"));
      if (key === "win_rate") {
        // Tamanho da amostra: 20% com 3 fechamentos não vale o mesmo que com 300.
        const closed = (current.wins || 0) + (current.losses || 0);
        n.append(
          el(
            "p",
            `${current.wins || 0} de ${closed} ${closed === 1 ? "fechamento" : "fechamentos"}`,
            "kpi-secondary",
          ),
        );
      }
      if (key === "wins") {
        n.append(el("p", money(current.revenue || 0) + " em receita", "kpi-secondary"));
        // Uma linha por variação, cada uma com o seu rótulo (UX-41).
        for (const [field, name] of [
          ["wins", "Ganhos"],
          ["revenue", "Receita"],
        ]) {
          const value = compare(block, current[field], previous[field]);
          if (value != null) n.append(change(value, field, name));
        }
      } else {
        const value = compare(block, current[key], previous[key]);
        if (value != null) n.append(change(value, key));
      }
      grid.append(n);
    }
    target.append(grid);
  }
  function table(block, target, columns, rows, previous = [], key = (r) => r.id) {
    if (!rows.length) {
      empty(target);
      return;
    }
    const wrap = el("div", null, "table-wrap"),
      t = el("table", null, "metrics-table"),
      head = el("thead"),
      body = el("tbody"),
      tr = el("tr");
    // Variações calculadas uma vez; a ordenação só reorganiza as linhas.
    const variations = new Map(
      rows.map((row) => {
        const old = previous.find((p) => key(p) === key(row));
        return [
          row,
          Object.fromEntries(
            columns
              .filter(([, , numeric]) => numeric)
              .map(([field]) => [
                field,
                old
                  ? compare(block, row[field], old[field])
                  : (tally(block, false), null),
              ]),
          ),
        ];
      }),
    );
    let sorted = null;
    function fill(list) {
      body.replaceChildren();
      for (const row of list) {
        const line = el("tr");
        for (const [field, , numeric] of columns) {
          const cell = el("td");
          if (numeric) {
            cell.className = "numeric";
            cell.append(el("span", format(field, row[field]), "cell-value"));
            const value = variations.get(row)[field];
            if (value != null) cell.append(change(value, field));
          } else cell.textContent = row[field] ?? "Não informado";
          line.append(cell);
        }
        body.append(line);
      }
    }
    const headers = columns.map(([field, title, numeric]) => {
      const th = el("th"),
        b = el("button", null, "sort");
      th.scope = "col";
      if (numeric) th.className = "numeric";
      b.type = "button";
      b.append(el("span", title, "sort-label"));
      // A definição fica como dica no próprio cabeçalho (UX-45).
      if (definitions[field]) {
        b.title = definitions[field];
        b.classList.add("has-help");
      }
      b.onclick = () => {
        const dir = sorted?.field === field ? -sorted.dir : numeric ? -1 : 1;
        sorted = { field, dir };
        fill(
          [...rows].sort(
            (x, y) =>
              dir *
              (numeric
                ? Number(x[field] ?? -Infinity) - Number(y[field] ?? -Infinity) || 0
                : String(x[field] ?? "").localeCompare(String(y[field] ?? ""), "pt-BR")),
          ),
        );
        for (const [other, cell] of headers) {
          const button = cell.firstChild;
          button.querySelector(".sort-icon")?.remove();
          if (other === field) {
            cell.setAttribute("aria-sort", dir > 0 ? "ascending" : "descending");
            button.append(icon(dir > 0 ? "up" : "down", "icon sort-icon"));
          } else cell.removeAttribute("aria-sort");
        }
      };
      th.append(b);
      tr.append(th);
      return [field, th];
    });
    head.append(tr);
    t.append(head, body);
    wrap.append(t);
    target.append(wrap);
    fill(rows);
  }
  function openSettings() {
    parent.postMessage(
      { event: "kanban:open-page", account: Number(account), page: "configuracoes" },
      location.origin,
    );
  }
  function sourcesEmpty(target) {
    const box = el("div", null, "empty-state");
    const dimensions = configuration.dimensions || {};
    if (dimensions.source || dimensions.campaign) {
      box.append(
        el("h3", "Nenhuma origem ou campanha neste período"),
        el(
          "p",
          "As negociações do período não têm origem nem campanha preenchidas nos contatos do Chatwoot.",
        ),
      );
    } else {
      box.append(
        el("h3", "Origem e campanha não configuradas"),
        el(
          "p",
          administrator
            ? "Escolha, nas Configurações do Pipeline, os atributos de contato que guardam a origem e a campanha. Os valores preenchidos no Chatwoot passam a aparecer aqui."
            : "Um administrador da conta pode escolher, nas Configurações do Pipeline, os atributos de contato que guardam a origem e a campanha.",
        ),
      );
      if (administrator) {
        const action = el("button", "Abrir configurações", "primary");
        action.type = "button";
        action.onclick = openSettings;
        box.append(action);
      }
    }
    target.append(box);
  }
  function render(block, result) {
    clearCharts(block);
    comparisons.delete(block);
    const section = $(block);
    section.replaceChildren();
    section.setAttribute("aria-busy", "false");
    const heading = el("div", null, "block-heading"),
      exportButton = el("a", null, "metric-action");
    exportButton.href = "/kanban/metrics/" + block + "?" + query() + "&format=csv";
    exportButton.download = "metricas-" + block + ".csv";
    exportButton.setAttribute("aria-label", `Exportar CSV de ${names[block]}`);
    exportButton.append(icon("download"), "Exportar CSV");
    heading.append(el("h2", names[block]), exportButton);
    section.append(heading);
    const body = el("div", null, "block-body");
    section.append(body);
    const c = result.current,
      p = result.previous;
    if (block === "summary")
      kpis(
        block,
        body,
        [
          ["leads", "Leads novos"],
          ["ongoing", "Em andamento"],
          ["wins", "Ganhos e receita"],
          ["losses", "Perdidos"],
          ["win_rate", "Taxa de ganho"],
          ["average_ticket", "Ticket médio", "Nenhum ganho no período."],
          ["open_value", "Valor em aberto"],
          ["forecast", "Previsão de receita"],
          ["cycle_days", "Ciclo médio", "Nenhum ganho no período."],
        ],
        result,
      );
    if (block === "funnel") {
      // Nome do funil só quando o recorte mistura funis (UX-47).
      const several = new Set(c.rows.map((r) => r.funnel_id)).size > 1;
      const label = (r) => (several ? r.funnel + " · " : "") + r.name;
      const columns = el("div", null, "metric-columns"),
        distribution = panel("Entradas por etapa"),
        dwell = panel("Tempo médio na etapa", "dwell_days");
      columns.append(distribution, dwell);
      const flow = panel("Passagem entre etapas", "flow");
      body.append(flow);
      if (several)
        empty(flow, "Escolha um funil para ver a passagem entre as etapas.");
      else if (!c.flow.length || !c.flow[0].reached)
        empty(flow, "Nenhum lead novo neste período.");
      else {
        // Cada barra mostra quantos chegaram e quanto passou da etapa anterior.
        const titles = c.flow.map((step, i) => {
          const before = i ? c.flow[i - 1].reached : null;
          const share = before ? Math.round((100 * step.reached) / before) : null;
          return share == null ? step.name : `${step.name} · ${share}% da anterior`;
        });
        chart(
          block,
          flow,
          titles,
          [
            {
              label: "Leads",
              data: c.flow.map((step) => step.reached),
              colors: c.flow.map((step) =>
                step.kind === "won" ? color("teal-9") : step.color || color("blue-9"),
              ),
            },
          ],
          { titles },
        );
      }
      body.append(columns);
      const colors = c.rows.map(stageColor);
      if (c.rows.some((r) => r.quantity)) {
        chart(block, distribution, c.rows.map(label), [
          { label: "Negociações", data: c.rows.map((r) => r.quantity), colors },
        ]);
        const drop = c.rows
          .filter(
            (r) =>
              r.kind === "open" &&
              r.quantity > 0 &&
              c.rows.some(
                (n) =>
                  n.funnel_id === r.funnel_id &&
                  Number(n.position) > Number(r.position),
              ),
          )
          .sort((a, b) => a.next_conversion - b.next_conversion)[0];
        if (drop)
          distribution.append(
            el(
              "p",
              `Maior queda: ${label(drop)}. ${num(100 - drop.next_conversion)}% das negociações não avançaram para a etapa seguinte.`,
              "drop-note",
            ),
          );
      } else empty(distribution);
      if (c.rows.some((r) => r.dwell_days != null)) {
        // Unidade que deixa os valores legíveis: minutos, horas ou dias.
        const longest = Math.max(...c.rows.map((r) => Number(r.dwell_days) || 0));
        const [unit, factor] =
          longest < 1 / 24 ? ["Minutos", 1440] : longest < 1 ? ["Horas", 24] : ["Dias", 1];
        chart(block, dwell, c.rows.map(label), [
          {
            label: unit,
            data: c.rows.map((r) =>
              r.dwell_days == null ? null : Number(r.dwell_days) * factor,
            ),
            colors,
          },
        ]);
      }
      else empty(dwell, "Nenhuma negociação saiu de uma etapa neste período.");
      table(
        block,
        body,
        [
          ...(several ? [["funnel", "Funil"]] : []),
          ["name", "Etapa"],
          ["quantity", "Entradas", true],
          ["value", "Valor", true],
          ["conversion", "Etapa posterior", true],
          ["next_conversion", "Etapa seguinte", true],
          ["loss_rate", "Perda", true],
          ["win_probability", "Chance de ganho", true],
          ["dwell_days", "Permanência", true],
        ],
        c.rows,
        p.rows,
      );
      const stale = panel("Negociações paradas", "stale");
      if (!c.stale.length) empty(stale, "Nenhuma negociação parada neste recorte.");
      for (const row of c.stale) {
        const line = el("p", null, "stale-row"),
          link = el("button", row.name, "metric-link");
        link.type = "button";
        link.onclick = () =>
          parent.postMessage(
            { event: "kanban:open-card", account: Number(account), id: row.id },
            location.origin,
          );
        line.append(
          link,
          el(
            "span",
            `${num(row.idle_days)} dias sem atividade (limite: ${row.stale_days})`,
            "muted",
          ),
        );
        stale.append(line);
      }
      body.append(stale);
    }
    if (block === "losses") {
      const box = panel("Motivos e etapa de saída");
      body.append(box);
      if (c.rows.length)
        chart(
          block,
          box,
          c.rows.map((r) => r.reason + " · " + r.from_stage),
          [{ label: "Perdas", data: c.rows.map((r) => r.quantity) }],
        );
      else empty(box, "Nenhuma perda registrada neste período.");
      table(
        block,
        body,
        [
          ["reason", "Motivo"],
          ["from_stage", "Etapa de saída"],
          ["quantity", "Perdas", true],
          ["value", "Valor", true],
        ],
        c.rows,
        p.rows,
        (r) => r.reason + "|" + r.from_stage,
      );
    }
    if (block === "sources") {
      const unknown = !c.rows.some(
        (r) => r.source !== "Não informada" || r.campaign !== "Não informada",
      );
      // Um único estado vazio em vez de tabelas só com "Não informada" (UX-46).
      if (unknown) {
        exportButton.hidden = true;
        sourcesEmpty(body);
      } else
        for (const [dimension, field, title] of [
          ["origins", "source", "Por origem"],
          ["campaigns", "campaign", "Por campanha"],
        ]) {
          const box = panel(title);
          body.append(box);
          // Dimensão sem atributo mapeado: avisar em vez de listar "Não informada".
          if (!(configuration.dimensions || {})[field]) {
            const hint = el("div", null, "empty-state");
            hint.append(
              el(
                "p",
                `${field === "source" ? "Origem" : "Campanha"} não configurada. ` +
                  (administrator
                    ? "Escolha o atributo do contato nas Configurações do Pipeline."
                    : "Um administrador pode escolher o atributo nas Configurações do Pipeline."),
              ),
            );
            if (administrator) {
              const action = el("button", "Abrir configurações");
              action.type = "button";
              action.onclick = openSettings;
              hint.append(action);
            }
            box.append(hint);
            continue;
          }
          table(
            block,
            box,
            [
              [field, field === "source" ? "Origem" : "Campanha"],
              ["leads", "Leads", true],
              ["wins", "Ganhos", true],
              ["win_rate", "Taxa de ganho", true],
              ["revenue", "Receita", true],
            ],
            c[dimension],
            p[dimension],
            (r) => r[field],
          );
        }
    }
    if (block === "team")
      table(
        block,
        body,
        [
          ["name", "Responsável"],
          ["leads", "Leads", true],
          ["wins", "Ganhos", true],
          ["win_rate", "Taxa de ganho", true],
          ["revenue", "Receita", true],
          ["overdue_tasks", "Tarefas vencidas", true],
        ],
        c.rows,
        p.rows,
        (r) => r.assignee_id,
      );
    if (block === "tasks")
      kpis(
        block,
        body,
        [
          ["open", "Abertas"],
          ["overdue", "Vencidas"],
          ["on_time_rate", "Concluídas no prazo", "Nenhuma tarefa concluída no período."],
          ["completed", "Concluídas"],
        ],
        result,
      );
    if (block === "timeline") {
      const box = panel("Leads novos e ganhos por dia");
      body.append(box);
      if (c.rows.some((r) => r.leads || r.wins))
        chart(
          block,
          box,
          c.rows.map((r) => dateBR(r.date).slice(0, 5)),
          [
            {
              label: "Leads novos",
              data: c.rows.map((r) => r.leads),
              previous: p.rows.map((r) => r.leads),
            },
            {
              label: "Ganhos",
              data: c.rows.map((r) => r.wins),
              previous: p.rows.map((r) => r.wins),
            },
          ],
          { type: "line", horizontal: false, titles: c.rows.map((r) => dateBR(r.date)) },
        );
      else empty(box);
      // Dinheiro no tempo: por mês quando o período passa de dois meses.
      const money_box = panel("Receita e perdas");
      body.append(money_box);
      if (c.rows.some((r) => r.revenue || r.lost_value)) {
        const monthly = c.rows.length > 62;
        const groups = new Map();
        for (const r of c.rows) {
          const key = monthly ? r.date.slice(0, 7) : r.date;
          const g = groups.get(key) || { revenue: 0, lost: 0 };
          g.revenue += Number(r.revenue) || 0;
          g.lost += Number(r.lost_value) || 0;
          groups.set(key, g);
        }
        const keys = [...groups.keys()];
        const label = (k) =>
          monthly ? `${k.slice(5, 7)}/${k.slice(0, 4)}` : dateBR(k).slice(0, 5);
        chart(
          block,
          money_box,
          keys.map(label),
          [
            {
              label: "Receita",
              money: true,
              data: keys.map((k) => groups.get(k).revenue / 100),
              colors: color("teal-9"),
            },
            {
              label: "Perdas",
              money: true,
              data: keys.map((k) => groups.get(k).lost / 100),
              colors: color("ruby-9"),
            },
          ],
          { horizontal: false, titles: keys.map((k) => (monthly ? label(k) : dateBR(k))) },
        );
      } else empty(money_box, "Nenhum ganho ou perda com valor neste período.");
      if (configuration.temperature) {
        const temperatures = panel("Temperatura");
        body.append(temperatures);
        if (c.temperature.length)
          chart(
            block,
            temperatures,
            c.temperature.map((r) => r.name),
            [
              {
                label: "Negociações",
                data: c.temperature.map((r) => r.quantity),
                previous: c.temperature.map(
                  (r) => p.temperature.find((old) => old.name === r.name)?.quantity || 0,
                ),
              },
            ],
            { type: "doughnut", horizontal: false },
          );
        else empty(temperatures);
      }
    }
    if (c.warning) body.append(el("p", c.warning, "metric-note"));
    updateCaption();
  }
  function day(d) {
    return d.toISOString().slice(0, 10);
  }
  function preset() {
    const today = new Date(
      new Date().toLocaleDateString("sv-SE", {
        timeZone: "America/Sao_Paulo",
      }) + "T12:00:00Z",
    );
    let a = new Date(today),
      b = new Date(today);
    switch ($("period").value) {
      case "yesterday":
        a.setUTCDate(a.getUTCDate() - 1);
        b = new Date(a);
        break;
      case "7days":
        a.setUTCDate(a.getUTCDate() - 6);
        break;
      case "month":
        a.setUTCDate(1);
        break;
      case "last-month":
        a.setUTCDate(1);
        a.setUTCMonth(a.getUTCMonth() - 1);
        b = new Date(today);
        b.setUTCDate(0);
        break;
      case "custom":
        break;
    }
    if ($("period").value !== "custom") {
      $("start").value = day(a);
      $("end").value = day(b);
    }
    $("custom-range").hidden = $("period").value !== "custom";
  }
  async function load() {
    if (!$("filters").reportValidity()) return;
    if ($("start").value > $("end").value) {
      $("filter-warning").hidden = false;
      $("filter-warning").textContent = "O início deve ser anterior ao fim.";
      return;
    }
    $("filter-warning").hidden = true;
    loaded.clear();
    comparisons.clear();
    const id = ++generation,
      p = query();
    p.set("period", $("period").value);
    history.replaceState(null, "", location.pathname + "?" + p);
    $("metrics-status").textContent = "Atualizando…";
    $("refresh").setAttribute("aria-busy", "true");
    for (const block of Object.keys(names)) {
      clearCharts(block);
      $(block).setAttribute("aria-busy", "true");
      $(block).replaceChildren(el("h2", names[block]), el("div", null, "skeleton"));
    }
    let errors = 0;
    await Promise.all(
      Object.keys(names).map(async (block) => {
        try {
          const result = await api("metrics/" + block + "?" + p);
          if (id !== generation) return;
          loaded.set(block, result);
          render(block, result);
        } catch (error) {
          if (id !== generation) return;
          errors++;
          $(block).setAttribute("aria-busy", "false");
          const retry = el("button", "Tentar novamente", "header-button faded");
          retry.type = "button";
          retry.onclick = load;
          $(block).replaceChildren(
            el("h2", names[block]),
            el("p", error.message, "metrics-error"),
            retry,
          );
        }
      }),
    );
    if (id !== generation) return;
    $("refresh").removeAttribute("aria-busy");
    $("metrics-status").textContent = errors
      ? "Alguns blocos não carregaram"
      : "Atualizado às " +
        new Date().toLocaleTimeString("pt-BR", {
          hour: "2-digit",
          minute: "2-digit",
        });
  }
  async function init() {
    const [options, session] = await Promise.all([
      api("metrics/options?account=" + encodeURIComponent(account)),
      api("session?account=" + encodeURIComponent(account)).catch(() => ({})),
    ]);
    configuration = options;
    administrator = session.role === "administrator";
    for (const [id, rows] of [
      ["funnel-filter", configuration.funnels],
      ["assignee-filter", configuration.agents],
      ["inbox-filter", configuration.inboxes],
    ])
      for (const row of rows || []) $(id).append(new Option(row.name, row.id));
    for (const [id, key] of [
      ["funnel-filter", "funnel_id"],
      ["assignee-filter", "assignee_id"],
      ["inbox-filter", "inbox_id"],
      ["period", "period"],
      ["start", "start"],
      ["end", "end"],
    ])
      if (url.searchParams.has(key)) $(id).value = url.searchParams.get(key);
    if (!$("period").value) $("period").value = "custom";
    preset();
    if (!$("start").value || !$("end").value) {
      $("period").value = "month";
      preset();
    }
    // Menus no padrão DropdownMenu (UX-40), criados depois dos valores iniciais
    // para o gatilho já mostrar a escolha vinda da URL.
    filterMenu($("funnel-filter"), "Todos os funis", "Nenhum funil nesta conta.");
    filterMenu($("period"), "", "");
    filterMenu(
      $("assignee-filter"),
      "Todos os responsáveis",
      "Nenhum agente disponível nesta conta.",
    );
    filterMenu(
      $("inbox-filter"),
      "Todas as caixas de entrada",
      "Nenhuma caixa de entrada disponível.",
    );
    // O período sempre tem valor: o gatilho fica neutro, como um seletor de datas.
    $("period").parentElement.classList.add("fixed");
    $("filters").classList.add("ready");
    await load();
    source = new EventSource("/kanban/events?account=" + encodeURIComponent(account));
    let connected = false;
    source.addEventListener("ready", () => {
      if (connected) load();
      connected = true;
    });
    source.addEventListener("change", () => {
      clearRestrictedData();
      debounce = setTimeout(load, 500);
    });
    source.addEventListener("unavailable", () => {
      clearRestrictedData();
      $("metrics-status").textContent = "Chatwoot indisponível";
    });
    source.addEventListener("expired", () => {
      source.close();
      clearRestrictedData();
      $("metrics-status").textContent = "Sessão expirada";
    });
  }
  $("period").addEventListener("change", () => {
    preset();
    load();
  });
  for (const id of ["funnel-filter", "assignee-filter", "inbox-filter", "start", "end"])
    $(id).addEventListener("change", load);
  $("filters").onsubmit = (e) => e.preventDefault();
  $("refresh").onclick = load;
  const theme = new MutationObserver(() => {
    for (const [block, result] of loaded)
      if ($(block).getAttribute("aria-busy") !== "true") render(block, result);
  });
  theme.observe(document.body, {
    attributes: true,
    attributeFilter: ["class"],
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") parent.postMessage({ event: "kanban:close" }, location.origin);
  });
  window.addEventListener("pagehide", () => {
    source?.close();
    theme.disconnect();
    clearTimeout(debounce);
    for (const c of charts.values()) c.destroy();
  });
  init().catch((error) => {
    $("filters").classList.add("ready");
    $("filter-warning").hidden = false;
    $("filter-warning").textContent = error.message;
  });
})();
