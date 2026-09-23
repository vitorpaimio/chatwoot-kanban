const { email, password } = require("./credentials.cjs");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const root = process.env.CHATWOOT_URL || "http://localhost:3000";
(async () => {
  const browser = await chromium.launch({
    executablePath:
      process.env.CHROME_PATH ||
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1600, height: 1000 },
      colorScheme: "light",
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(root + "/app/accounts/1/contacts");
    if (page.url().includes("/login")) {
      await page.locator("[name=email_address]").fill(email);
      await page.locator("[type=password]").fill(password);
      await page.locator("[type=submit]").click();
    }
    await page.locator("aside nav").waitFor();
    if (!(await page.locator("#sidebar-account-switcher").count()))
      await page.locator("aside .cursor-col-resize").dblclick();
    if (
      (await page
        .locator("#sidebar-account-switcher")
        .getAttribute("data-account-id")) !== "1"
    ) {
      await page.locator("#sidebar-account-switcher").click();
      await page.locator("#account-1").click();
      await page.waitForURL(/accounts\/1\//);
    }
    await page.goto(root + "/app/accounts/1/contacts");
    await page.locator("aside nav").waitFor();
    await page.locator("header.sticky").first().waitFor();
    const nativeHeader = await page
      .locator("header.sticky")
      .first()
      .evaluate((n) => ({
        height: n.getBoundingClientRect().height,
        titleSize: getComputedStyle(n.querySelector(".text-xl")).fontSize,
      }));
    await page.evaluate(() => localStorage.setItem("color_scheme", "auto"));
    await page.reload();
    await page.locator("[data-pipeline-header]").waitFor();
    if (
      (await page
        .locator("[data-pipeline-header]")
        .getAttribute("aria-expanded")) !== "true"
    )
      await page.locator("[data-pipeline-header]").click();
    await page.locator("[data-pipeline-page=kanban]").click();
    const frame = page.frameLocator("#chatwoot-kanban-panel iframe");
    await frame.locator(".card").first().waitFor();
    const realFrame = page.frames().find((f) => /\/kanban\?/.test(f.url()));
    await realFrame.waitForFunction(() => !metadataLoading);
    console.log("Quadro real carregado");
    assert.equal(await frame.locator("#close,#reports,.eyebrow").count(), 0);
    assert.equal(await frame.locator("#retry").isVisible(), false);
    assert.equal(await frame.locator("#connection").textContent(), "");
    assert.equal(
      await frame
        .locator(".column")
        .first()
        .evaluate((n) => n.getBoundingClientRect().width),
      292,
    );
    const card = frame.locator(".card").first();
    const cardTitle = await card.locator(".card-name").textContent();
    await card.click();
    assert.equal(await frame.locator("#dialog-title").textContent(), cardTitle);
    await frame.locator("#dialog-close").click();
    await card.hover();
    await card.locator(".task-action").click();
    await frame
      .getByLabel("Tarefa", { exact: true })
      .fill("Rascunho preservado na troca de tema");
    await page.emulateMedia({ colorScheme: "dark" });
    await realFrame.waitForFunction(() =>
      document.body.classList.contains("dark"),
    );
    assert.equal(
      await frame.getByLabel("Tarefa", { exact: true }).inputValue(),
      "Rascunho preservado na troca de tema",
    );
    await frame.locator("#dialog-close").click();
    await frame.locator("#manage").click();
    assert.match(
      await frame.locator("#dialog-title").textContent(),
      /^Gerenciar/,
    );
    await frame.locator("#dialog-close").click();
    await frame.locator("#more-actions summary").click();
    await frame.getByRole("button", { name: "Histórico", exact: true }).click();
    await frame.locator("#dialog-content .history-item").first().waitFor();
    await frame.locator("#dialog-close").click();
    for (const theme of ["light", "dark"]) {
      await page.emulateMedia({ colorScheme: theme });
      await realFrame.waitForFunction(
        (dark) => document.body.classList.contains("dark") === dark,
        theme === "dark",
      );
      const style = await realFrame.evaluate(() => {
        const p = parent.getComputedStyle(parent.document.body),
          r = getComputedStyle(document.documentElement);
        return {
          font: r.fontFamily,
          parentFont: p.fontFamily,
          fonts: [...parent.document.fonts].every((face) =>
            document.fonts.has(face),
          ),
          bg: getComputedStyle(document.body).backgroundColor,
          surface: r.getPropertyValue("--surface-1").trim(),
          parentSurface: p.getPropertyValue("--surface-1").trim(),
          header: document.querySelector(".page-header").getBoundingClientRect()
            .height,
          title: getComputedStyle(document.querySelector(".picker-title"))
            .fontSize,
          button: getComputedStyle(document.querySelector("#add-card"))
            .backgroundColor,
          brand: r.getPropertyValue("--blue-9").trim(),
          rootCustom: [
            ...parent.getComputedStyle(parent.document.documentElement),
          ]
            .filter((k) => k.startsWith("--"))
            .every(
              (k) =>
                document.documentElement.style.getPropertyValue(k).trim() ===
                p.getPropertyValue(k).trim(),
            ),
        };
      });
      assert.equal(style.font, style.parentFont);
      assert.equal(style.fonts, true);
      assert.equal(style.surface, style.parentSurface);
      assert.equal(style.rootCustom, true);
      assert.equal(style.header, nativeHeader.height);
      assert.equal(style.title, nativeHeader.titleSize);
      await page.mouse.move(1500, 950);
      await page.screenshot({ path: `.local/quadro-chatwoot-${theme}.png` });
      console.log(theme, JSON.stringify(style));
    }
    // Exercitar também a mudança em html.dark pedida no contrato, sem trocar de rota.
    await page.emulateMedia({ colorScheme: "light" });
    await realFrame.waitForFunction(
      () => !document.body.classList.contains("dark"),
    );
    await page.evaluate(() => document.documentElement.classList.add("dark"));
    await realFrame.waitForFunction(() =>
      document.body.classList.contains("dark"),
    );
    await page.evaluate(() =>
      document.documentElement.classList.remove("dark"),
    );
    await realFrame.waitForFunction(
      () => !document.body.classList.contains("dark"),
    );
    await page.locator("[data-pipeline-page=metricas]").click();
    await page
      .frameLocator("#chatwoot-kanban-panel iframe")
      .locator("table")
      .waitFor();
    console.log("Métricas no menu lateral OK");
    // Casos de borda isolados no transporte do navegador. Capturas acima usam dados reais.
    const original = await (
      await page.request.get(root + "/kanban/board?account=1")
    ).json();
    const fixture = structuredClone(original),
      first = fixture.cards[0];
    Object.assign(first, {
      name: 'MARIA <img src=x onerror="window.__xss=1">',
      phone: "+55 11 99999-0000",
      thumbnail: "javascript:alert(1)",
      labels: ["Prioridade", "Cliente", "WhatsApp", "Quarta", "Quinta"],
      value_cents: 0,
      sync_status: "failed",
      task_id: 999,
      task_version: 1,
      message: '<svg onload="window.__xss=1">',
      due_date: "2026-09-22",
      due_state: "overdue",
      last_activity_at: new Date(Date.now() - 300000).toISOString(),
      assignee_name: "Ana <script>alert(1)</script>",
    });
    const second = structuredClone(first);
    Object.assign(second, {
      id: 99999,
      contact_id: 99999,
      name: "João da Silva",
      sync_status: "synced",
      due_state: "today",
      due_date: "2026-09-23",
      value_cents: 125000,
      labels: [],
      message: "Retornar proposta",
    });
    fixture.cards = [first, second];
    await page.route("**/kanban/board?*", (route) =>
      route.fulfill({ json: fixture }),
    );
    await page.route("**/api/v1/accounts/1/labels", (route) =>
      route.fulfill({
        json: {
          payload: [
            { title: "Prioridade", color: "#e64c65" },
            { title: "Cliente", color: "#45a888" },
            { title: "WhatsApp", color: "#2781f6" },
          ],
        },
      }),
    );
    await page.locator("[data-pipeline-page=kanban]").click();
    const edgeFrame = page.frameLocator("#chatwoot-kanban-panel iframe");
    await edgeFrame.locator(".sync-alert").waitFor();
    const ef = page.frames().find((f) => /\/kanban\?/.test(f.url()));
    await ef.waitForFunction(() => !metadataLoading);
    const edgeCard = edgeFrame.locator(`[data-card-id="${first.id}"]`);
    assert.equal(
      await edgeCard.locator(".card-name").textContent(),
      first.name,
    );
    assert.equal(await edgeCard.locator(".tag:not(.more)").count(), 3);
    assert.equal(await edgeCard.locator(".tag.more").textContent(), "+2");
    assert.equal(
      await edgeCard
        .locator(".label-dot")
        .first()
        .evaluate((n) => getComputedStyle(n).backgroundColor),
      "rgb(230, 76, 101)",
    );
    assert.equal(await edgeCard.locator(".card-value").count(), 0);
    assert.match(
      await edgeCard.locator(".last-activity").textContent(),
      /há 5 min/,
    );
    assert.equal(await edgeFrame.locator("#retry").isVisible(), true);
    assert.match(
      await edgeFrame.locator("#sync-count").textContent(),
      /^1 contato/,
    );
    assert.equal(await ef.evaluate(() => window.__xss), undefined);
    assert.equal(
      await edgeCard
        .locator('[onerror],script,img[src^="javascript:"]')
        .count(),
      0,
    );
    const dates = await ef.evaluate(() =>
      ["overdue", "today"].map((state) => {
        const node = document.querySelector(`.task.${state} time`);
        return [
          getComputedStyle(node).color,
          getComputedStyle(document.documentElement)
            .getPropertyValue(state === "overdue" ? "--ruby-11" : "--amber-11")
            .trim(),
        ];
      }),
    );
    for (const [actual, token] of dates)
      assert.equal(actual, `rgb(${token.split(/\s+/).join(", ")})`);
    await edgeFrame.locator("#search").fill("João");
    assert.equal(await edgeFrame.locator(".card").count(), 1);
    await edgeFrame.locator("#search").fill("");
    await edgeFrame.locator("#task-filter").selectOption("today");
    assert.equal(await edgeFrame.locator(".card").count(), 1);
    assert.deepEqual(errors, []);
    console.log(
      "OK: detalhes, tarefa, rascunho, gestão, histórico, temas, variáveis, métricas, etiquetas, datas, falhas, filtros e XSS",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
