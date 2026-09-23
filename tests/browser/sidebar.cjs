const { email, password } = require("./credentials.cjs");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const root = process.env.CHATWOOT_URL || "http://localhost:3000";
const menu = "#chatwoot-kanban-menu";
const header = `${menu} [data-pipeline-header]`;
const child = (key) => `${menu} [data-pipeline-page=${key}]`;
(async () => {
  const browser = await chromium.launch({
    executablePath:
      process.env.CHROME_PATH ||
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      colorScheme: "light",
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(root + "/app/login");
    await page.locator("[name=email_address]").fill(email);
    await page.locator("[type=password]").fill(password);
    await page.locator("[type=submit]").click();
    await page.locator("aside nav").waitFor();
    if (!(await page.locator("#sidebar-account-switcher").count()))
      await page.locator("aside .cursor-col-resize").dblclick();
    await page.locator(`${header} .truncate`).waitFor();
    await page.evaluate(() => localStorage.setItem("color_scheme", "auto"));
    await page.reload();
    await page.locator(header).waitFor();
    if ((await page.locator(header).getAttribute("aria-expanded")) !== "true")
      await page.locator(header).click();
    console.log("Menu e sessão carregados");
    async function position(part = "contacts", after = true) {
      assert.equal(
        await page.locator(menu).evaluate(
          (node, { part, after }) => {
            const list = node.parentElement;
            let target =
              list.querySelector(`a[href*="/${part}"]`) ||
              list.querySelector(".i-lucide-contact");
            while (target && target.parentElement !== list)
              target = target.parentElement;
            return after
              ? target?.nextElementSibling === node
              : node.nextElementSibling === target;
          },
          { part, after },
        ),
        true,
        `Posição relativa a ${part}`,
      );
    }
    await position();
    assert.equal(
      await page.locator(`${menu} [href], ${menu} router-link`).count(),
      0,
    );
    assert.equal(await page.locator(`${menu} svg`).count(), 3);
    const nativeActive = page.locator("aside nav a[aria-current=page]").first();
    const activeClass = await nativeActive.getAttribute("class");
    const activeHref = await nativeActive.getAttribute("href");
    const route = page.url();
    await page.locator(child("kanban")).click();
    await page
      .frameLocator("#chatwoot-kanban-panel iframe")
      .locator(".column")
      .first()
      .waitFor();
    assert.match(
      await page.locator("#chatwoot-kanban-panel iframe").getAttribute("src"),
      /^\/kanban\?account=\d+$/,
    );
    assert.equal(
      await page.locator(child("kanban")).getAttribute("aria-current"),
      "page",
    );
    for (const cls of [
      "active",
      "text-n-slate-12",
      "bg-n-alpha-2",
      "router-link-exact-active",
    ])
      assert.ok(
        (await page.locator(child("kanban")).getAttribute("class"))
          .split(" ")
          .includes(cls),
      );
    assert.equal(
      await page
        .locator(`aside nav a[href="${activeHref}"]`)
        .getAttribute("aria-current"),
      null,
    );
    assert.equal(page.url(), route);
    const handle = await page.locator("aside .cursor-col-resize").boundingBox();
    const dragY = handle.y + handle.height / 2;
    await page.mouse.move(handle.x + handle.width / 2, dragY);
    await page.mouse.down();
    await page.mouse.move(handle.x + 65, dragY, { steps: 8 });
    await page.mouse.up();
    await page.waitForFunction(
      () =>
        Math.abs(
          document
            .querySelector("#chatwoot-kanban-panel")
            .getBoundingClientRect().left -
            document.querySelector("aside").getBoundingClientRect().right,
        ) < 1,
    );
    const resized = await page
      .locator("aside .cursor-col-resize")
      .boundingBox();
    await page.mouse.move(resized.x + resized.width / 2, dragY);
    await page.mouse.down();
    await page.mouse.move(handle.x + handle.width / 2, dragY, { steps: 8 });
    await page.mouse.up();
    await page.keyboard.press("Escape");
    await page.locator("#chatwoot-kanban-panel").waitFor({ state: "detached" });
    assert.equal(
      await page
        .locator(`aside nav a[href="${activeHref}"]`)
        .getAttribute("class"),
      activeClass,
    );
    assert.equal(
      await page
        .locator(`aside nav a[href="${activeHref}"]`)
        .getAttribute("aria-current"),
      "page",
    );
    await page.locator(header).focus();
    await page.keyboard.press("Enter");
    assert.equal(
      await page.evaluate(() => localStorage.getItem("bee-pipeline-open")),
      "false",
    );
    await page.reload();
    await page.locator(header).waitFor();
    assert.equal(
      await page.locator(header).getAttribute("aria-expanded"),
      "false",
    );
    await page.locator(header).click();
    fs.mkdirSync(".local", { recursive: true });
    const measurements = [];
    for (const theme of ["light", "dark"]) {
      console.log("Tema", theme);
      await page.emulateMedia({ colorScheme: theme });
      await page.waitForFunction(
        (dark) => document.body.classList.contains("dark") === dark,
        theme === "dark",
      );
      const result = await page.locator(header).evaluate((node) => {
        const native = document.querySelector(
          'aside nav [name="Conversation"]',
        );
        const neutral = document.querySelector('aside nav [name="Captain"]');
        const properties = [
          "fontFamily",
          "fontSize",
          "lineHeight",
          "height",
          "paddingTop",
          "paddingRight",
          "paddingBottom",
          "paddingLeft",
          "gap",
          "borderRadius",
        ];
        const read = (element) =>
          Object.fromEntries(
            properties.map((key) => [key, getComputedStyle(element)[key]]),
          );
        return {
          pipeline: read(node),
          native: read(native),
          colors: [
            getComputedStyle(node).color,
            getComputedStyle(neutral).color,
          ],
          icons: [
            node.querySelector("svg").getBoundingClientRect().width,
            native.querySelector(".size-4").getBoundingClientRect().width,
          ],
        };
      });
      assert.deepEqual(result.pipeline, result.native);
      assert.equal(result.colors[0], result.colors[1]);
      assert.deepEqual(result.icons, [16, 16]);
      measurements.push({ theme, ...result });
      await page.locator('aside nav [name="Captain"]').hover();
      const hover = await page
        .locator('aside nav [name="Captain"]')
        .evaluate((n) => getComputedStyle(n).backgroundColor);
      await page.locator(header).hover();
      assert.equal(
        await page
          .locator(header)
          .evaluate((n) => getComputedStyle(n).backgroundColor),
        hover,
      );
      await page.mouse.move(900, 700);
      await page.screenshot({ path: `.local/pipeline-${theme}.png` });
      await page.locator(child("metricas")).click();
      const metrics = page.frameLocator("#chatwoot-kanban-panel iframe");
      await metrics.getByRole("heading", { name: "Métricas" }).waitFor();
      await page.waitForFunction(
        (dark) =>
          document
            .querySelector("#chatwoot-kanban-panel iframe")
            .contentDocument.body.classList.contains("dark") === dark,
        theme === "dark",
      );
      await metrics.locator("body").press("Escape");
      await page
        .locator("#chatwoot-kanban-panel")
        .waitFor({ state: "detached" });
      await page.locator("aside .cursor-col-resize").dblclick();
      await page.waitForFunction(
        () =>
          !document.querySelector(
            "#chatwoot-kanban-menu [data-pipeline-header] .truncate",
          ),
      );
      await position();
      assert.equal(
        await page.locator(header).evaluate((n) => n.textContent.trim()),
        "",
      );
      assert.equal(
        await page
          .locator(header)
          .evaluate((n) => n.getBoundingClientRect().width),
        40,
      );
      await page.screenshot({ path: `.local/pipeline-${theme}-recolhido.png` });
      await page.locator(header).click();
      await page.locator(child("metricas")).click();
      await metrics.getByRole("heading", { name: "Métricas" }).waitFor();
      await metrics.locator("body").press("Escape");
      await page.locator("aside .cursor-col-resize").dblclick();
      await page.locator(`${header} .truncate`).waitFor();
    }
    console.log("Reinjeção e fallbacks");
    // Recriação do menu e fallbacks sem depender de textos traduzidos.
    await page.locator(menu).evaluate((n) => n.remove());
    await page.locator(header).waitFor();
    await position();
    for (const [remove, fallback] of [
      ["contacts", "reports"],
      ["reports", "settings"],
    ]) {
      await page.evaluate(
        ({ remove, menu }) => {
          const list = document.querySelector("aside nav > ul");
          for (const a of list.querySelectorAll(`a[href*="/${remove}"]`))
            a.removeAttribute("href");
          document.querySelector(menu).remove();
        },
        { remove, menu },
      );
      // Recarregar evita interferir no DOM controlado pelo Vue depois do teste.
      await page.locator(header).waitFor();
      await position(fallback, false);
    }
    await page.reload();
    await page.locator(header).waitFor();
    await page.locator("#sidebar-account-switcher").click();
    await page.locator("#account-2").click();
    await page.waitForURL(/accounts\/2\//);
    await page.locator(child("metricas")).click();
    assert.equal(
      await page.locator("#chatwoot-kanban-panel iframe").getAttribute("src"),
      "/kanban/metricas?account=2",
    );
    await page.locator("#sidebar-account-switcher").click();
    await page.locator("#account-1").click();
    await page.waitForURL(/accounts\/1\//);
    await page.locator(header).waitFor();
    assert.equal(await page.locator("#chatwoot-kanban-panel").count(), 0);
    assert.equal(await page.locator(menu).count(), 1);
    // Primeira carga recolhida: sem folhas nativas montadas pelo Vue.
    await page.locator("aside .cursor-col-resize").dblclick();
    await page.reload();
    await page.locator(header).waitFor();
    await position();
    await page.locator(header).click();
    await page.locator(child("metricas")).click();
    await page
      .frameLocator("#chatwoot-kanban-panel iframe")
      .getByRole("heading", { name: "Métricas" })
      .waitFor();
    await page.keyboard.press("Escape");
    await page.locator("aside .cursor-col-resize").dblclick();
    assert.deepEqual(errors, []);
    console.log(
      JSON.stringify(
        {
          status: "OK",
          measurements,
          checks: [
            "posição e fallbacks",
            "clonagem e ícones",
            "ativo e restauração",
            "teclado e persistência",
            "temas e hover",
            "recolhimento e primeira carga recolhida",
            "reinjeção sem duplicação",
            "troca de contas",
            "Kanban real e Métricas",
          ],
        },
        null,
        2,
      ),
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
