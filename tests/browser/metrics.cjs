// Página Métricas (UX-40 a UX-51) com rotas simuladas por dados reais da base demo.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const http = require("node:http");
(async () => {
  const fixtures = JSON.parse(await fs.readFile(path.join(__dirname, "fixtures/metricas.json"), "utf8"));
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, "http://localhost");
    const file = url.pathname === "/kanban/metricas" ? "templates/metricas.html" :
      url.pathname.startsWith("/kanban/static/") ? url.pathname.slice(8) : null;
    if (!file || file.includes("..")) { res.writeHead(404).end(); return; }
    try {
      const bytes = await fs.readFile(path.join(__dirname, "../../app", file));
      res.setHeader("Content-Type", file.endsWith(".js") ? "text/javascript" : file.endsWith(".css") ? "text/css" : "text/html");
      res.end(bytes);
    } catch { res.writeHead(404).end(); }
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 900}});
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    await page.addInitScript(() => {
      window.messages = [];
      window.addEventListener("message", (e) => window.messages.push(e.data));
      window.EventSource = class extends EventTarget { close() {} };
    });
    let data = fixtures.month, role = "administrator";
    const requests = [];
    await page.route("**/kanban/session?*", route => route.fulfill({json: {role, activation: {enabled: true, activation_status: "ready"}}}));
    await page.route("**/kanban/metrics/**", route => {
      const url = new URL(route.request().url());
      const block = url.pathname.split("/").pop();
      requests.push({block, ...Object.fromEntries(url.searchParams)});
      return route.fulfill({json: data[block]});
    });
    const open = async () => {
      requests.length = 0;
      await page.goto(`${origin}/kanban/metricas?account=2`);
      await page.locator("#timeline[aria-busy=false]").waitFor();
      await page.locator("#summary[aria-busy=false]").waitFor();
    };
    const kpi = (label) => page.locator(".metric-kpi", {has: page.locator(".kpi-label", {hasText: label})});
    const trigger = (name) => page.locator("#filters").getByRole("button", {name, exact: true});
    const option = (name) => page.getByRole("option", {name, exact: true});
    await open();

    // UX-49: só o título e "Atualizar" com ícone; UX-51: nota de atendimento no rodapé.
    assert.equal(await page.locator(".header-context").count(), 0);
    assert.equal(await page.locator("header.page-header").innerText().then(t => t.replace(/\s+/g, " ").trim()).then(t => t.startsWith("Métricas")), true);
    const refresh = page.getByRole("button", {name: "Atualizar", exact: true});
    assert.equal(await refresh.locator("svg.icon").count(), 1);
    assert.equal(await refresh.evaluate(n => getComputedStyle(n).height), "32px");
    assert.match(await page.locator("footer").innerText(), /Relatórios do Chatwoot/);
    assert.doesNotMatch(await page.locator("main").innerText(), /Indicadores de atendimento/);
    let reload = page.waitForResponse("**/kanban/metrics/timeline?*");
    await refresh.click();
    await reload;
    await page.locator("#metrics-status", {hasText: "Atualizado às"}).waitFor();
    assert.equal(new Set(requests.filter(r => r.block !== "options").map(r => r.block)).size, 7);

    // UX-40: filtros como menu, sem lista nativa; o <select> segue como valor.
    for (const id of ["funnel-filter", "period", "assignee-filter", "inbox-filter"])
      assert.equal(await page.locator(`#${id}`).getAttribute("aria-hidden"), "true");
    assert.equal(await trigger("Funil").textContent(), "Funil");
    assert.equal(await trigger("Período: Este mês").textContent(), "Este mês");
    await trigger("Responsável").click();
    assert.equal(await option("Todos os responsáveis").getAttribute("aria-selected"), "true");
    const menu = await page.locator(".filter-menu:visible").boundingBox();
    assert.ok(menu.x >= 0, "o menu abre para dentro da página");
    reload = page.waitForResponse("**/kanban/metrics/summary?*");
    await option("Ana Demo").click();
    await reload;
    assert.ok(requests.some(r => r.block === "summary" && r.assignee_id === "2"));
    assert.equal(await trigger("Responsável: Ana Demo").textContent(), "Ana Demo");
    await trigger("Caixa de entrada").focus();
    await page.keyboard.press("ArrowDown");
    await option("Demo WhatsApp").waitFor();
    await page.keyboard.press("Escape");
    assert.equal(await page.getByRole("listbox").count(), 0);
    await page.waitForTimeout(100);
    assert.equal(await page.evaluate(() => window.messages.filter(m => m?.event === "kanban:close").length), 0);
    await trigger("Período: Este mês").click();
    await option("Personalizado").click();
    await page.locator("#custom-range").waitFor();
    for (const id of ["start", "end"])
      assert.equal(await page.locator(`#${id}`).evaluate(n => getComputedStyle(n).height), "40px");
    assert.equal(await page.locator("#custom-range label").first().innerText(), "De");

    // UX-42: sem dado anterior, nenhuma comparação e uma única nota.
    await open();
    assert.equal(await page.locator(".change").count(), 0);
    assert.equal(await page.locator("#comparison-note").isVisible(), true);
    assert.equal(await page.locator("#comparison-note").innerText(), "Sem dados no período anterior (07/08/2026 a 31/08/2026) para comparar.");
    assert.equal((await page.locator("body").innerText()).match(/período anterior/gi).length, 1);

    // UX-44: exportar como botão ghost com ícone de download.
    const exports = page.locator("a.metric-action:visible");
    assert.ok(await exports.count() >= 6);
    assert.equal(await exports.first().innerText(), "Exportar CSV");
    assert.equal(await exports.first().locator("svg.icon").count(), 1);
    assert.equal(await exports.first().evaluate(n => getComputedStyle(n).textDecorationLine), "none");
    assert.match(await exports.first().getAttribute("href"), /format=csv/);

    // UX-45: sem "↕" nem "?"; ícone só na coluna ordenada; ajuda como dica.
    const text = await page.locator("main").innerText();
    assert.doesNotMatch(text, /↕|\?/);
    const funnelTable = page.locator("#funnel .metrics-table");
    assert.equal(await funnelTable.locator(".sort-icon").count(), 0);
    assert.match(await funnelTable.getByRole("button", {name: "Etapa seguinte"}).getAttribute("title"), /etapa seguinte/);
    await funnelTable.getByRole("button", {name: "Entradas"}).click();
    assert.equal(await funnelTable.locator(".sort-icon").count(), 1);
    assert.equal(await funnelTable.locator("th[aria-sort]").getAttribute("aria-sort"), "descending");
    assert.equal(await funnelTable.locator("tbody tr td").first().innerText(), "Novo");
    await funnelTable.getByRole("button", {name: "Entradas"}).click();
    assert.equal(await funnelTable.locator("th[aria-sort]").getAttribute("aria-sort"), "ascending");

    // UX-47: sem o nome do único funil e barras na cor de cada etapa.
    const funnelChart = await page.evaluate(() => {
      const chart = Chart.getChart(document.querySelector("#funnel canvas"));
      return {labels: chart.data.labels, colors: chart.data.datasets[0].backgroundColor};
    });
    assert.deepEqual(funnelChart.labels, fixtures.month.funnel.current.rows.map(r => r.name));
    assert.deepEqual(funnelChart.colors, fixtures.month.funnel.current.rows.map(r => r.color));

    // UX-48: linhas retas e datas sem inclinação.
    const timeline = await page.evaluate(() => {
      const chart = Chart.getChart(document.querySelector("#timeline canvas"));
      return {tension: chart.data.datasets.map(d => d.tension), rotation: chart.options.scales.x.ticks.maxRotation,
        limit: chart.options.scales.x.ticks.maxTicksLimit, label: chart.data.labels[0]};
    });
    assert.deepEqual(timeline.tension, [0, 0]);
    assert.equal(timeline.rotation, 0);
    assert.ok(timeline.limit <= 8);
    assert.equal(timeline.label, "01/09");

    // UX-50: glossário com "negociação", sem "card".
    const titles = await page.locator("[title]").evaluateAll(nodes => nodes.map(n => n.title));
    assert.ok(titles.length > 10);
    assert.equal(titles.some(t => /\bcards?\b|kind=/i.test(t)), false);

    // UX-46: estado vazio único com ação para Configurações (administrador).
    const sources = page.locator("#sources");
    assert.equal(await sources.locator("table").count(), 0);
    assert.equal(await sources.getByText("Não informada").count(), 0);
    await sources.getByRole("heading", {name: "Origem e campanha não configuradas"}).waitFor();
    assert.equal(await sources.locator("a.metric-action").isVisible(), false);
    await sources.getByRole("button", {name: "Abrir configurações"}).click();
    await page.waitForFunction(() => window.messages.some(m => m?.event === "kanban:open-page"));
    assert.deepEqual(await page.evaluate(() => window.messages.find(m => m?.event === "kanban:open-page")),
      {event: "kanban:open-page", account: 2, page: "configuracoes"});

    // UX-41: uma linha por variação, com rótulo.
    data = structuredClone(fixtures.month);
    Object.assign(data.summary.previous, {wins: 3, revenue: 1000000, leads: 20});
    await open();
    const wins = kpi("Ganhos e receita");
    assert.deepEqual(await wins.locator(".change").allInnerTexts(), ["Ganhos: +100% vs. anterior", "Receita: +183% vs. anterior"]);
    assert.equal(await kpi("Leads novos").locator(".change").innerText(), "+25% vs. anterior");
    assert.equal(await page.locator("#comparison-note").innerText(), "Indicadores sem variação não têm valor no período anterior.");
    assert.match(await page.locator("#period-caption").innerText(), /comparado com 07\/08\/2026 a 31\/08\/2026/);

    // UX-43: sem tarefa concluída, "no prazo" mostra "—" (dados reais de 24/09).
    data = fixtures.yesterday;
    assert.equal(data.tasks.current.on_time_rate, null);
    await open();
    const onTime = kpi("Concluídas no prazo");
    assert.equal(await onTime.locator(".kpi-value").innerText(), "—");
    assert.equal(await onTime.locator(".kpi-hint").innerText(), "Nenhuma tarefa concluída no período.");
    assert.equal(await kpi("Concluídas").last().locator(".kpi-value").innerText(), "0");

    // Agente não vê a ação de Configurações.
    data = fixtures.month;
    role = "agent";
    await open();
    await page.locator("#sources .empty-state").waitFor();
    assert.equal(await page.locator("#sources").getByRole("button", {name: "Abrir configurações"}).count(), 0);
    assert.match(await page.locator("#sources .empty-state").innerText(), /administrador/);

    // Esc fora de menu fecha o painel.
    await page.keyboard.press("Escape");
    await page.waitForFunction(() => window.messages.some(m => m?.event === "kanban:close"));

    assert.deepEqual(errors, []);
    console.log("Métricas: filtros por menu, comparações, estado vazio, tabelas, gráficos e cabeçalho aprovados");
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
