// Páginas Tarefas e Configurações com API controlada (ADR-045).
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const http = require("node:http");
const templates = {"/kanban/tarefas": "templates/tarefas.html", "/kanban/configuracoes": "templates/configuracoes.html"};
(async () => {
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, "http://localhost");
    const file = templates[url.pathname] ||
      (url.pathname.startsWith("/kanban/static/") ? url.pathname.slice(8) : null);
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
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    await page.addInitScript(() => {
      window.messages = [];
      window.addEventListener("message", (e) => window.messages.push(e.data));
      window.EventSource = class extends EventTarget { close() {} };
    });

    // Tarefas: contagens por estado, filtro por aba, abrir o cartão, vazio e 403.
    const tasks = [
      {id: 1, card_id: 11, descricao: "Enviar proposta revisada", vencimento: "2026-09-20", due_state: "overdue", name: "Ana Souza",
        funnel: "Funil principal", stage: "Proposta enviada", stage_color: "#e54666", assignee_name: "Ana Demo"},
      {id: 2, card_id: 12, descricao: "Ligar para confirmar", vencimento: "2026-09-25", due_state: "today", name: "Bruno Lima",
        funnel: "Funil principal", stage: "Novo", stage_color: "#6366f1", assignee_name: null},
    ];
    const queries = [];
    let tasksStatus = 200;
    await page.route("**/kanban/tasks?*", route => {
      const query = Object.fromEntries(new URL(route.request().url()).searchParams);
      queries.push(query);
      if (tasksStatus !== 200) return route.fulfill({status: tasksStatus, json: {detail: "Conta não habilitada para o Kanban"}});
      const rows = tasks.filter(t => !query.state || t.due_state === query.state);
      return route.fulfill({json: {tasks: rows, counts: {total: 2, overdue: 1, today: 1, active: 0}}});
    });
    await page.goto(`${origin}/kanban/tarefas?account=1`);
    await page.getByRole("heading", {name: "Tarefas", exact: true}).waitFor();
    await page.locator(".task-row").nth(1).waitFor();
    assert.equal(await page.getByRole("tab", {name: "Vencidas (1)"}).count(), 1);
    assert.equal(await page.locator(".task-row").first().locator(".due").textContent(), "20/09/2026");
    assert.equal(await page.locator(".task-row").first().locator(".due-label").textContent(), "Vencida");
    assert.equal(await page.locator(".task-row").nth(1).locator("td").nth(3).textContent(), "Sem responsável");
    await page.getByRole("tab", {name: "Vencem hoje (1)"}).click();
    await page.waitForFunction(() => document.querySelectorAll(".task-row").length === 1);
    assert.equal(queries.at(-1).state, "today");
    await page.getByRole("tab", {name: "Vencem hoje (1)"}).press("ArrowRight");
    await page.getByText("Nenhuma tarefa agendada para os próximos dias.", {exact: true}).waitFor();
    assert.equal(await page.locator("#tasks").isVisible(), false);
    await page.getByRole("tab", {name: "Todas (2)"}).click();
    await page.locator(".task-row").nth(1).waitFor();
    await page.locator(".task-row").first().press("Enter");
    await page.waitForFunction(() => window.messages.some(m => m?.event === "kanban:open-card"));
    assert.deepEqual(await page.evaluate(() => window.messages.find(m => m?.event === "kanban:open-card")), {event: "kanban:open-card", account: 1, id: 11});
    tasksStatus = 403;
    await page.reload();
    await page.getByText("O Pipeline não está ativo nesta conta. Abra o Kanban para ativá-lo.", {exact: true}).waitFor();

    // Configurações: situação, atributos, motivos, lote, importação, token e desativação.
    const provisioning = {attribute_mappings: {origem: null, campanha: null, temperatura: null}, processing_limit: 10,
      provisioning_warnings: [], activation_status: "ready", activation_error: null, import_status: "idle",
      import_error: null, imported_count: 0, resources: [
        {resource_type: "attribute", resource_key: "contact:kanban_etapa", ownership: "preexisting"},
        {resource_type: "webhook", resource_key: "http://proxy/kanban/webhooks/1/events", ownership: "created"}]};
    const session = {role: "administrator", activation: {enabled: true, activation_status: "ready"}};
    const sent = [];
    const record = (route) => sent.push([route.request().method(), new URL(route.request().url()).pathname, route.request().postDataJSON()]);
    await page.route("**/kanban/session?*", route => route.fulfill({json: session}));
    await page.route("**/kanban/provisioning?*", route => {
      if (route.request().method() === "PUT") {
        record(route);
        Object.assign(provisioning, {attribute_mappings: route.request().postDataJSON().mappings,
          processing_limit: route.request().postDataJSON().processing_limit});
      }
      return route.fulfill({json: provisioning});
    });
    await page.route("**/kanban/metrics/configuration?*", route => {
      if (route.request().method() === "PUT") {
        record(route);
        return route.fulfill({json: route.request().postDataJSON()});
      }
      return route.fulfill({json: {loss_reasons: ["Preço"]}});
    });
    await page.route("**/kanban/import/estimate?*", route => route.fulfill({json: {contacts: 42}}));
    await page.route("**/kanban/board?*", route => route.fulfill({json: {funnels: [{id: 1, name: "Principal"}], cards: [], contacts: [],
      stages: [{id: 1, funnel_id: 1, name: "Novo", kind: "open"}, {id: 2, funnel_id: 1, name: "Ganho", kind: "won"}]}}));
    for (const path of ["import", "activation", "provisioning/retry"])
      await page.route(`**/kanban/${path}?*`, route => { record(route); return route.fulfill({json: {status: "ok"}}); });
    await page.route("**/kanban/activate?*", route => route.fulfill({status: 400, json: {detail: "Token sem acesso administrativo à conta"}}));
    const last = () => sent.at(-1);
    await page.goto(`${origin}/kanban/configuracoes?account=1`);
    await page.getByRole("heading", {name: "Situação", exact: true}).waitFor();
    assert.equal(await page.locator(".badge").textContent(), "Pronto");
    assert.deepEqual(await page.locator(".resource-list li").allTextContents(), [
      "Atributo de contatocontact:kanban_etapajá existia", "Webhookhttp://proxy/kanban/webhooks/1/eventscriado pelo Pipeline"]);

    await page.getByLabel("Origem", {exact: true}).fill("fonte");
    await page.getByRole("button", {name: "Salvar atributos"}).click();
    await page.getByText("Atributos salvos.", {exact: false}).waitFor();
    assert.deepEqual(last(), ["PUT", "/kanban/provisioning", {mappings: {origem: "fonte", campanha: null, temperatura: null}, processing_limit: 10}]);

    assert.equal(await page.getByLabel("Motivos", {exact: true}).inputValue(), "Preço");
    await page.getByLabel("Motivos", {exact: true}).fill("Preço\n\nConcorrente\n");
    await page.getByRole("button", {name: "Salvar motivos"}).click();
    await page.getByText("Motivos de perda salvos.", {exact: true}).waitFor();
    assert.deepEqual(last()[2], {loss_reasons: ["Preço", "Concorrente"]});

    await page.getByLabel("Contatos por lote", {exact: true}).fill("3");
    await page.getByRole("button", {name: "Salvar", exact: true}).click();
    await page.getByText("Tamanho do lote salvo.", {exact: true}).waitFor();
    assert.deepEqual(last()[2], {mappings: {origem: "fonte", campanha: null, temperatura: null}, processing_limit: 3});

    await page.getByRole("button", {name: "Importar contatos"}).click();
    await page.getByText("O que importar · 42 contatos no Chatwoot", {exact: true}).waitFor();
    await page.getByLabel("Dados e negociações para quem ainda não está no funil").check();
    assert.deepEqual(await page.locator("#import select[name=stage] option").allTextContents(), ["Novo"]);
    await page.getByRole("button", {name: "Iniciar importação"}).click();
    await page.getByText("Importação agendada.", {exact: true}).waitFor();
    assert.deepEqual(last(), ["POST", "/kanban/import", {mode: "cards", funnel_id: 1, stage_id: 1}]);

    Object.assign(provisioning, {import_status: "failed", import_error: "Requisição interrompida", imported_count: 12});
    await page.reload();
    await page.getByText("Importação interrompida. 12 contatos processados. Requisição interrompida", {exact: true}).waitFor();
    await page.getByRole("button", {name: "Retomar importação"}).click();
    await page.getByText("Importação retomada.", {exact: true}).waitFor();
    assert.deepEqual(last()[2], {resume: true});

    await page.getByLabel("Novo token de acesso", {exact: true}).fill("token-sem-permissao");
    await page.getByRole("button", {name: "Atualizar token"}).click();
    await page.getByText("Este token não tem acesso de administrador a esta conta.", {exact: false}).waitFor();

    await page.getByRole("button", {name: "Desativar Pipeline"}).click();
    await page.getByRole("dialog", {name: "Desativar o Pipeline?"}).getByRole("button", {name: "Desativar", exact: true}).click();
    await page.getByText("O Pipeline foi desativado nesta conta.", {exact: false}).waitFor();
    assert.deepEqual(last(), ["PUT", "/kanban/activation", {enabled: false}]);
    await page.getByRole("button", {name: "Abrir Kanban"}).click();
    await page.waitForFunction(() => window.messages.some(m => m?.event === "kanban:open-page" && m.page === "kanban"));

    session.role = "agent";
    await page.reload();
    await page.getByText("Apenas administradores da conta podem alterar as configurações do Pipeline.", {exact: true}).waitFor();
    await page.keyboard.press("Escape");
    await page.waitForFunction(() => window.messages.some(m => m?.event === "kanban:close"));

    assert.deepEqual(errors, []);
    console.log("Páginas: tarefas (abas, abrir cartão, vazio, 403) e configurações (conta, atributos, motivos, importação, token, desativação) aprovadas");
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
