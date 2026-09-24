(() => {
  const $ = (id) => document.getElementById(id),
    { money, dateBR } = window.KanbanHelpers;
  const url = new URL(location.href),
    account = url.searchParams.get("account");
  const names = {
    summary: "Resumo",
    funnel: "Funil",
    losses: "Motivos de perda",
    sources: "Origem",
    team: "Equipe",
    tasks: "Tarefas",
    timeline: "Evolução",
  };
  const definitions = {
    leads: "Lead novo: card criado no período.",
    ongoing: "Em andamento: cards em etapas kind=open no fim do período.",
    wins: "Ganho: card que entrou numa etapa kind=won no período.",
    revenue:
      "Receita: soma do valor dos ganhos no momento de entrada na etapa ganha.",
    losses: "Perdido: card que entrou numa etapa kind=lost no período.",
    win_rate: "Taxa de ganho: ganhos / (ganhos + perdidos) do período.",
    average_ticket:
      "Ticket médio: soma do valor dos ganhos / número de ganhos.",
    open_value: "Valor em aberto: soma do valor dos cards em andamento.",
    cycle_days:
      "Ciclo médio: média de (data do ganho - data de criação) dos ganhos do período.",
    conversion:
      "Dos cards que entraram na etapa X no período, percentual que depois entrou em qualquer etapa posterior do mesmo funil, observado até agora.",
    next_conversion:
      "Dos cards que entraram nesta etapa no período, percentual que depois entrou na próxima etapa.",
    dwell_days:
      "Tempo médio na etapa: média da permanência encerrada no período, calculada pelos eventos de movimento.",
    stale:
      "Card parado: sem movimento nem tarefa concluída há mais de N dias, configurado por funil (padrão 7).",
    service_open:
      "Conversas abertas agora no Chatwoot, com cache de até 5 minutos.",
    unanswered:
      "Conversas abertas aguardando resposta ou sem primeira resposta.",
    open: "Tarefas abertas no fim do período.",
    overdue:
      "Tarefas abertas que já passaram da data de vencimento, em Brasília.",
    on_time_rate:
      "Tarefas concluídas no prazo / tarefas concluídas no período.",
    completed: "Tarefas concluídas no período.",
    conversations: "Conversas criadas no período no Chatwoot.",
    first_response_seconds:
      "Média dos tempos de primeira resposta nos eventos do Chatwoot no período.",
    resolution_seconds:
      "Média dos tempos de resolução nos eventos do Chatwoot no período.",
  };
  const charts = new Map(),
    loaded = new Map();
  let generation = 0,
    configuration = {},
    source,
    debounce;
  const el = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text != null) n.textContent = String(text);
    if (cls) n.className = cls;
    return n;
  };
  const num = (n) =>
    n == null
      ? "sem dados"
      : Number(n).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  const pct = (n) => (n == null ? "sem dados" : num(n) + "%");
  const format = (key, value) =>
    value == null
      ? "sem dados"
      : ["revenue", "average_ticket", "open_value", "value"].includes(key)
        ? money(value)
        : [
              "win_rate",
              "on_time_rate",
              "conversion",
              "next_conversion",
            ].includes(key)
          ? pct(value)
          : key.endsWith("_days")
            ? Number(value) > 0 && Number(value) < 1
              ? num(Number(value) * 1440) + " min"
              : num(value) + " dias"
            : key.endsWith("_seconds")
              ? num(Number(value) / 60) + " min"
              : num(value);
  const color = (token) =>
    `rgb(${getComputedStyle(document.documentElement)
      .getPropertyValue("--" + token)
      .trim()})`;
  function tooltip(key) {
    const b = el("button", "?", "definition");
    b.type = "button";
    b.title = definitions[key] || key;
    b.setAttribute("aria-label", b.title);
    return b;
  }
  function delta(current, previous) {
    return current == null || previous == null
      ? null
      : previous === 0
        ? current === 0
          ? 0
          : null
        : ((current - previous) / Math.abs(previous)) * 100;
  }
  function variation(value, lower = false) {
    const n = el(
      "span",
      value == null
        ? "sem dados no período anterior"
        : `${value > 0 ? "↑" : value < 0 ? "↓" : "→"} ${num(Math.abs(value))}% vs. anterior`,
      "change",
    );
    if (value) n.classList.add(value > 0 !== lower ? "good" : "bad");
    return n;
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
    const r = await fetch("/kanban/metrics/" + path, {
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
    for (const block of Object.keys(names)) $(block).replaceChildren();
  }
  function clearCharts(block) {
    for (const [id, chart] of charts)
      if (id.startsWith(block + ":")) {
        chart.destroy();
        charts.delete(id);
      }
  }
  function chart(
    block,
    target,
    labels,
    series,
    type = "bar",
    horizontal = true,
  ) {
    const wrap = el("div", null, "chart-wrap"),
      canvas = el("canvas");
    canvas.setAttribute("role", "img");
    canvas.setAttribute(
      "aria-label",
      labels
        .map(
          (label, i) =>
            label + ": " + series.map((s) => num(s.data[i])).join(", "),
        )
        .join("; "),
    );
    wrap.append(canvas);
    target.append(wrap);
    const palette = [
      "blue-9",
      "teal-9",
      "amber-9",
      "ruby-9",
      "iris-9",
      "slate-9",
    ];
    Chart.defaults.color = color("slate-11");
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    const datasets = series.map((s, i) => ({
      ...s,
      backgroundColor:
        type === "doughnut"
          ? labels.map((_, j) => color(palette[j % palette.length]))
          : color(palette[i % palette.length]),
      borderColor: color(palette[i % palette.length]),
      borderWidth: type === "line" ? 2 : 0,
      pointRadius: 3,
      tension: 0.25,
      borderRadius: type === "bar" ? 4 : 0,
    }));
    const instance = new Chart(canvas, {
      type,
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: horizontal ? "y" : "x",
        animation: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? false
          : { duration: 250 },
        plugins: {
          legend: {
            display: series.length > 1 || type === "doughnut",
            labels: { color: color("slate-11") },
          },
          tooltip: {
            backgroundColor: color("solid-2"),
            titleColor: color("slate-12"),
            bodyColor: color("slate-12"),
            borderColor: color("slate-6"),
            borderWidth: 1,
            callbacks: {
              label(context) {
                const series = context.dataset;
                const value = series.data[context.dataIndex];
                const text = `${series.label}: ${num(value)}`;
                if (!series.previous) return text;
                const change = delta(value, series.previous[context.dataIndex]);
                return [text, variation(change).textContent];
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
                  grid: { color: color("slate-3") },
                  ticks: { color: color("slate-11") },
                },
                y: {
                  beginAtZero: true,
                  grid: { display: false },
                  ticks: { color: color("slate-11") },
                },
              },
      },
    });
    charts.set(block + ":" + charts.size, instance);
  }
  function panel(title) {
    const n = el("div", null, "metric-panel");
    n.append(el("h3", title));
    return n;
  }
  function empty(target, text = "Sem dados neste período.") {
    target.append(el("div", text, "chart-empty"));
  }
  function kpis(target, rows, result) {
    const grid = el("div", null, "kpi-grid");
    for (const [key, label, lower, definition] of rows) {
      const n = el("article", null, "metric-kpi"),
        title = el("p", label, "kpi-label");
      title.append(tooltip(definition || key));
      n.append(title, el("p", format(key, result.current[key]), "kpi-value"));
      if (key === "wins") {
        n.append(
          el(
            "p",
            money(result.current.revenue || 0) + " em receita",
            "kpi-secondary",
          ),
          Object.assign(variation(result.variation.revenue), {
            textContent:
              "Receita: " + variation(result.variation.revenue).textContent,
          }),
        );
      }
      const change = variation(result.variation[key], lower);
      if (key === "wins") change.prepend("Ganhos: ");
      n.append(change);
      grid.append(n);
    }
    target.append(grid);
  }
  function table(target, columns, rows, previous = [], key = (r) => r.id) {
    if (!rows.length) {
      empty(target);
      return;
    }
    const wrap = el("div", null, "table-wrap"),
      t = el("table", null, "metrics-table"),
      head = el("thead"),
      body = el("tbody");
    let order = 1;
    const tr = el("tr");
    function fill(list) {
      body.replaceChildren();
      for (const row of list) {
        const line = el("tr");
        const old = previous.find((p) => key(p) === key(row));
        for (const [field, title, numeric] of columns) {
          const cell = el("td");
          if (numeric) {
            cell.append(
              el("div", format(field, row[field])),
              variation(
                delta(row[field], old?.[field] ?? 0),
                field.includes("days") ||
                  field.includes("overdue") ||
                  field.includes("seconds") ||
                  field === "losses",
              ),
            );
          } else cell.textContent = row[field] ?? "Não informado";
          line.append(cell);
        }
        body.append(line);
      }
    }
    for (const [field, title, numeric] of columns) {
      const th = el("th"),
        b = el("button", title + " ↕");
      b.type = "button";
      b.onclick = () => {
        order *= -1;
        fill(
          [...rows].sort(
            (a, b) =>
              order *
              (numeric
                ? Number(a[field] || 0) - Number(b[field] || 0)
                : String(a[field] || "").localeCompare(
                    String(b[field] || ""),
                    "pt-BR",
                  )),
          ),
        );
      };
      th.append(b);
      if (definitions[field]) th.append(tooltip(field));
      tr.append(th);
    }
    head.append(tr);
    t.append(head, body);
    wrap.append(t);
    target.append(wrap);
    fill(rows);
  }
  function render(block, result) {
    clearCharts(block);
    const section = $(block);
    section.replaceChildren();
    section.setAttribute("aria-busy", "false");
    const heading = el("div", null, "block-heading"),
      exportButton = el("a", "Exportar CSV", "export metric-link");
    exportButton.href =
      "/kanban/metrics/" + block + "?" + query() + "&format=csv";
    exportButton.download = "metricas-" + block + ".csv";
    heading.append(el("h2", names[block]), exportButton);
    section.append(heading);
    const body = el("div", null, "block-body");
    section.append(body);
    const c = result.current,
      p = result.previous;
    if (block === "summary")
      kpis(
        body,
        [
          ["leads", "Leads novos"],
          ["ongoing", "Em andamento"],
          ["wins", "Ganhos + receita"],
          ["losses", "Perdidos", true],
          ["win_rate", "Taxa de ganho"],
          ["average_ticket", "Ticket médio"],
          ["open_value", "Valor em aberto"],
          ["cycle_days", "Ciclo médio", true],
        ],
        result,
      );
    if (block === "funnel") {
      const columns = el("div", null, "metric-columns"),
        distribution = panel("Entradas por etapa"),
        dwell = panel("Tempo médio na etapa · dias");
      columns.append(distribution, dwell);
      body.append(columns);
      const label = (r) =>
        ($("funnel-filter").value ? "" : r.funnel + " · ") + r.name;
      if (c.rows.some((r) => r.quantity)) {
        chart(block, distribution, c.rows.map(label), [
          { label: "Negociações", data: c.rows.map((r) => r.quantity) },
        ]);
        const eligible = c.rows.filter(
          (r, i) =>
            r.quantity > 0 &&
            c.rows.some(
              (n) =>
                n.funnel_id === r.funnel_id &&
                Number(n.position) > Number(r.position),
            ),
        );
        const drop = eligible.sort(
          (a, b) => a.next_conversion - b.next_conversion,
        )[0];
        if (drop)
          distribution.append(
            el(
              "p",
              `Maior queda: ${label(drop)} · ${num(100 - drop.next_conversion)}% não avançaram para a próxima etapa.`,
              "drop-note",
            ),
          );
      } else empty(distribution);
      if (c.rows.some((r) => r.dwell_days != null))
        chart(block, dwell, c.rows.map(label), [
          { label: "Dias", data: c.rows.map((r) => r.dwell_days) },
        ]);
      else empty(dwell, "Sem permanências encerradas no período.");
      table(
        body,
        [
          ["name", "Etapa"],
          ["quantity", "Quantidade", true],
          ["value", "Valor", true],
          ["conversion", "Etapa posterior", true],
          ["next_conversion", "Próxima etapa", true],
          ["dwell_days", "Permanência", true],
        ],
        c.rows,
        p.rows,
      );
      const stale = panel("Negociações paradas");
      stale.append(tooltip("stale"));
      if (!c.stale.length)
        empty(stale, "Nenhuma negociação parada neste recorte.");
      for (const row of c.stale) {
        const line = el("p"),
          link = el("button", row.name, "metric-link");
        link.onclick = () =>
          parent.postMessage(
            { event: "kanban:open-card", account: Number(account), id: row.id },
            location.origin,
          );
        line.append(
          link,
          el(
            "span",
            ` · ${num(row.idle_days)} dias sem atividade (limite: ${row.stale_days})`,
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
      if (
        !c.rows.length ||
        c.rows.every(
          (r) => r.source === "Não informada" && r.campaign === "Não informada",
        )
      )
        body.append(
          el(
            "p",
            "Configure os atributos de origem e campanha na configuração da conta do Kanban e preencha os campos correspondentes no Chatwoot. Os valores serão copiados para as negociações e atualizados por webhook ou reconciliação.",
            "chart-empty",
          ),
        );
      for (const [dimension, field, title] of [
        ["origins", "source", "Por origem"],
        ["campaigns", "campaign", "Por campanha"],
      ]) {
        const box = panel(title);
        body.append(box);
        table(
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
    if (block === "service") {
      kpis(
        body,
        [
          ["conversations", "Conversas"],
          ["open", "Abertas agora", false, "service_open"],
          ["unanswered", "Sem resposta agora", true],
          ["resolution_seconds", "Resolução", true],
        ],
        result,
      );
      body.append(el("p", c.live_note, "metric-note"));
      const box = panel("Conversas por caixa de entrada");
      body.append(box);
      if (c.inboxes.length)
        chart(
          block,
          box,
          c.inboxes.map((r) => r.name),
          [{ label: "Conversas", data: c.inboxes.map((r) => r.quantity) }],
        );
      else empty(box);
      table(
        box,
        [
          ["name", "Caixa de entrada"],
          ["quantity", "Conversas", true],
        ],
        c.inboxes,
        p.inboxes,
        (r) => r.inbox_id,
      );
      if (c.longest_wait) {
        const link = el(
          "button",
          `Maior espera atual: ${format("wait_seconds", c.longest_wait.seconds)} · abrir conversa #${c.longest_wait.id}`,
          "metric-link",
        );
        link.onclick = () =>
          parent.postMessage(
            {
              event: "kanban:navigate",
              account: Number(account),
              resource: "conversations",
              id: c.longest_wait.id,
            },
            location.origin,
          );
        body.append(link);
      } else
        body.append(
          el(
            "p",
            "Nenhuma conversa aberta aguardando resposta.",
            "metric-note",
          ),
        );
    }
    if (block === "team")
      table(
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
        body,
        [
          ["open", "Abertas"],
          ["overdue", "Vencidas", true],
          ["on_time_rate", "Concluídas no prazo"],
          ["completed", "Concluídas"],
        ],
        result,
      );
    if (block === "timeline") {
      const box = panel("Leads novos × ganhos por dia");
      body.append(box);
      if (c.rows.some((r) => r.leads || r.wins))
        chart(
          block,
          box,
          c.rows.map((r) => dateBR(r.date)),
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
          "line",
          false,
        );
      else empty(box);
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
                  (r) =>
                    p.temperature.find((old) => old.name === r.name)
                      ?.quantity || 0,
                ),
              },
            ],
            "doughnut",
            false,
          );
        else empty(temperatures);
      }
    }
    if (c.warning) body.append(el("p", c.warning, "metric-note"));
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
    for (const id of ["start-label", "end-label"])
      $(id).hidden = $("period").value !== "custom";
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
    const id = ++generation,
      p = query();
    p.set("period", $("period").value);
    history.replaceState(null, "", location.pathname + "?" + p);
    $("metrics-status").textContent = "Atualizando…";
    for (const block of Object.keys(names)) {
      clearCharts(block);
      $(block).setAttribute("aria-busy", "true");
      $(block).replaceChildren(
        el("h2", names[block]),
        el("div", null, "skeleton"),
      );
    }
    let errors = 0;
    await Promise.all(
      Object.keys(names).map(async (block) => {
        try {
          const result = await api(block + "?" + p);
          if (id !== generation) return;
          loaded.set(block, result);
          render(block, result);
          $("period-caption").textContent =
            `${dateBR(result.period.start)} a ${dateBR(result.period.end)} · comparação: ${dateBR(result.period.previous_start)} a ${dateBR(result.period.previous_end)} · Brasília`;
        } catch (error) {
          if (id !== generation) return;
          errors++;
          $(block).setAttribute("aria-busy", "false");
          const retry = el("button", "Tentar novamente");
          retry.onclick = load;
          $(block).replaceChildren(
            el("h2", names[block]),
            el("p", error.message, "metrics-error"),
            retry,
          );
        }
      }),
    );
    if (id === generation)
      $("metrics-status").textContent = errors
        ? "Alguns blocos não carregaram"
        : "Atualizado às " +
          new Date().toLocaleTimeString("pt-BR", {
            hour: "2-digit",
            minute: "2-digit",
          });
  }
  async function init() {
    configuration = await api("options?account=" + encodeURIComponent(account));
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
    await load();
    source = new EventSource(
      "/kanban/events?account=" + encodeURIComponent(account),
    );
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
  $("period").onchange = () => {
    preset();
    load();
  };
  for (const id of [
    "funnel-filter",
    "assignee-filter",
    "inbox-filter",
    "start",
    "end",
  ])
    $(id).onchange = load;
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
    if (e.key === "Escape")
      parent.postMessage({ event: "kanban:close" }, location.origin);
  });
  window.addEventListener("pagehide", () => {
    source?.close();
    theme.disconnect();
    clearTimeout(debounce);
    for (const c of charts.values()) c.destroy();
  });
  init().catch((error) => {
    $("filter-warning").hidden = false;
    $("filter-warning").textContent = error.message;
  });
})();
