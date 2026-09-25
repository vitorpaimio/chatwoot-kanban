// Fluxo de ativação com API controlada (ADR-043); não é certificação do Chatwoot.
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
      window.streams = 0;
      window.EventSource = class extends EventTarget {
        constructor() { super(); window.streams++; window.lastStream = this; }
        close() {}
      };
    });
    const board = { funnels: [{id: 1, name: "Principal"}], stages: [{id: 1, funnel_id: 1, name: "Novo", color: "#6366f1", kind: "open"}], contacts: [], cards: [] };
    let session = {role: "administrator", activation: null};
    const calls = [];
    await page.route("**/kanban/session?*", route => route.fulfill({json: session}));
    await page.route("**/kanban/board?*", route => route.fulfill({json: board}));
    await page.route("**/kanban/activate?*", route => {
      const token = route.request().postDataJSON().token;
      calls.push("activate");
      if (token !== "token-de-administrador")
        return route.fulfill({status: 400, json: {detail: "Token sem acesso administrativo à conta"}});
      session = {...session, activation: {enabled: true, activation_status: "pending", activation_error: null}};
      return route.fulfill({json: {status: "pending"}});
    });
    await page.route("**/kanban/provisioning/retry?*", route => {
      calls.push("retry");
      return route.fulfill({json: {status: "pending"}});
    });
    const hidden = async (selector) => assert.equal(await page.locator(selector).isVisible(), false, selector);
    await page.goto(`http://127.0.0.1:${server.address().port}/kanban?account=1`);

    // Conta sem ativação: só o painel, sem quadro, engrenagem ou tempo real.
    await page.getByRole("heading", {name: "Ative o Pipeline nesta conta", exact: true}).waitFor();
    assert.equal(await page.locator(".page-header h1").textContent(), "Pipeline");
    for (const selector of [".toolbar", "#board", ".board-status", "#manage", "#connection", "#setup-spinner"]) await hidden(selector);
    assert.equal(await page.evaluate(() => window.streams), 0);

    // Token recusado: erro junto do campo, sem aviso global.
    await page.getByLabel("Token de acesso", {exact: true}).fill("token-sem-permissao");
    await page.getByRole("button", {name: "Ativar Pipeline", exact: true}).click();
    await page.getByText("Este token não tem acesso de administrador", {exact: false}).waitFor();
    assert.equal(await page.getByLabel("Token de acesso", {exact: true}).getAttribute("aria-invalid"), "true");
    await hidden("#notice");

    // Token aceito: configuração em andamento, com progresso e sem formulário.
    await page.getByLabel("Token de acesso", {exact: true}).fill("token-de-administrador");
    await page.getByRole("button", {name: "Ativar Pipeline", exact: true}).click();
    await page.getByRole("heading", {name: "Configurando o Pipeline…", exact: true}).waitFor();
    assert.equal(await page.locator("#setup-spinner").isVisible(), true);
    await hidden("#activate-form");
    await hidden(".toolbar");

    // Falha com nova tentativa automática: motivo e ações de administrador.
    session.activation.activation_error = "Chatwoot indisponível (HTTP 502)";
    await page.getByRole("heading", {name: "Não foi possível concluir a configuração", exact: true}).waitFor();
    await page.getByText("Motivo: Chatwoot indisponível (HTTP 502). Uma nova tentativa será feita automaticamente.", {exact: true}).waitFor();
    await page.getByRole("button", {name: "Abrir configurações", exact: true}).waitFor();
    session.activation.activation_error = null;
    await page.getByRole("button", {name: "Tentar novamente", exact: true}).click();
    await page.getByRole("heading", {name: "Configurando o Pipeline…", exact: true}).waitFor();
    assert.deepEqual(calls, ["activate", "activate", "retry"]);

    // Conta pronta: o quadro aparece e o tempo real conecta uma única vez.
    session.activation.activation_status = "ready";
    await page.locator("#activation").waitFor({state: "hidden", timeout: 10000});
    await page.locator(".toolbar").waitFor();
    await page.locator("#manage").waitFor();
    await page.locator("[data-stage-id]").first().waitFor();
    assert.equal(await page.evaluate(() => window.streams), 1);

    // Conta desativada: reativar é só informar o token de novo.
    session.activation.enabled = false;
    await page.reload();
    await page.getByRole("heading", {name: "Reative o Pipeline nesta conta", exact: true}).waitFor();
    await hidden(".toolbar");
    await hidden("#setup-actions");
    await page.getByLabel("Token de acesso", {exact: true}).fill("token-de-administrador");
    await page.getByRole("button", {name: "Reativar Pipeline", exact: true}).click();
    await page.getByRole("heading", {name: "Configurando o Pipeline…", exact: true}).waitFor();
    assert.equal(session.activation.enabled, true);

    // Desativada em outra aba: um 403 do quadro volta ao painel, sem aviso de erro.
    session.activation.activation_status = "ready";
    await page.locator(".toolbar").waitFor({timeout: 10000});
    session.activation.enabled = false;
    await page.route("**/kanban/board?*", route => route.fulfill({status: 403, json: {detail: "Conta não habilitada para o Kanban"}}));
    await page.evaluate(() => window.lastStream.dispatchEvent(new Event("change")));
    await page.getByRole("heading", {name: "Reative o Pipeline nesta conta", exact: true}).waitFor();
    await hidden("#notice");
    await page.unroute("**/kanban/board?*");
    await page.route("**/kanban/board?*", route => route.fulfill({json: board}));

    // Agente com a conta desativada: só a orientação.
    session.role = "agent";
    await page.reload();
    await page.getByRole("heading", {name: "O Pipeline está desativado nesta conta", exact: true}).waitFor();
    await hidden("#activate-form");

    // Agente sem permissão: só a orientação, sem formulário nem ações.
    session = {role: "agent", activation: null};
    await page.reload();
    await page.getByRole("heading", {name: "O Pipeline ainda não está ativo nesta conta", exact: true}).waitFor();
    await hidden("#activate-form");
    await hidden("#setup-actions");
    await hidden("#manage");

    assert.deepEqual(errors, []);
    console.log("Ativação: estados, erros do token, nova tentativa e liberação do quadro aprovados");
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
