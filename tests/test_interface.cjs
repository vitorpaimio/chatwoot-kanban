const { test } = require("node:test");
const assert = require("node:assert/strict");
const { money, dateBR, validNavigation } = require("../app/static/helpers.js");
test("valor brasileiro conserva centavos", () =>
  assert.match(money(123456), /1\.234,56/));
test("data civil não sofre conversão de fuso", () => {
  assert.equal(dateBR("2026-09-23"), "23/09/2026");
  assert.equal(dateBR("2026-09-23T00:00:00Z"), "23/09/2026");
  assert.equal(dateBR(null), "—");
});
test("navegação recusa conta, recurso e identificador adulterados", () => {
  const valid = {
    event: "kanban:navigate",
    account: 1,
    resource: "contacts",
    id: 3,
  };
  assert.ok(validNavigation(valid, 1));
  assert.ok(!validNavigation(valid, 2));
  assert.ok(!validNavigation({ ...valid, resource: "javascript:alert(1)" }, 1));
  assert.ok(!validNavigation({ ...valid, id: "../settings" }, 1));
});
test("entrada monetária limita centavos e aceita colagem em reais", () => {
  const { moneyInputCents } = require("../app/static/helpers.js");
  assert.equal(moneyInputCents("R$ 1.299,90"), 129990);
  assert.equal(moneyInputCents("999999999999999999999999"), 99999999999);
  assert.equal(moneyInputCents("R$ 0,001"), 1);
  assert.equal(moneyInputCents(""), 0);
});
test("loader monta o menu com a aba oculta, sem requestAnimationFrame", async () => {
  const { readFileSync } = require("node:fs");
  const vm = require("node:vm");
  const source = readFileSync(`${__dirname}/../app/static/loader.js`, "utf8");
  let mutated;
  let lookups = 0;
  const context = {
    location: { pathname: "/app/accounts/1/dashboard" },
    localStorage: { getItem: () => null },
    addEventListener() {},
    requestAnimationFrame() {},
    setTimeout,
    ResizeObserver: class {
      observe() {}
      disconnect() {}
    },
    MutationObserver: class {
      constructor(callback) {
        mutated = callback;
      }
      observe() {}
      disconnect() {}
    },
    document: {
      documentElement: {},
      addEventListener() {},
      querySelector(selector) {
        if (selector === "aside nav") lookups += 1;
        return null;
      },
    },
  };
  context.window = context;
  vm.runInNewContext(source, context);
  assert.equal(lookups, 1);
  mutated();
  await new Promise((resolve) => setTimeout(resolve, 150));
  assert.equal(lookups, 2);
});
