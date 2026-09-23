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
