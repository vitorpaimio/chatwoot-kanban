const { email, password } = require("./credentials.cjs");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const root = process.env.CHATWOOT_URL || "http://localhost:3000";
const pause = (ms) => new Promise((r) => setTimeout(r, ms));
async function eventually(fn) {
  let last;
  for (let i = 0; i < 45; i++) {
    try {
      const value = await fn();
      if (value) return value;
    } catch (e) {
      last = e;
    }
    await pause(1000);
  }
  throw last || new Error("Condição não alcançada");
}
(async () => {
  const browser = await chromium.launch({
    executablePath:
      process.env.CHROME_PATH ||
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
  });
  const contexts = [];
  const errors = [];
  async function login() {
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
    });
    contexts.push(ctx);
    const page = await ctx.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await eventually(async () => {
      try {
        return (await ctx.request.get(root + "/app/login")).ok();
      } catch {
        return false;
      }
    });
    await page.goto(root + "/app/login");
    await page.locator("input[name=email_address]").fill(email);
    await page.locator("input[type=password]").fill(password);
    await page.locator("button[type=submit]").click();
    await page.waitForURL(/\/app\/accounts\//, { timeout: 60000 });
    await page.locator("aside nav").waitFor();
    if (!(await page.locator("#sidebar-account-switcher").count()))
      await page.locator("aside .cursor-col-resize").dblclick();
    await page.locator("#sidebar-account-switcher").waitFor();
    if (
      (await page
        .locator("#sidebar-account-switcher")
        .getAttribute("data-account-id")) !== "1"
    ) {
      await page.locator("#sidebar-account-switcher").click();
      await page.locator("#account-1").click();
      await page.waitForURL(/accounts\/1\/dashboard/);
      await page
        .locator('#sidebar-account-switcher[data-account-id="1"]')
        .waitFor();
    }
    console.log("LOGIN", page.url());
    await page.locator("#chatwoot-kanban-menu").waitFor();
    if (
      (await page
        .locator("[data-pipeline-header]")
        .getAttribute("aria-expanded")) !== "true"
    )
      await page.locator("[data-pipeline-header]").click();
    await page.getByRole("button", { name: "Kanban", exact: true }).click();
    await page
      .frameLocator("#chatwoot-kanban-panel iframe")
      .locator(".column")
      .first()
      .waitFor();
    return page;
  }
  const a = await login(),
    b = await login();
  const fa = a.frameLocator("#chatwoot-kanban-panel iframe"),
    fb = b.frameLocator("#chatwoot-kanban-panel iframe");
  const cookie = (await a.context().cookies()).find(
    (c) => c.name === "cw_d_session_info",
  );
  const creds = JSON.parse(decodeURIComponent(cookie.value));
  const headers = Object.fromEntries(
    ["access-token", "client", "uid"].map((k) => [k, creds[k]]),
  );

  const service = headers;
  async function api(path, method = "GET", body, account = 1) {
    const url = new URL("/kanban" + path, root);
    url.searchParams.set("account", account);
    const r = await a.request.fetch(url.href, { method, data: body });
    assert.ok(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`);
    return r.json();
  }
  const stamp = Date.now(),
    name = "Cliente de teste Kanban " + stamp;
  const created = await a.request.post(root + "/api/v1/accounts/1/contacts", {
    headers: service,
    data: { name, identifier: "kanban-test-" + stamp },
  });
  assert.ok(created.ok(), await created.text());
  const contact = (await created.json()).payload.contact;
  await eventually(async () =>
    (await api("/board")).cards.some((c) => c.contact_id === contact.id),
  );
  await fa.locator(".card").filter({ hasText: name }).waitFor();
  console.log("OK menu, login, importação por webhook");
  const cardA = () => fa.locator(".card").filter({ hasText: name });
  const cardB = () => fb.locator(".card").filter({ hasText: name });
  await cardA().getByRole("button", { name: "Criar tarefa" }).click();
  await fa.getByLabel("Tarefa", { exact: true }).fill("Retornar proposta");
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Sao_Paulo",
  }).format(new Date());
  await fa.getByLabel("Vencimento — horário de Brasília").fill(today);
  await fa.getByRole("button", { name: "Salvar", exact: true }).click();
  await cardB().getByText("Retornar proposta", { exact: false }).waitFor();
  assert.match(await cardB().textContent(), /Vence hoje/);
  await cardB()
    .getByRole("button", { name: "Editar tarefa", exact: true })
    .click();
  await fb.getByLabel("Tarefa", { exact: true }).fill("Rascunho preservado");
  let board = await api("/board");
  let card = board.cards.find((c) => c.contact_id === contact.id);
  const won = board.stages.find(
    (s) => s.funnel_id === card.funnel_id && s.kind === "won",
  );
  await api("/cards/" + card.id, "PATCH", {
    version: card.version,
    stage_id: won.id,
    value_cents: 129990,
  });
  await pause(1500);
  assert.equal(
    await fb.getByLabel("Tarefa", { exact: true }).inputValue(),
    "Rascunho preservado",
  );
  await fb.locator("#dialog-close").click();
  await eventually(
    async () =>
      (await cardB().locator("..").getAttribute("data-stage-id")) ===
      String(won.id),
  );
  console.log("OK SSE entre sessões, rascunho preservado e movimentação");
  await fa.getByRole("button", { name: "Gerenciar funis" }).click();
  await fa.getByRole("button", { name: "Criar funil", exact: true }).click();
  const funnelName = "Renovação teste " + stamp;
  await fa.getByLabel("Nome do funil").fill(funnelName);
  await fa.getByRole("button", { name: "Salvar", exact: true }).click();
  await fa.getByLabel("Selecionar funil", { exact: true }).click();
  await fa
    .locator("#funnel-picker button")
    .filter({ hasText: funnelName })
    .click();
  await fa
    .getByRole("button", { name: "Adicionar negociação", exact: true })
    .click();
  await fa.getByLabel("1. Buscar contato", { exact: true }).fill(name);
  await fa.locator(".contact-result").filter({ hasText: name }).click();
  await fa
    .getByRole("button", { name: "Criar negociação", exact: true })
    .click();
  await cardA().getByText("Retornar proposta", { exact: false }).waitFor();
  await cardA()
    .getByRole("button", { name: "Editar tarefa", exact: true })
    .click();
  await fa
    .getByRole("button", { name: "Concluir tarefa", exact: true })
    .click();
  await eventually(async () => {
    const r = await a.request.get(
      root + `/api/v1/accounts/1/contacts/${contact.id}`,
      { headers: service },
    );
    const c = (await r.json()).payload;
    return (
      c.custom_attributes.kanban_view_mensaje == null &&
      c.custom_attributes.kanban_view_fecha_termino == null
    );
  });
  await cardA().getByRole("button", { name: "Criar tarefa" }).click();
  await fa
    .getByLabel("Tarefa", { exact: true })
    .fill('<img src=x onerror="window.__xss=1">');
  await fa.getByLabel("Vencimento — horário de Brasília").fill(today);
  await fa.getByRole("button", { name: "Salvar", exact: true }).click();
  await cardA()
    .getByText('<img src=x onerror="window.__xss=1">', { exact: false })
    .waitFor();
  assert.equal(
    await a
      .frames()
      .find((f) => /\/kanban\/?\?/.test(f.url()))
      .evaluate(() => window.__xss),
    undefined,
  );
  console.log(
    "OK múltiplos funis, tarefa compartilhada, encerramento, recriação e XSS",
  );
  assert.ok((await api("/reports")).stages.length);
  await cardA()
    .getByRole("button", { name: "Editar tarefa", exact: true })
    .click();
  await fa
    .getByLabel("Tarefa", { exact: true })
    .fill("Retornar proposta de renovação");
  await fa.getByRole("button", { name: "Salvar", exact: true }).click();
  await fa.getByLabel("Selecionar funil", { exact: true }).click();
  await fa
    .locator("#funnel-picker button")
    .filter({ hasText: /^Funil principal$/ })
    .click();
  await a.screenshot({
    path: ".local/kanban-duas-sessoes.png",
    fullPage: true,
  });
  assert.equal(
    (await a.request.get(root + "/kanban/board?account=999999")).status(),
    403,
  );
  assert.equal((await api("/board", "GET", undefined, 2)).cards.length, 0);
  await fa
    .locator(".card")
    .filter({ has: fa.getByText("jane", { exact: true }) })
    .click();
  await fa
    .getByRole("button", { name: "Abrir conversa ou contato", exact: true })
    .click();
  await a.waitForURL(/\/conversations\/\d+/);
  console.log("OK relatórios, isolamento e abertura da conversa no Chatwoot");
  await a.screenshot({ path: ".local/conversa-chatwoot.png", fullPage: true });
  await a.waitForLoadState("domcontentloaded");
  assert.equal(await a.locator("iframe[id^=dashboard-app--frame]").count(), 0);
  assert.equal(
    await a
      .locator(".conversation-details-wrap a")
      .filter({ hasText: /^\s*Kanban\s*$/ })
      .count(),
    0,
  );
  console.log("OK conversa sem Dashboard App Kanban");
  await a.locator("#sidebar-account-switcher").click();
  await a.locator("#account-2").click();
  await a.waitForURL(/accounts\/2\/dashboard/);
  await a.locator('#sidebar-account-switcher[data-account-id="2"]').waitFor();
  if (
    (await a
      .locator("[data-pipeline-header]")
      .getAttribute("aria-expanded")) !== "true"
  )
    await a.locator("[data-pipeline-header]").click();
  await a.getByRole("button", { name: "Kanban", exact: true }).click();
  assert.equal(await a.locator("#chatwoot-kanban-menu").count(), 1);
  await a
    .frameLocator("#chatwoot-kanban-panel iframe")
    .locator(".column")
    .first()
    .waitFor();
  assert.equal(
    await a
      .frameLocator("#chatwoot-kanban-panel iframe")
      .locator(".card")
      .count(),
    0,
  );
  await a.locator("aside .cursor-col-resize").dblclick();
  await pause(1300);
  assert.equal(await a.locator("#chatwoot-kanban-panel").count(), 1);
  const left = await a
    .locator("#chatwoot-kanban-panel")
    .evaluate((x) => parseFloat(x.style.left));
  assert.ok(left < 100);
  await a.locator("aside .cursor-col-resize").dblclick();
  await pause(1300);
  await a.setViewportSize({ width: 1200, height: 800 });
  await pause(300);
  await a.keyboard.press("Escape");
  assert.equal(await a.locator("#chatwoot-kanban-panel").count(), 0);
  console.log("OK troca de conta, item único e fechamento por Escape");
  console.log("PAGEERRORS", errors);
  await browser.close();
})().catch((e) => {
  console.error(e.stack);
  process.exit(1);
});
