"use strict";
// Lista simples das tarefas abertas (ADR-045). Abrir uma linha leva ao cartão no Kanban.
const $ = (id) => document.getElementById(id);
const account = Number(new URLSearchParams(location.search).get("account"));
const { dateBR } = window.KanbanHelpers;
const PAGE = 100;
const DUE = { overdue: "Vencida", today: "Vence hoje", active: "Agendada" };
const EMPTY = {
  "": "Nenhuma tarefa aberta. Crie tarefas pelo cartão da negociação no Kanban.",
  overdue: "Nenhuma tarefa vencida.",
  today: "Nenhuma tarefa vence hoje.",
  active: "Nenhuma tarefa agendada para os próximos dias.",
};
let state = "",
  offset = 0,
  generation = 0,
  live;
const el = (tag, text, cls) => {
  const node = document.createElement(tag);
  if (text != null) node.textContent = String(text);
  if (cls) node.className = cls;
  return node;
};
async function api(path) {
  const url = new URL("/kanban" + path, location.origin);
  url.searchParams.set("account", account);
  const response = await fetch(url, {
    credentials: "same-origin",
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) {
    const error = new Error(`Falha ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}
const status = (text) => ($("status").textContent = text);
function openCard(task) {
  parent.postMessage(
    { event: "kanban:open-card", account, id: task.card_id },
    location.origin,
  );
}
function row(task) {
  const tr = el("tr", null, "task-row");
  tr.tabIndex = 0;
  tr.dataset.cardId = task.card_id;
  tr.setAttribute(
    "aria-label",
    `${task.descricao} — ${task.name}. Abrir negociação no Kanban`,
  );
  const deal = el("td");
  const stage = el("span", null, "deal-stage");
  const dot = el("span", null, "dot");
  if (/^#[\da-f]{3,8}$/i.test(task.stage_color || ""))
    dot.style.background = task.stage_color;
  stage.append(dot, el("span", `${task.funnel} · ${task.stage}`));
  deal.append(el("span", task.name, "deal-name"), stage);
  const due = el("td");
  const time = el("time", dateBR(task.vencimento), `due ${task.due_state}`);
  time.dateTime = task.vencimento;
  due.append(time, el("span", DUE[task.due_state] || "", `due-label ${task.due_state}`));
  const what = el("td");
  what.append(el("span", task.descricao, "task-text"));
  tr.append(
    what,
    deal,
    due,
    el("td", task.assignee_name || "Sem responsável", task.assignee_name ? "" : "muted"),
  );
  tr.onclick = () => openCard(task);
  tr.onkeydown = (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openCard(task);
    }
  };
  return tr;
}
async function load(reset = true) {
  const current = ++generation;
  if (reset) {
    offset = 0;
    status("Carregando tarefas…");
  }
  try {
    const query = new URLSearchParams({ state, offset: String(offset), limit: String(PAGE) });
    const data = await api(`/tasks?${query}`);
    if (current !== generation) return;
    for (const [key, value] of Object.entries(data.counts))
      document.querySelector(`[data-count="${key}"]`).textContent = `(${value})`;
    const body = $("tasks").tBodies[0];
    if (reset) body.replaceChildren();
    body.append(...data.tasks.map(row));
    offset += data.tasks.length;
    const total = state ? data.counts[state] : data.counts.total;
    $("tasks").hidden = !offset;
    $("more").hidden = offset >= total;
    status(offset ? "" : EMPTY[state]);
    if (!live) listen();
  } catch (error) {
    if (current !== generation) return;
    $("tasks").hidden = true;
    $("more").hidden = true;
    status(
      error.status === 403
        ? "O Pipeline não está ativo nesta conta. Abra o Kanban para ativá-lo."
        : error.status === 401
          ? "Sessão expirada. Entre novamente no Chatwoot."
          : "Não foi possível carregar as tarefas. Tente novamente.",
    );
  }
}
function listen() {
  // Mesmo canal do quadro: qualquer mudança na conta recarrega a lista.
  let timer;
  live = new EventSource(`/kanban/events?account=${account}`);
  live.addEventListener("change", () => {
    clearTimeout(timer);
    timer = setTimeout(() => load().catch(() => {}), 300);
  });
  window.addEventListener("pagehide", () => live.close(), { once: true });
}
const tabs = [...document.querySelectorAll("[role=tab]")];
function select(tab) {
  for (const t of tabs) {
    const active = t === tab;
    t.setAttribute("aria-selected", String(active));
    t.tabIndex = active ? 0 : -1;
  }
  state = tab.dataset.state;
  load();
}
for (const tab of tabs) {
  tab.tabIndex = tab.getAttribute("aria-selected") === "true" ? 0 : -1;
  tab.onclick = () => select(tab);
  tab.onkeydown = (event) => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault();
    const next = tabs[(tabs.indexOf(tab) + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
    next.focus();
    select(next);
  };
}
$("more").onclick = () => load(false);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape")
    parent.postMessage({ event: "kanban:close" }, location.origin);
});
load();
