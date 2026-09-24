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
    let revoked = false;
    const board = { funnels: [{id: 1, name: "Principal"}], stages: [{id: 1, funnel_id: 1, name: "Novo", color: "#6366f1", kind: "open"}], contacts: [], cards: [{id: 1, contact_id: 10, funnel_id: 1, stage_id: 1, name: "Contato teste", labels: [], value_cents: 0, version: 1, sync_status: "synced", conversation_id: null}] };
    await page.route("**/kanban/session?*", route => route.fulfill({json: {role: "agent", activation: {enabled: true, activation_status: "ready"}}}));
    await page.route("**/kanban/board?*", route => route.fulfill({json: revoked ? {...board, cards: []} : board}));
    await page.route("**/kanban/cards/1?*", route => route.fulfill({
      status: revoked ? 404 : 200, json: revoked ? {detail: "Revogado"} : board.cards[0]
    }));
    await page.goto(`http://127.0.0.1:${server.address().port}/kanban?account=1`);
    await page.locator("[data-card-id='1']").waitFor();
    assert.equal(await page.locator("[data-card-id='1'] .channel").count(), 0);
    await page.waitForFunction(() => Boolean(window.stream));
    await page.locator("[data-card-id='1']").press("Enter");
    await page.getByLabel("Valor em reais").fill("123456");
    board.cards[0].sync_status = "pending";
    const refresh = page.waitForResponse("**/kanban/board?*");
    await page.evaluate(() => window.stream.dispatchEvent(new Event("change")));
    await refresh;
    assert.equal(await page.locator("#dialog").evaluate(node => node.open), true);
    assert.match(await page.getByLabel("Valor em reais").inputValue(), /1\.234,56/);
    // Uma revogação continua removendo detalhes, mesmo durante uma edição.
    revoked = true;
    await page.evaluate(() => window.stream.dispatchEvent(new Event("change")));
    await page.locator("[data-card-id='1']").waitFor({state: "detached"});
    assert.equal(await page.locator("#dialog").evaluate(node => node.open), false);
    await page.evaluate(() => window.stream.dispatchEvent(new Event("expired")));
    assert.equal(await page.locator("[data-card-id]").count(), 0);
    assert.deepEqual(errors, []);
    console.log("Frontend: cartão sem canal e remoção após revogação/expiração aprovados");
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
