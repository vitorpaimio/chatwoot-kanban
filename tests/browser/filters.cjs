// Menus de filtro da barra (Responsável, Etiqueta, Tarefa) com API controlada.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const http = require("node:http");
(async () => {
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, "http://localhost");
    const file = url.pathname === "/kanban" ? "templates/kanban.html" :
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
    const context = await browser.newContext();
    await context.addCookies([{name: "cw_d_session_info", value: encodeURIComponent(JSON.stringify({"access-token": "a", client: "b", uid: "c"})), url: origin}]);
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    await page.addInitScript(() => {
      window.closes = 0;
      window.addEventListener("message", (e) => { if (e.data?.event === "kanban:close") window.closes++; });
      window.EventSource = class extends EventTarget { close() {} };
    });
    const labels = ["vip", "lead-quente", "lead-frio", "retorno", "orcamento", "suporte", "demo", "parceiro", "indicacao"];
    const card = {id: 1, contact_id: 1, funnel_id: 1, stage_id: 1, name: "Ana Souza", labels: ["vip"], value_cents: 0, assignee_id: 4, assignee_name: "Bruno", version: 1};
    const board = {funnels: [{id: 1, name: "Principal"}], stages: [{id: 1, funnel_id: 1, name: "Novo", color: "#6366f1", kind: "open"}],
      contacts: [], cards: [card], agents: [{id: 4, name: "Bruno"}, {id: 5, name: "Carla"}]};
    const queries = [];
    let labelPayload = labels.map((title, i) => ({title, color: i === 0 ? "#e54666" : "#2781f6"}));
    await page.route("**/kanban/session?*", route => route.fulfill({json: {role: "administrator", activation: {enabled: true, activation_status: "ready"}}}));
    await page.route("**/kanban/board?*", route => {
      queries.push(Object.fromEntries(new URL(route.request().url()).searchParams));
      return route.fulfill({json: board});
    });
    await page.route("**/api/v1/accounts/1/labels", route => route.fulfill({json: {payload: labelPayload}}));
    await page.route("**/api/v1/accounts/1/agents", route => route.fulfill({json: []}));
    await page.goto(`${origin}/kanban?account=1`);
    await page.locator("[data-stage-id]").first().waitFor();

    // A página do quadro não rola: só o quadro (horizontal) e as colunas (vertical).
    const cardBox = await page.locator(".card").first().boundingBox();
    await page.mouse.move(cardBox.x + 20, cardBox.y + 20);
    await page.mouse.wheel(0, 600);
    await page.waitForTimeout(200);
    assert.equal(await page.evaluate(() => scrollY), 0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight), true);

    const trigger = (name) => page.getByRole("button", {name, exact: true});
    const option = (name) => page.getByRole("option", {name, exact: true});
    const next = () => page.waitForResponse("**/kanban/board?*");

    // Etiqueta: rótulo neutro, opção "todas", pesquisa com mais de 8 opções e cor.
    assert.equal(await trigger("Etiqueta").textContent(), "Etiqueta");
    await trigger("Etiqueta").click();
    assert.equal(await option("Todas as etiquetas").getAttribute("aria-selected"), "true");
    await page.getByLabel("Pesquisar em Etiqueta").fill("vi");
    assert.equal(await page.getByRole("option").count(), 2);
    assert.equal(await option("vip").locator(".label-dot").evaluate(n => getComputedStyle(n).getPropertyValue("--label-color")), "#e54666");
    let response = next();
    await option("vip").click();
    await response;
    assert.equal(queries.at(-1).label, "vip");
    assert.equal(await trigger("Etiqueta: vip").textContent(), "vip");
    assert.ok(await page.locator(".filter.active").count());
    assert.equal(await page.getByRole("listbox").count(), 0);

    // Tarefa pelo teclado: seta abre, seta navega, Enter aplica; Esc não fecha o painel.
    await trigger("Filtrar por tarefa").focus();
    await page.keyboard.press("ArrowDown");
    await option("Todas as tarefas").waitFor();
    assert.equal(await page.getByRole("option").count(), 5);
    await page.keyboard.press("ArrowDown");
    response = next();
    await page.keyboard.press("Enter");
    await response;
    assert.equal(queries.at(-1).task, "none");
    assert.equal(await trigger("Filtrar por tarefa: Sem tarefa").textContent(), "Sem tarefa");
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Escape");
    assert.equal(await page.getByRole("listbox").count(), 0);
    assert.equal(await page.evaluate(() => document.activeElement.getAttribute("aria-label")), "Filtrar por tarefa: Sem tarefa");
    assert.equal(await page.evaluate(() => window.closes), 0);

    // Responsável pelo <select> invisível (compatível com os testes antigos).
    response = next();
    await page.locator("#assignee").selectOption("5");
    await response;
    assert.equal(queries.at(-1).assignee_id, "5");
    assert.equal(await trigger("Responsável: Carla").textContent(), "Carla");

    // Conta sem etiquetas: o menu explica em vez de mostrar uma lista vazia.
    labelPayload = [];
    board.cards = [{...card, labels: []}];
    await page.reload();
    await page.locator("[data-stage-id]").first().waitFor();
    await trigger("Etiqueta").click();
    await page.getByText("Nenhuma etiqueta nesta conta.", {exact: true}).waitFor();
    assert.equal(await page.getByLabel("Pesquisar em Etiqueta").isVisible(), false);
    await page.mouse.click(5, 5);
    assert.equal(await page.getByRole("listbox").count(), 0);

    assert.deepEqual(errors, []);
    console.log("Filtros: menus, pesquisa, teclado, estado vazio e compatibilidade com o select aprovados");
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
