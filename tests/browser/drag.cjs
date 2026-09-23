const { email, password } = require("./credentials.cjs");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({
    executablePath:
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
  });
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    await page.goto("http://localhost:3000/app/login");
    await page.locator("[name=email_address]").fill(email);
    await page.locator("[type=password]").fill(password);
    await page.locator("[type=submit]").click();
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
      await page
        .locator('#sidebar-account-switcher[data-account-id="1"]')
        .waitFor();
    }
    await page.locator("#chatwoot-kanban-menu").waitFor();
    if (
      (await page
        .locator("[data-pipeline-header]")
        .getAttribute("aria-expanded")) !== "true"
    )
      await page.locator("[data-pipeline-header]").click();
    await page.getByRole("button", { name: "Kanban", exact: true }).click();
    const frame = page.frameLocator("#chatwoot-kanban-panel iframe");
    await frame.locator(".card").first().waitFor();
    await page
      .frames()
      .find((f) => /\/kanban\?/.test(f.url()))
      .waitForFunction(() => !metadataLoading);
    const data = await (
      await page.request.get("http://localhost:3000/kanban/board?account=1")
    ).json();
    const main = data.funnels.find((f) => f.is_primary);
    const card = data.cards.find(
      (c) =>
        c.funnel_id === main.id && c.name.startsWith("Cliente de teste Kanban"),
    );
    const target = data.stages.find(
      (s) => s.funnel_id === main.id && s.id !== card.stage_id,
    );
    await frame
      .locator(`[data-card-id="${card.id}"]`)
      .dragTo(frame.locator(`[data-stage-id="${target.id}"] .column-head`));
    let moved;
    for (let i = 0; i < 20; i++) {
      const state = await (
        await page.request.get("http://localhost:3000/kanban/board?account=1")
      ).json();
      moved = state.cards.find((c) => c.id === card.id);
      if (moved.stage_id === target.id) break;
      await page.waitForTimeout(500);
    }
    assert.equal(moved.stage_id, target.id);
    assert.equal(moved.version, card.version + 1);
    await page.evaluate(() =>
      window.postMessage({ event: "kanban:close" }, location.origin),
    );
    await page.waitForTimeout(100);
    assert.equal(await page.locator("#chatwoot-kanban-panel").count(), 1);
    const restore = await page.request.patch(
      `http://localhost:3000/kanban/cards/${card.id}?account=1`,
      { data: { version: moved.version, stage_id: card.stage_id } },
    );
    assert.ok(restore.ok());
    console.log(
      "OK arrastar no quadro real e rejeitar mensagem de janela incorreta",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
