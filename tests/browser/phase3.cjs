// Interface real com API controlada; não substitui certificação no Chatwoot.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
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
  let browser;
  try {
    browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"});
    const page = await browser.newPage({hasTouch: true, viewport: {width: 1200, height: 900}});
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.addInitScript(() => {
      window.streams = [];
      window.EventSource = class extends EventTarget {
        constructor() { super(); window.stream = this; window.streams.push(this); }
        close() { this.closed = true; }
      };
    });
    const cards = Array.from({length: 120}, (_, i) => ({
      id: i + 1, contact_id: i + 10, funnel_id: 1, stage_id: 1,
      name: `Contato ${String(i + 1).padStart(3, "0")}`, labels: ["Cliente"],
      value_cents: 1000, version: 1, sync_status: "synced", conversation_id: null,
      stage_entered_at: "2026-09-20T12:00:00Z", assignee_id: 3, assignee_name: "Ana",
      task_id: i + 1, task_version: 1, message: "Retornar", due_date: "2026-12-31",
      due_state: "active", task_assigned_to: 3, task_assignee_name: "Ana",
    }));
    const base = {
      funnels: [{id: 1, name: "Principal"}],
      stages: [{id: 1, funnel_id: 1, name: "Novo", kind: "open", color: "#6366f1"},
        {id: 2, funnel_id: 1, name: "Proposta", kind: "open", color: "#6366f1"}],
      agents: [{id: 3, name: "Ana"}, {id: 4, name: "Bruno"}], contacts: [],
    };
    const queries = [], writes = [];
    let conflict = false, revoked = false, removedFunnel = false;
    await page.route("**/kanban/session?*", route => route.fulfill({json: {
      id: 3, name: "Ana", role: "agent", activation: {enabled: true, activation_status: "ready"},
    }}));
    await page.route("**/kanban/board?*", route => {
      const query = new URL(route.request().url()).searchParams;
      queries.push(Object.fromEntries(query));
      const offset = Number(query.get("offset") || 0);
      const stage = Number(query.get("stage_id") || 0);
      const limit = Number(query.get("limit") || 50);
      if (removedFunnel) {
        const selected = query.get("funnel_id") === "2";
        return route.fulfill({json: {...base,
          funnels: [{id: 2, name: "Sobrevivente"}],
          stages: [{id: 3, funnel_id: 2, name: "Novo", kind: "open", color: "#6366f1"}],
          cards: selected ? [{...cards[0], id: 1001, funnel_id: 2, stage_id: 3}] : [],
          totals: selected ? [{stage_id: 3, count: 1, value_cents: 1000}] : [],
        }});
      }
      return route.fulfill({json: {...base, cards: revoked ? [] : cards.slice(offset, offset + limit),
        totals: [{stage_id: 1, count: revoked ? 0 : 120, value_cents: 120000},
          ...(stage ? [] : [{stage_id: 2, count: 0, value_cents: 0}])],
      }});
    });
    await page.route("**/kanban/cards/*?*", route => {
      if (route.request().method() === "GET") return route.fulfill({status: revoked ? 404 : 200,
        json: revoked ? {detail: "Registro não encontrado nesta conta"} : cards[0]});
      writes.push(route.request().postDataJSON());
      return route.fulfill({status: conflict ? 409 : 200,
        json: conflict ? {detail: "Cartão alterado por outra pessoa; atualize"} : {ok: true}});
    });
    await page.route("**/kanban/contacts/*/task?*", route => {
      writes.push(route.request().postDataJSON());
      return route.fulfill({json: {ok: true}});
    });
    await page.goto(`http://127.0.0.1:${server.address().port}/kanban?account=1`);
    await page.locator("[data-card-id='1']").waitFor();
    assert.equal(await page.locator(".card").count(), 50);
    const summary = await page.locator("#summary").textContent();
    assert.match(summary, /120 negociações/);
    assert.equal(queries[0].limit, "1");
    assert.equal(queries[0].funnel_id, undefined);
    assert.equal(queries.at(-1).funnel_id, "1");
    assert.equal(queries.at(-1).limit, "50");
    // Arrastar ao fim da página deve inserir antes de 51, não após 120.
    const transfer = await page.evaluateHandle(() => new DataTransfer());
    await page.locator("[data-card-id='1']").dispatchEvent("dragstart", {dataTransfer: transfer});
    await page.locator("[data-card-id='50']").scrollIntoViewIfNeeded();
    const dragSaved = page.waitForResponse(response => response.request().method() === "PATCH");
    await page.evaluate(transfer => {
      const column = document.querySelector("[data-stage-id='1']");
      const last = column.querySelector("[data-card-id='50']").getBoundingClientRect();
      const options = {bubbles: true, cancelable: true, dataTransfer: transfer,
        clientX: last.left + last.width / 2, clientY: last.bottom + 2};
      column.dispatchEvent(new DragEvent("dragover", options));
      column.dispatchEvent(new DragEvent("drop", options));
    }, transfer);
    await dragSaved;
    assert.equal(writes.at(-1).before_id, 51);
    assert.equal(writes.at(-1).stage_id, 1);
    assert.ok(queries.some(query => query.stage_id === "1" && query.offset === "50"));
    await page.waitForFunction(() => !document.getElementById("board").hasAttribute("aria-busy"));
    await transfer.dispose();
    await page.getByRole("button", {name: "Próximos", exact: true}).click();
    await page.locator("[data-card-id='51']").waitFor();
    assert.equal(await page.locator(".card").count(), 50);
    assert.equal(await page.locator("#summary").textContent(), summary);
    assert.equal(queries.at(-1).offset, "50");
    assert.equal(queries.at(-1).stage_id, "1");
    await page.getByRole("button", {name: "Próximos", exact: true}).click();
    await page.locator("[data-card-id='101']").waitFor();
    assert.equal(await page.locator(".card").count(), 20);
    assert.equal(await page.getByRole("button", {name: "Próximos", exact: true}).isDisabled(), true);
    assert.equal(await page.locator("#summary").textContent(), summary);
    async function changeFilter(selector, value, select = false) {
      const response = page.waitForResponse("**/kanban/board?*");
      if (select) await page.locator(selector).selectOption(value);
      else await page.locator(selector).fill(value);
      await response;
    }
    await changeFilter("#search", "Maria");
    assert.equal(queries.at(-1).search, "Maria");
    assert.equal(queries.at(-1).offset, "0");
    await changeFilter("#assignee", "4", true);
    await changeFilter("#label", "Cliente", true);
    await changeFilter("#task-filter", "active", true);
    assert.equal(queries.at(-1).assignee_id, "4");
    assert.equal(queries.at(-1).label, "Cliente");
    assert.equal(queries.at(-1).task, "active");
    await page.locator("[data-card-id='1']").press("Enter");
    await page.getByLabel("Valor em reais").fill("123456");
    let response = page.waitForResponse("**/kanban/board?*");
    await page.evaluate(() => window.stream.dispatchEvent(new Event("change")));
    await response;
    assert.equal(await page.locator("#dialog").evaluate(node => node.open), true);
    assert.match(await page.getByLabel("Valor em reais").inputValue(), /1\.234,56/);
    await page.getByLabel(/^Etapa/).selectOption("2");
    conflict = true;
    await page.locator("#dialog-save").tap();
    await page.locator("#dialog-error").waitFor();
    assert.equal(writes.at(-1).stage_id, 2);
    assert.equal(await page.locator("#dialog").evaluate(node => node.open), true);
    assert.match(await page.getByLabel("Valor em reais").inputValue(), /1\.234,56/);
    conflict = false;
    response = page.waitForResponse("**/kanban/board?*");
    await page.locator("#dialog-save").tap();
    await response;
    await page.locator("[data-card-id='1'] .task-action").tap();
    await page.getByLabel(/^Responsável da tarefa/).selectOption("4");
    response = page.waitForResponse("**/kanban/board?*");
    await page.locator("#dialog-save").tap();
    await response;
    assert.equal(writes.at(-1).assigned_to, 4);
    assert.equal(writes.at(-1).version, 1);
    await page.locator("[data-card-id='1']").press("Enter");
    revoked = true;
    await page.evaluate(() => window.stream.dispatchEvent(new Event("change")));
    await page.waitForFunction(() => !document.getElementById("dialog").open);
    assert.equal(await page.locator(".card").count(), 0);
    const streams = await page.evaluate(() => window.streams.length);
    await page.evaluate(() => window.stream.onerror());
    await page.waitForFunction(count => window.streams.length > count, streams, {timeout: 5000});
    assert.equal(await page.evaluate(() => window.streams.at(-2).closed), true);
    // A remoção do funil atual precisa consultar novamente o novo selecionado.
    revoked = false;
    removedFunnel = true;
    const queryCount = queries.length;
    await page.evaluate(() => window.stream.dispatchEvent(new Event("change")));
    await page.locator("[data-card-id='1001']").waitFor();
    const fallbackQueries = queries.slice(queryCount);
    assert.equal(fallbackQueries[0].funnel_id, "1");
    assert.equal(fallbackQueries.at(-1).funnel_id, "2");
    assert.match(await page.locator("#summary").textContent(), /1 negociação/);
    assert.equal(await page.locator(".card").count(), 1);
    assert.deepEqual(errors, []);
    console.log("Fase 3: paginação, totais, filtros, tarefa, teclado/toque, conflito, rascunho, revogação, reconexão, drag paginado e funil arquivado aprovados");
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
