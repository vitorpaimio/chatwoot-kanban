// Testa o frontend real com API controlada; não é certificação do Chatwoot.
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
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    await page.addInitScript(() => {
      window.EventSource = class extends EventTarget {
        constructor() { super(); window.stream = this; }
        close() {}
      };
    });
    const board = { funnels: [{id: 1, name: "Principal"}], stages: [{id: 1, funnel_id: 1, name: "Novo", color: "#6366f1", kind: "open"}], contacts: [], cards: [] };
    const session = {role: "administrator", activation: {enabled: true, activation_status: "ready"}};
    const provisioning = {attribute_mappings: {origem: null, campanha: null, temperatura: null}, processing_limit: 10,
      provisioning_warnings: [], activation_status: "ready", import_status: "idle", imported_count: 0,
      resources: [{resource_key: "contact:kanban_etapa", ownership: "preexisting"}]};
    const submissions = [];
    await page.route("**/kanban/session?*", route => route.fulfill({json: session}));
    await page.route("**/kanban/board?*", route => route.fulfill({json: board}));
    await page.route("**/kanban/provisioning?*", route => {
      if (route.request().method() === "PUT") submissions.push(route.request().postDataJSON());
      return route.fulfill({json: provisioning});
    });
    await page.route("**/kanban/import/estimate?*", route => route.fulfill({json: {contacts: 42}}));
    await page.route("**/kanban/import?*", route => {
      submissions.push(route.request().postDataJSON());
      return route.fulfill({json: {status: "pending"}});
    });
    await page.goto(`http://127.0.0.1:${server.address().port}/kanban?account=1`);
    if ((await page.locator("#more-actions").getAttribute("open")) === null) {
      await page.getByLabel("Mais ações", {exact: true}).click();
    }
    await page.locator("#reimport").click();
    await page.getByText("Estimativa: 42 contatos.", {exact: false}).waitFor();
    assert.equal(await page.getByLabel("O que importar").inputValue(), "metadata");
    await page.locator("#dialog-save").click();
    assert.equal(submissions[0].mode, "metadata");
    if ((await page.locator("#more-actions").getAttribute("open")) === null) {
      await page.getByLabel("Mais ações", {exact: true}).click();
    }
    await page.locator("#reimport").click();
    await page.getByLabel("O que importar").selectOption("cards");
    await page.getByLabel("Etapa de destino").selectOption("1");
    await page.locator("#dialog-save").click();
    assert.deepEqual(submissions[1], {mode: "cards", funnel_id: 1, stage_id: 1});
    await page.locator("#manage").click();
    await page.getByRole("button", {name: "Configuração da conta", exact: true}).click();
    await page.getByText("contact:kanban_etapa: preexistente", {exact: true}).waitFor();
    await page.getByLabel("Atributo de origem (vazio desativa)").fill("fonte");
    await page.getByLabel("Contatos por lote e por conta").fill("3");
    await page.locator("#dialog-save").click();
    assert.equal(submissions[2].mappings.origem, "fonte");
    assert.equal(submissions[2].processing_limit, 3);
    provisioning.import_status = "failed"; provisioning.import_error = "Requisição interrompida";
    provisioning.imported_count = 12;
    if ((await page.locator("#more-actions").getAttribute("open")) === null) {
      await page.getByLabel("Mais ações", {exact: true}).click();
    }
    await page.locator("#reimport").click();
    await page.getByText("12 contatos processados.", {exact: false}).waitFor();
    await page.locator("#dialog-save").click();
    assert.deepEqual(submissions[3], {resume: true});
    session.activation.activation_status = "pending";
    await page.reload();
    await page.getByText("Provisionamento: em andamento.", {exact: false}).waitFor();
    session.activation.activation_status = "ready";
    await page.locator("#notice").waitFor({state: "hidden", timeout: 10000});
    session.activation.activation_status = "failed";
    await page.reload();
    await page.locator("#manage").click();
    await page.getByRole("heading", {name: "Configuração da conta", exact: true}).waitFor();
    await page.getByText("Provisionamento: pronto.", {exact: true}).waitFor();
    assert.deepEqual(errors, []);
    console.log("Fase 2: estimativa, modos explícitos, mapeamento, manifesto e retomada aprovados");
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
