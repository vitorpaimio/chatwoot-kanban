// Kanban com API controlada: ações do funil e estados da conta (ADR-043, ADR-045).
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
    await page.addInitScript(() => {
      window.messages = [];
      window.addEventListener("message", (e) => window.messages.push(e.data));
    });
    const board = { funnels: [{id: 1, name: "Principal", is_primary: true, stale_days: 7, position: 1024},
      {id: 2, name: "Pós-venda", is_primary: false, stale_days: 14, position: 2048}],
      stages: [{id: 1, funnel_id: 1, name: "Novo", color: "#6366f1", kind: "open", position: 1024},
        {id: 2, funnel_id: 2, name: "Onboarding", color: "#12a594", kind: "open", position: 1024}], contacts: [],
      cards: [{id: 7, contact_id: 7, funnel_id: 1, stage_id: 1, position: 1, name: "Ana Souza", labels: [], value_cents: 450000,
        version: 1, assignee_id: 2, assignee_name: "Ana Demo", task_id: 3, message: "Enviar proposta revisada",
        due_date: "2026-09-20", due_state: "overdue", task_assignee_name: "Ana Demo", sync_status: "synced"}] };
    const session = {role: "administrator", activation: {enabled: true, activation_status: "ready"}};
    const sent = [];
    await page.route("**/kanban/session?*", route => route.fulfill({json: session}));
    await page.route("**/kanban/board?*", route => route.fulfill({json: board}));
    await page.route("**/kanban/funnels**", route => {
      sent.push([route.request().method(), new URL(route.request().url()).pathname, route.request().postDataJSON()]);
      return route.fulfill({json: {id: 3}});
    });
    await page.goto(`http://127.0.0.1:${server.address().port}/kanban?account=1`);

    // Ações do funil na barra superior (antes dentro de "Gerenciar funil").
    await page.locator("[data-stage-id]").first().waitFor();
    // Tarefa: só o indicador no cartão; texto, vencimento e responsável na janela.
    const card = page.locator(".card").first();
    assert.equal(await card.locator(".task-flag.overdue").getAttribute("title"), "Vencida · 20/09/2026");
    assert.doesNotMatch(await card.textContent(), /Enviar proposta revisada/);
    await card.locator(".card-name").click();
    await page.locator(".detail-task").getByText("Enviar proposta revisada", {exact: true}).waitFor();
    assert.equal(await page.locator(".detail-task-due").textContent(), "Vencida · 20/09/2026");
    await page.getByText("Responsável da tarefa: Ana Demo", {exact: true}).waitFor();
    assert.doesNotMatch(await page.locator("#dialog-content").textContent(), /Sincroniza/);
    await page.locator("#dialog-close").click();

    // Barra como as listas do Chatwoot: busca de 240 px e ação principal no fim.
    assert.equal(await page.locator(".search").evaluate(n => n.getBoundingClientRect().width), 240);
    assert.equal(await page.locator(".toolbar > :last-child").getAttribute("id"), "add-card");
    // O ponto de status leva à Situação em Configurações.
    await page.locator("#status-link").click();
    await page.waitForFunction(() => window.messages.some(m => m?.event === "kanban:open-page" && m.page === "configuracoes"));

    assert.equal(await page.locator("#funnel-actions").isVisible(), true);
    assert.equal(await page.locator("#archive-funnel").isHidden(), true);
    await page.getByRole("button", {name: "Gerenciar etapas do funil"}).click();
    await page.getByRole("heading", {name: "Etapas · Principal", exact: true}).waitFor();
    assert.equal(await page.getByRole("button", {name: "Configuração da conta"}).count(), 0);
    assert.equal(await page.getByRole("button", {name: "Motivos de perda"}).count(), 0);
    await page.locator("#dialog-close").click();
    await page.getByRole("button", {name: "Novo funil"}).click();
    await page.getByLabel("Nome do funil").fill("Parcerias");
    await page.locator("#dialog-save").click();
    await page.waitForFunction(() => !document.getElementById("dialog").open);
    assert.deepEqual(sent.at(-1).slice(0, 2), ["POST", "/kanban/funnels"]);
    assert.equal(sent.at(-1)[2].name, "Parcerias");

    await page.locator("#funnel-picker summary").click();
    await page.getByRole("button", {name: "Pós-venda", exact: true}).click();
    await page.getByLabel("Mais ações do funil").click();
    await page.getByRole("button", {name: "Editar funil", exact: true}).click();
    assert.equal(await page.getByLabel("Nome do funil").inputValue(), "Pós-venda");
    await page.locator("#dialog-close").click();
    await page.getByLabel("Mais ações do funil").click();
    await page.getByRole("button", {name: "Arquivar funil", exact: true}).click();
    await page.getByRole("heading", {name: 'Arquivar funil "Pós-venda"?', exact: true}).waitFor();
    await page.locator("#dialog-save").click();
    await page.waitForFunction(() => !document.getElementById("dialog").open);
    assert.deepEqual(sent.at(-1).slice(0, 2), ["POST", "/kanban/funnels/2/archive"]);
    assert.equal(await page.getByRole("button", {name: "Importar contatos"}).count(), 0);

    // Estados da conta: configurando e falha que leva à página Configurações.
    session.activation.activation_status = "pending";
    await page.reload();
    await page.getByRole("heading", {name: "Configurando o Pipeline…", exact: true}).waitFor();
    assert.equal(await page.locator("#funnel-actions").isHidden(), true);
    session.activation.activation_status = "ready";
    await page.locator("#activation").waitFor({state: "hidden", timeout: 10000});
    session.activation.activation_status = "failed";
    await page.reload();
    await page.getByRole("button", {name: "Abrir configurações", exact: true}).click();
    await page.waitForFunction(() => window.messages.some(m => m?.event === "kanban:open-page" && m.page === "configuracoes"));
    assert.deepEqual(errors, []);
    console.log("Kanban: ações do funil na barra superior, etapas e estados da conta aprovados");
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
