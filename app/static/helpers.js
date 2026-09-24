(function (root) {
  const helpers = {
    money: (cents) =>
      new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
      }).format(Number(cents) / 100),
    moneyInputCents: (value) => Number(String(value).replace(/\D/g, "").replace(/^0+/, "").slice(0, 11) || 0),
    dateBR: (value) =>
      value ? String(value).slice(0, 10).split("-").reverse().join("/") : "—",
    validNavigation: (data, account) =>
      data?.event === "kanban:navigate" &&
      String(data.account) === String(account) &&
      /^(conversations|contacts)$/.test(data.resource) &&
      Number.isSafeInteger(data.id) &&
      data.id > 0,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = helpers;
  else root.KanbanHelpers = helpers;
})(typeof window === "undefined" ? globalThis : window);
