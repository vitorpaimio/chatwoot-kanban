"use strict";
const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const account = Number(params.get("account"));
const compact = params.has("compact");
let user,
  data = { funnels: [], stages: [], cards: [], contacts: [] },
  selected,
  contactContext;
let authorizationEpoch = 0;
let loadGeneration = 0;
let dialogGeneration = 0;
let editing = false,
  pendingRefresh = false,
  dragged,
  moving = false,
  landingCard,
  landingTimer,
  reconnectTimer;
const { money, dateBR } = window.KanbanHelpers;
// Funil escolhido por último: o primeiro carregamento já pede a página certa.
const funnelKey = `kanban-funnel-${account}`;
try {
  selected = Number(localStorage.getItem(funnelKey)) || undefined;
} catch {
  /* Armazenamento pode estar desabilitado. */
}
function rememberFunnel(id) {
  try {
    localStorage.setItem(funnelKey, String(id));
  } catch {
    /* Armazenamento pode estar desabilitado. */
  }
}
const el = (tag, text, cls) => {
  const n = document.createElement(tag);
  if (text != null) n.textContent = String(text);
  if (cls) n.className = cls;
  return n;
};
const metadata = {
  labels: new Map(),
  agents: new Map(),
  inboxes: new Map(),
};
let metadataLoaded = false,
  metadataLoading;
function icon(name) {
  const paths = {
    check: ["m5 12 4 4L19 6"],
    trash: ["M3 6h18", "M9 6V3h6v3", "m5 6 1 15h12l1-15", "M10 10v7M14 10v7"],
    history: ["M3 12a9 9 0 1 0 3-6.7", "M3 3v6h6", "M12 7v5l3 2"],
    link: ["M10 13a5 5 0 0 0 7 .1l3-3a5 5 0 0 0-7-7l-2 2", "M14 11a5 5 0 0 0-7-.1l-3 3a5 5 0 0 0 7 7l2-2"],
    task: [
      "M9 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-4",
      "m9 14 2 2L21 6",
      "M9 3h6v4H9z",
    ],
    alert: [
      "m10.3 3.9-8 14a2 2 0 0 0 1.7 3h16a2 2 0 0 0 1.7-3l-8-14a2 2 0 0 0-3.4 0",
      "M12 9v4",
      "M12 17h.01",
    ],
    chat: [
      "M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8z",
    ],
    mail: [
      "M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
      "m22 6-10 7L2 6",
    ],
    phone: [
      "M22 16.9v3a2 2 0 0 1-2.2 2A19.8 19.8 0 0 1 3.1 5.2 2 2 0 0 1 5.1 3h3a2 2 0 0 1 2 1.7l.4 2.8a2 2 0 0 1-.6 1.7L8.6 10.5a16 16 0 0 0 4.9 4.9l1.3-1.3a2 2 0 0 1 1.7-.6l2.8.4a2 2 0 0 1 2.7 3z",
    ],
    web: ["M3 3h18v18H3z", "M3 8h18", "M7 5h.01M10 5h.01"],
    edit: ["M12 20h9", "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"],
    archive: ["M3 4h18v4H3z", "M5 8v12h14V8", "M10 12h4"],
    plus: ["M12 5v14", "M5 12h14"],
    up: ["m18 15-6-6-6 6"],
    down: ["m6 9 6 6 6-6"],
    settings: [
      "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
      "M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
    ],
    user: ["M20 21v-2a7 7 0 0 0-14 0v2", "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0"],
    instagram: [
      "M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5z",
      "M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
      "M17.5 6.5h.01",
    ],
  };
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  for (const d of paths[name] || paths.chat) {
    const path = document.createElementNS(svg.namespaceURI, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}
const channelMasks = new Map();
function channelIcon(type, fallback) {
  const glyphs = {
    Api: "api",
    Email: "mail",
    FacebookPage: "messenger",
    Line: "line",
    Sms: "sms",
    Telegram: "telegram",
    TwilioSms: "sms",
    TwitterProfile: "x",
    WebWidget: "website",
    Whatsapp: "whatsapp",
    Instagram: "instagram",
    Tiktok: "tiktok",
  };
  const glyph = glyphs[type];
  if (!glyph) return icon(fallback);
  try {
    if (!channelMasks.has(glyph)) {
      const probe = parent.document.createElement("span");
      probe.className = `i-woot-${glyph}`;
      probe.hidden = true;
      parent.document.body.append(probe);
      try {
        channelMasks.set(glyph, parent.getComputedStyle(probe).maskImage);
      } finally {
        probe.remove();
      }
    }
    const mask = channelMasks.get(glyph);
    if (mask && mask !== "none") {
      const node = el("span", null, "icon");
      node.setAttribute("aria-hidden", "true");
      Object.assign(node.style, {
        maskImage: mask,
        maskSize: "contain",
        maskRepeat: "no-repeat",
        backgroundColor: "currentColor",
      });
      return node;
    }
  } catch {
    /* Canal genérico quando o ícone nativo não estiver disponível. */
  }
  return icon(fallback);
}
function avatar(name, source, small = false) {
  const initials = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => [...word][0])
    .join("")
    .toLocaleUpperCase("pt-BR");
  const node = el("span", initials, "avatar" + (small ? " small" : ""));
  node.title = name || "Sem responsável";
  node.setAttribute("aria-label", node.title);
  if (!name) {
    node.classList.add("unassigned");
    node.append(icon("user"));
  }
  if (source) {
    try {
      const url = new URL(source, location.origin);
      if (
        url.protocol === "https:" ||
        (url.protocol === "http:" && url.origin === location.origin)
      ) {
        const image = el("img");
        image.src = url.href;
        image.alt = String(name || "");
        image.loading = "lazy";
        image.referrerPolicy = "no-referrer";
        image.onerror = () =>
          node.replaceChildren(document.createTextNode(initials));
        node.replaceChildren(image);
      }
    } catch {
      /* Preservar iniciais quando a imagem não for válida. */
    }
  }
  return node;
}
function relativeTime(value) {
  const seconds = Math.max(
    0,
    Math.floor((Date.now() - new Date(value).getTime()) / 1000),
  );
  if (!Number.isFinite(seconds)) return "Sem atividade";
  if (seconds < 60) return "agora";
  if (seconds < 3600) return `há ${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `há ${Math.floor(seconds / 3600)} h`;
  return new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" }).format(
    -Math.floor(seconds / 86400),
    "day",
  );
}
async function nativeApi(path) {
  const raw = document.cookie
    .split("; ")
    .find((value) => value.startsWith("cw_d_session_info="));
  if (!raw) throw new Error("Sessão nativa indisponível");
  const session = JSON.parse(
    decodeURIComponent(raw.slice(raw.indexOf("=") + 1)),
  );
  const headers = Object.fromEntries(
    ["access-token", "client", "uid"].map((key) => [key, session[key]]),
  );
  const response = await fetch(`/api/v1/accounts/${account}${path}`, {
    credentials: "same-origin",
    signal: AbortSignal.timeout(15000),
    headers,
  });
  if (!response.ok) throw new Error("Metadados indisponíveis");
  return response.json();
}
// Canal vem da caixa de entrada: uma consulta por conta, não uma por cartão.
function enrichCards() {
  if (metadataLoading || metadataLoaded) return;
  const epoch = authorizationEpoch;
  metadataLoading = (async () => {
    const results = await Promise.allSettled([
      nativeApi("/labels"),
      nativeApi("/agents"),
      nativeApi("/inboxes"),
    ]);
    if (epoch !== authorizationEpoch) return;
    if (results[0].status === "fulfilled")
      for (const label of results[0].value.payload || [])
        metadata.labels.set(label.title, label);
    if (results[1].status === "fulfilled")
      for (const agent of results[1].value.payload || results[1].value || [])
        metadata.agents.set(agent.id, agent);
    if (results[2].status === "fulfilled")
      for (const inbox of results[2].value.payload || [])
        metadata.inboxes.set(inbox.id, inbox);
    metadataLoaded = results.every((result) => result.status === "fulfilled");
    renderLabelOptions();
    if (!editing && !dragged && !moving) render();
    else pendingRefresh = true;
  })()
    .catch(() => {})
    .finally(() => {
      metadataLoading = null;
    });
}
function connectionStatus(text, state) {
  $("connection").title = text;
  $("connection").setAttribute("aria-label", text);
  $("connection").dataset.state = state;
}
const button = (text, fn) => {
  const b = el("button", text);
  b.type = "button";
  b.onclick = () => Promise.resolve(fn()).catch(showError);
  return b;
};
function notice(text) {
  $("notice").textContent = text;
  $("notice").hidden = !text;
}
function showError(error) {
  if (error.name === "AbortError") return;
  const message = error.name === "TimeoutError"
    ? "A consulta demorou demais. Tente novamente."
    : error.message || String(error);
  if (editing) {
    let feedback = $("dialog-error");
    if (!feedback) {
      feedback = el("p", "", "dialog-error");
      feedback.id = "dialog-error";
      feedback.setAttribute("role", "alert");
      $("dialog-content").append(feedback);
    }
    feedback.textContent = message;
  } else notice(message);
}
async function lossReason() {
  const config = await api("/metrics/configuration");
  return new Promise((resolve, reject) => {
    const wasEditing = editing;
    editing = true;
    const modal = el("dialog"),
      form = el("form"),
      title = el("h2", "Motivo da perda");
    const [reason, select] = selectField("Motivo", [
      ["", "Selecione um motivo"],
      ...config.loss_reasons.map((r) => [r, r]),
      ["Outro", "Outro"],
    ]);
    select.required = true;
    const [description, text] = field("Descreva o motivo", "textarea", "");
    text.maxLength = 490;
    description.hidden = true;
    select.onchange = () => {
      description.hidden = select.value !== "Outro";
      text.required = select.value === "Outro";
    };
    const actions = el("div", null, "dialog-actions"),
      cancel = button("Cancelar", () => finish(null)),
      save = el("button", "Confirmar perda", "primary");
    save.type = "submit";
    actions.append(cancel, save);
    form.append(title, reason, description, actions);
    modal.append(form);
    document.body.append(modal);
    function finish(value) {
      modal.close();
      modal.remove();
      editing = wasEditing;
      if (value) resolve(value);
      else reject(new DOMException("Movimentação cancelada", "AbortError"));
    }
    modal.oncancel = (e) => {
      e.preventDefault();
      finish(null);
    };
    form.onsubmit = (e) => {
      e.preventDefault();
      if (select.value === "Outro" && !text.value.trim()) {
        text.setCustomValidity("Descreva o motivo.");
        text.reportValidity();
        return;
      }
      finish(
        select.value === "Outro" ? "Outro: " + text.value.trim() : select.value,
      );
    };
    text.oninput = () => text.setCustomValidity("");
    dismissOutside(modal, () => finish(null));
    modal.showModal();
    select.focus();
  });
}
async function api(path, method = "GET", body) {
  if (
    body?.stage_id &&
    /^\/cards(?:\/\d+)?$/.test(path) &&
    ["PATCH", "POST"].includes(method)
  ) {
    const target = data.stages.find((s) => s.id === body.stage_id);
    const current = data.cards.find((c) => c.id === Number(path.split("/")[2]));
    if (target?.kind === "lost" && !body.lost_reason)
      body.lost_reason =
        current?.stage_id === target.id && current.lost_reason
          ? current.lost_reason
          : await lossReason();
  }
  const url = new URL("/kanban" + path, location.origin);
  url.searchParams.set("account", account);
  const response = await fetch(url, {
    method,
    credentials: "same-origin",
    signal: AbortSignal.timeout(15000),
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    if ([401, 403].includes(response.status)) clearRestrictedData();
    const result = await response.json().catch(() => ({}));
    const error = new Error(
      typeof result.detail === "string"
        ? result.detail
        : `Falha ${response.status}. Atualize e tente novamente.`,
    );
    error.status = response.status;
    throw error;
  }
  return response.json();
}
function options(select, items, value) {
  select.replaceChildren(
    ...items.map(([v, t]) => {
      const o = el("option", t);
      o.value = v;
      return o;
    }),
  );
  if (value !== undefined) select.value = value;
}
function field(label, type, value) {
  const wrapper = el("label", label);
  const input = el(type === "textarea" ? "textarea" : "input");
  if (type !== "textarea") input.type = type;
  input.value = value ?? "";
  wrapper.append(input);
  return [wrapper, input];
}
function selectField(label, items, value) {
  const wrapper = el("label", label),
    input = el("select");
  options(input, items, value);
  wrapper.append(input);
  return [wrapper, input];
}
function dialog(title, content, save, after) {
  dialogGeneration++;
  editing = true;
  notice("");
  document.querySelectorAll(".dialog-extra").forEach((node) => node.remove());
  $("dialog").classList.remove("deal-dialog", "stage-dialog", "manage-dialog");
  $("dialog-save").classList.remove("danger");
  $("dialog-save").textContent = "Salvar";
  $("dialog-save").disabled = false;
  $("dialog-title").textContent = title;
  $("dialog-content").replaceChildren(...content);
  $("dialog-save").hidden = !save;
  $("dialog-form").onsubmit = async (event) => {
    event.preventDefault();
    $("dialog-save").disabled = true;
    try {
      if (save) await save();
      pendingRefresh = false;
      closeDialog();
      await load();
      if (after) after();
    } catch (e) {
      showError(e);
    } finally {
      $("dialog-save").disabled = false;
    }
  };
  if (!$("dialog").open) $("dialog").showModal();
}
function closeDialog() {
  dialogGeneration++;
  $("dialog").close();
  editing = false;
  editingCardId = null;
  refreshHistory = null;
  if (pendingRefresh) {
    pendingRefresh = false;
    load().catch(showError);
  }
}
$("dialog-close").onclick = closeDialog;
$("dialog").addEventListener("cancel", (event) => {
  event.preventDefault();
  closeDialog();
});
function dismissOutside(modal, close) {
  let outside = false;
  const isOutside = (event) => {
    const rect = modal.getBoundingClientRect();
    return event.clientX < rect.left || event.clientX > rect.right ||
      event.clientY < rect.top || event.clientY > rect.bottom;
  };
  modal.addEventListener("pointerdown", (event) => { outside = isOutside(event); });
  modal.addEventListener("click", (event) => {
    if (outside && isOutside(event)) close();
    outside = false;
  });
}
dismissOutside($("dialog"), closeDialog);
function navigate(card) {
  if (!card.conversation_id) return;
  const resource = "conversations", id = card.conversation_id;
  if (compact)
    window.top.location.assign(`/app/accounts/${account}/${resource}/${id}`);
  else {
    const message = { event: "kanban:navigate", account, resource, id };
    if (window.KanbanHelpers.validNavigation(message, account))
      parent.postMessage(message, location.origin);
  }
}
async function conversationDialog(card) {
  let chosen = card.conversation_pinned ? card.conversation_id : null;
  let conversations = [];
  const [searchLabel, search] = field("Buscar conversa", "search", "");
  search.placeholder = "Busque pelo texto, caixa ou situação";
  const results = el("div", null, "conversation-results");
  const status = el("p", "Carregando conversas…", "muted");
  status.setAttribute("role", "status");
  const statuses = { open: "Aberta", resolved: "Resolvida", pending: "Pendente", snoozed: "Adiada" };
  const automatic = button("Usar conversa com atividade mais recente", () => {
    chosen = null;
    draw();
  });
  function draw() {
    automatic.setAttribute("aria-pressed", String(chosen === null));
    results.replaceChildren();
    const query = search.value.trim().toLocaleLowerCase("pt-BR");
    const filtered = conversations.filter((c) =>
      [c.preview, c.inbox, statuses[c.status] || c.status].join(" ").toLocaleLowerCase("pt-BR").includes(query));
    for (const c of filtered) {
      const row = button("", () => { chosen = c.id; draw(); });
      row.className = "conversation-option";
      row.setAttribute("aria-pressed", String(chosen === c.id));
      row.append(icon("chat"), el("strong", c.preview),
        el("small", `${c.inbox} · ${statuses[c.status] || c.status}`));
      results.append(row);
    }
    status.textContent = filtered.length ? "Selecione a conversa que deseja vincular." : "Nenhuma conversa disponível para esta busca.";
  }
  search.oninput = draw;
  dialog("Conversa vinculada", [searchLabel, automatic, status, results], () =>
    api(`/cards/${card.id}/conversation`, "PUT", { conversation_id: chosen, version: card.version }));
  const generation = dialogGeneration;
  $("dialog-save").disabled = true;
  try {
    conversations = await api(`/cards/${card.id}/conversations`);
    if (generation !== dialogGeneration) return;
    draw();
    $("dialog-save").disabled = false;
  } catch (error) {
    if (generation === dialogGeneration) status.textContent = error.message;
  }
}
function clearRestrictedData() {
  authorizationEpoch++;
  pendingRefresh = false;
  dragged = null;
  moving = false;
  data = { funnels: [], stages: [], cards: [], contacts: [] };
  metadata.inboxes.clear();
  metadataLoaded = false;
  if ($("dialog").open) closeDialog();
  render();
}
function taskDialog(card) {
  editingCardId = card.id;
  const [msg, m] = field("Tarefa", "textarea", card.message);
  m.required = true;
  m.maxLength = 4000;
  const [due, d] = field(
    "Vencimento — horário de Brasília",
    "date",
    card.due_date,
  );
  d.required = true;
  const members = new Map((data.agents || []).map(a => [a.id, a.name]));
  for (const a of metadata.agents.values()) members.set(a.id, a.name);
  if (user?.id) members.set(user.id, user.name || "Você");
  const [owner, o] = selectField("Responsável da tarefa",
    [["", "Sem responsável"], ...members.entries()],
    card.task_id ? (card.task_assigned_to || "") : (user?.id || ""));
  const content = [msg, due, owner];
  dialog(`Tarefa · ${card.name}`, content, () =>
    api(`/contacts/${card.contact_id}/task`, "PUT", {
      descricao: m.value,
      vencimento: d.value,
      assigned_to: o.value ? Number(o.value) : null,
      version: card.task_version || null,
    }),
  );
  if (card.task_id) {
    const complete = button("Concluir tarefa", async () => {
      complete.disabled = true;
      try {
        await api(`/contacts/${card.contact_id}/task/close`, "POST", {version: card.task_version});
        pendingRefresh = false;
        closeDialog();
        await load();
      } finally { complete.disabled = false; }
    });
    complete.className = "dialog-extra task-complete";
    complete.prepend(icon("check"));
    $("dialog-save").before(complete);
  }
}
const STAGE_KINDS = { won: "Ganho", lost: "Perdido" };
function stageOption(stage) {
  const dot = el("span", null, "stage-dot");
  if (/^#[0-9a-f]{6}$/i.test(stage.color || ""))
    dot.style.backgroundColor = stage.color;
  const parts = [dot, el("span", stage.name, "stage-option-name")];
  const kind = STAGE_KINDS[stage.kind];
  if (kind && kind.toLowerCase() !== stage.name.trim().toLowerCase())
    parts.push(el("span", kind, `stage-kind ${stage.kind}`));
  return parts;
}
// Menu próprio: o <select> nativo não mostra cor nem tipo da etapa.
function stageField(stages, value) {
  const state = { value: String(value) };
  const wrapper = el("div", null, "stage-field");
  const caption = el("span", "Etapa", "field-caption");
  const root = el("details", null, "picker stage-picker");
  const trigger = el("summary", null, "picker-trigger");
  trigger.setAttribute("aria-label", "Etapa");
  const current = el("span", null, "stage-option");
  const list = el("div", null, "picker-menu stage-menu");
  list.setAttribute("role", "listbox");
  list.setAttribute("aria-label", "Etapa");
  const paint = () => {
    const stage = stages.find((x) => String(x.id) === state.value);
    current.replaceChildren(...(stage ? stageOption(stage) : []));
  };
  for (const stage of stages) {
    const option = button("", () => {
      state.value = String(stage.id);
      list
        .querySelectorAll("button")
        .forEach((b) => b.setAttribute("aria-selected", String(b === option)));
      paint();
      root.open = false;
      trigger.focus();
    });
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", String(String(stage.id) === state.value));
    const check = icon("check");
    check.classList.add("stage-check");
    option.append(...stageOption(stage), check);
    list.append(option);
  }
  trigger.append(current, el("span", "⌄", "picker-arrow"));
  root.append(trigger, list);
  root.addEventListener("toggle", () => {
    if (root.open)
      (list.querySelector('[aria-selected="true"]') || list.firstChild)?.focus();
  });
  root.onkeydown = (event) => {
    if (event.key === "Escape" && root.open) {
      event.stopPropagation();
      event.preventDefault();
      root.open = false;
      trigger.focus();
    }
    if (["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      if (!root.open) return void (root.open = true);
      const buttons = [...list.querySelectorAll("button")];
      const index = buttons.indexOf(document.activeElement);
      buttons[
        (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) %
          buttons.length
      ]?.focus();
    }
  };
  root.addEventListener("focusout", () =>
    setTimeout(() => {
      if (!root.contains(document.activeElement)) root.open = false;
    }, 0),
  );
  paint();
  wrapper.append(caption, root);
  return [wrapper, state];
}
function details(card) {
  editingCardId = card.id;
  const [stage, s] = stageField(
    data.stages.filter((x) => x.funnel_id === card.funnel_id),
    card.stage_id,
  );
  const [value, v] = field("Valor em reais", "text", money(card.value_cents));
  v.inputMode = "numeric";
  v.maxLength = 17;
  v.oninput = () => { v.value = money(window.KanbanHelpers.moneyInputCents(v.value)); };
  const actions = el("div", null, "card-actions");
  const action = (label, glyph, fn) => {
    const node = button(label, fn);
    node.prepend(icon(glyph));
    actions.append(node);
  };
  if (card.conversation_id) action("Abrir conversa", "chat", () => navigate(card));
  else action("Vincular conversa", "link", () => conversationDialog(card));
  action("Histórico", "history", () => history(card.contact_id));
  action(card.task_id ? "Editar tarefa" : "Criar tarefa", "task", () => taskDialog(card));
  const content = [
    el(
      "p",
      card.phone || card.email || "Contato sem telefone cadastrado",
      "muted",
    ),
    stage,
    value,
    el(
      "p",
      `Responsável: ${card.assignee_name || "Não atribuído"} · Sincronização: ${syncLabel(card.sync_status)}`,
      "muted",
    ),
    actions,
  ];
  dialog(card.name, content, () =>
    api(`/cards/${card.id}`, "PATCH", {
      version: card.version,
      stage_id: Number(s.value),
      value_cents: window.KanbanHelpers.moneyInputCents(v.value),
    }),
  );
  const remove = button("", () => {
    dialog("Excluir negociação?", [el("p", "O contato, as conversas e a tarefa compartilhada serão mantidos.")], async () => {
      const result = await api(`/cards/${card.id}`, "DELETE", {version: card.version});
      notice("Negociação excluída. ");
      const undo = button("Desfazer", async () => {
        undo.disabled = true;
        try {
          await api(`/cards/${card.id}/restore`, "POST", {version: result.version});
          notice("");
          await load();
        } finally { undo.disabled = false; }
      });
      $("notice").append(undo);
    });
    $("dialog-save").textContent = "Excluir negociação";
  });
  $("dialog").classList.add("stage-dialog");
  remove.className = "dialog-extra delete-deal";
  remove.title = "Excluir negociação";
  remove.setAttribute("aria-label", "Excluir negociação");
  remove.append(icon("trash"));
  $("dialog-close").before(remove);
}
const syncLabel = (status) =>
  ({
    synced: "Sincronizado",
    pending: "Sincronização pendente",
    failed: "Falha na sincronização",
  })[status] || status;
function render() {
  renderedFunnel = selected;
  const cards = data.cards.filter(c => c.funnel_id === selected &&
    (!compact || c.contact_id === contactContext));
  const totals = new Map((data.totals || []).map(t => [t.stage_id, t]));
  const failures = data.cards.filter((card) => card.sync_status === "failed");
  const failedContacts = data.failed_contacts ?? new Set(failures.map((card) => card.contact_id)).size;
  $("sync-warning").hidden = !failedContacts;
  $("sync-count").textContent =
    `${failedContacts} ${failedContacts === 1 ? "contato com falha de sincronização" : "contatos com falha de sincronização"}`;
  $("retry").hidden = !failedContacts || user?.role !== "administrator";
  $("board").replaceChildren();
  for (const stage of data.stages.filter((s) => s.funnel_id === selected)) {
    const column = el("section", null, "column");
    column.dataset.stageId = stage.id;
    const rows = cards.filter((c) => c.stage_id === stage.id);
    const total = totals.get(stage.id) || {count: rows.length,
      value_cents: rows.reduce((n, c) => n + c.value_cents, 0)};
    const head = el("div", null, "column-head");
    const dot = el("span", null, "dot");
    dot.style.backgroundColor = stage.color;
    head.append(
      dot,
      el("span", stage.name),
      el("span", total.count, "count"),
      el(
        "span",
        money(total.value_cents),
        "column-total",
      ),
    );
    column.append(head);
    for (const card of rows) {
      const item = el("article", null, "card");
      item.draggable = true;
      item.tabIndex = 0;
      item.dataset.cardId = card.id;
      if (card.id === landingCard) item.classList.add("card-landed");
      item.ondragstart = (e) => {
        if (moving) {
          e.preventDefault();
          return;
        }
        dragged = card;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(card.id));
        $("board").classList.add("is-dragging");
        requestAnimationFrame(() => {
          if (dragged?.id === card.id) item.classList.add("is-drag-source");
        });
      };
      item.ondragend = () => {
        clearDrag();
        if (pendingRefresh && !editing && !moving) {
          pendingRefresh = false;
          load().catch(showError);
        }
      };
      item.setAttribute("aria-label", `Detalhes de ${card.name}`);
      const heading = el("div", null, "card-heading");
      const portrait = el("div", null, "avatar-wrap");
      portrait.append(avatar(card.name, card.thumbnail));
      const channelName = metadata.inboxes.get(card.conversation_inbox_id)?.channel_type;
      if (card.conversation_id) {
        const channel = el("span", null, "channel");
        const type = String(channelName || "").replace("Channel::", "");
        const channels = {
          Email: ["mail", "E-mail"],
          Whatsapp: ["phone", "WhatsApp"],
          TwilioSms: ["phone", "SMS"],
          Sms: ["phone", "SMS"],
          WebWidget: ["web", "Chat do site"],
          Instagram: ["instagram", "Instagram"],
          FacebookPage: ["chat", "Messenger"],
          Telegram: ["chat", "Telegram"],
          Api: ["chat", "API"],
        };
        const [glyph, title] = channels[type] || ["chat", type || "Conversa"];
        channel.title = title;
        channel.setAttribute("aria-label", title);
        channel.append(channelIcon(type, glyph));
        portrait.append(channel);
      }
      const identity = el("div", null, "card-identity");
      const name = el("span", card.name, "card-name");
      name.title = card.name;
      identity.append(
        name,
        el("span", card.phone || card.email || "Sem telefone", "card-phone"),
      );
      heading.append(portrait, identity);
      item.append(heading);
      if (card.labels.length) {
        const tags = el("div", null, "tags");
        card.labels.slice(0, 3).forEach((title) => {
          const tag = el("span", null, "tag");
          tag.title = title;
          const dot = el("span", null, "label-dot");
          const color = metadata.labels.get(title)?.color;
          if (/^#[\da-f]{3,8}$/i.test(color || ""))
            dot.style.setProperty("--label-color", color);
          tag.append(dot, el("span", title, "tag-text"));
          tags.append(tag);
        });
        if (card.labels.length > 3) {
          const more = el("span", `+${card.labels.length - 3}`, "tag more");
          more.title = card.labels.slice(3).join(", ");
          tags.append(more);
        }
        item.append(tags);
      }
      const bottom = el("div", null, "card-bottom");
      if (card.value_cents > 0)
        bottom.append(el("span", money(card.value_cents), "card-value"));
      if (card.sync_status === "failed") {
        const alert = el("span", null, "sync-alert");
        alert.title = "Falha na sincronização";
        alert.setAttribute("aria-label", alert.title);
        alert.append(icon("alert"));
        bottom.append(alert);
      }
      if (card.last_activity_at) {
        const time = el(
          "time",
          relativeTime(card.last_activity_at),
          "last-activity",
        );
        time.dateTime = card.last_activity_at;
        time.dataset.activityAt = card.last_activity_at;
        time.title = new Date(card.last_activity_at).toLocaleString("pt-BR");
        bottom.append(time);
      }
      if (card.stage_entered_at) {
        const duration = el("span", `Na etapa ${relativeTime(card.stage_entered_at)}`, "last-activity");
        duration.title = `Entrada na etapa: ${new Date(card.stage_entered_at).toLocaleString("pt-BR")}`;
        bottom.append(duration);
      }
      const agent = metadata.agents.get(card.assignee_id);
      bottom.append(
        avatar(card.assignee_name, agent?.thumbnail || agent?.avatar_url, true),
      );
      item.append(bottom);
      if (card.task_id) {
        const taskBox = el(
          "div",
          null,
          "task " +
            (["overdue", "today", "active"].includes(card.due_state)
              ? card.due_state
              : "active"),
        );
        const message = el("span", card.message, "task-message");
        message.title = card.message;
        const due = el("time", dateBR(card.due_date));
        due.dateTime = card.due_date;
        due.title = `${card.due_state === "overdue" ? "Vencida" : card.due_state === "today" ? "Vence hoje" : "Vencimento"} · ${dateBR(card.due_date)}`;
        taskBox.append(icon("task"), message, due);
        if (card.task_assignee_name) taskBox.append(el("span", card.task_assignee_name, "task-owner"));
        item.append(taskBox);
      }
      const taskButton = button("", () => taskDialog(card));
      taskButton.className = "task-action icon-button ghost";
      taskButton.title = card.task_id ? "Editar tarefa" : "Criar tarefa";
      taskButton.setAttribute("aria-label", taskButton.title);
      taskButton.append(icon("task"));
      item.append(taskButton);
      item.onclick = (event) => {
        if (!event.target.closest("button")) details(card);
      };
      item.onkeydown = (event) => {
        if (
          (event.key === "Enter" || event.key === " ") &&
          event.target === item
        ) {
          event.preventDefault();
          details(card);
        }
      };
      column.append(item);
    }
    if (!rows.length)
      column.append(
        el(
          "div",
          compact
            ? "Sem cartão nesta etapa"
            : "Arraste uma negociação para esta etapa",
          "empty",
        ),
      );
    const offset = stageOffsets.get(stage.id) || 0;
    if (offset || total.count > rows.length) {
      const pages = el("div", null, "column-pages");
      const previous = button("Anteriores", () => loadStage(stage.id, Math.max(0, offset - 50)));
      previous.disabled = !offset;
      const next = button("Próximos", () => loadStage(stage.id, offset + 50));
      next.disabled = offset + rows.length >= total.count;
      pages.append(previous, el("span", `${offset + (rows.length ? 1 : 0)}–${offset + rows.length} de ${total.count}`), next);
      column.append(pages);
    }
    $("board").append(column);
  }
  if (!data.funnels.length)
    $("board").append(
      el("p", "Aguardando provisionamento da conta.", "empty"),
    );
  if (compact && !contactContext)
    $("board").replaceChildren(
      el(
        "p",
        "Abra uma conversa para visualizar os funis deste contato.",
        "empty",
      ),
    );
  const visibleTotals = data.stages.filter(s => s.funnel_id === selected).map(s => totals.get(s.id)).filter(Boolean);
  const count = data.totals ? visibleTotals.reduce((n, t) => n + t.count, 0) : cards.length;
  const value = data.totals ? visibleTotals.reduce((n, t) => n + t.value_cents, 0) : cards.reduce((n, c) => n + c.value_cents, 0);
  $("summary").textContent = `${count} ${count === 1 ? "negociação" : "negociações"} · ${money(value)}`;
}
const dropMarker = el("div", null, "drop-marker");
dropMarker.setAttribute("aria-hidden", "true");
let dropColumn, dropBefore;
function clearDropTarget() {
  dropColumn?.classList.remove("drop-active");
  dropMarker.remove();
  dropColumn = null;
  dropBefore = null;
}
function clearDrag() {
  clearDropTarget();
  $("board").classList.remove("is-dragging");
  $("board")
    .querySelectorAll(".is-drag-source")
    .forEach((node) => node.classList.remove("is-drag-source"));
  dragged = null;
}
function previewDrop(event) {
  if (!dragged || moving) return null;
  const boardRect = $("board").getBoundingClientRect();
  if (
    event.clientX < boardRect.left ||
    event.clientX > boardRect.right ||
    event.clientY < boardRect.top ||
    event.clientY > boardRect.bottom
  ) {
    clearDropTarget();
    return null;
  }
  const columns = [...$("board").querySelectorAll(".column")];
  const column = columns.find((node) => {
    const rect = node.getBoundingClientRect();
    return event.clientX >= rect.left - 8 && event.clientX <= rect.right + 8;
  });
  if (!column) {
    clearDropTarget();
    return null;
  }
  const before =
    [...column.querySelectorAll(".card")].find((node) => {
      if (Number(node.dataset.cardId) === dragged.id) return false;
      const rect = node.getBoundingClientRect();
      return event.clientY < rect.top + rect.height / 2;
    }) || null;
  if (column !== dropColumn || before !== dropBefore) {
    clearDropTarget();
    dropColumn = column;
    dropBefore = before;
    column.classList.add("drop-active");
    column.insertBefore(dropMarker, before);
  }
  return {
    stage_id: Number(column.dataset.stageId),
    before_id: before ? Number(before.dataset.cardId) : null,
  };
}
$("board").ondragover = (event) => {
  if (!previewDrop(event)) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
};
$("board").ondragleave = (event) => {
  if (!event.relatedTarget || !$("board").contains(event.relatedTarget))
    clearDropTarget();
};
$("board").ondrop = async (event) => {
  const target = previewDrop(event);
  if (!target) return;
  event.preventDefault();
  const card = dragged;
  const previous = data.cards;
  moving = true;
  clearDrag();
  const updated = {
    ...card,
    stage_id: target.stage_id,
    sync_status: "pending",
  };
  data.cards = previous.filter((item) => item.id !== card.id);
  const index =
    target.before_id === null
      ? data.cards.length
      : data.cards.findIndex((item) => item.id === target.before_id);
  data.cards.splice(index < 0 ? data.cards.length : index, 0, updated);
  landingCard = card.id;
  clearTimeout(landingTimer);
  landingTimer = setTimeout(() => {
    landingCard = null;
  }, 450);
  render();
  $("board").setAttribute("aria-busy", "true");
  try {
    const loaded = previous.filter(c => c.stage_id === target.stage_id).length;
    const end = (stageOffsets.get(target.stage_id) || 0) + loaded;
    const total = data.totals?.find(t => t.stage_id === target.stage_id)?.count || 0;
    if (target.before_id === null && end < total) {
      // A borda da página aponta ao próximo cartão, não ao fim da etapa.
      const next = await api(boardQuery(target.stage_id, end));
      target.before_id = next.cards[0]?.id || null;
    }
    await api(`/cards/${card.id}`, "PATCH", {
      version: card.version,
      ...target,
    });
  } catch (error) {
    data.cards = previous;
    landingCard = null;
    render();
    showError(error);
  } finally {
    moving = false;
    $("board").removeAttribute("aria-busy");
    pendingRefresh = false;
    await load().catch(showError);
  }
};
let editingCardId = null, refreshHistory = null, renderedFunnel = null;
const stageOffsets = new Map();
function boardQuery(stage, offset = 0) {
  const params = new URLSearchParams({limit: "50", offset: String(offset),
    search: $("search").value, label: $("label").value, task: $("task-filter").value});
  if (selected) params.set("funnel_id", selected);
  if (stage) params.set("stage_id", stage);
  if (compact && contactContext) params.set("contact_id", contactContext);
  if ($("assignee").value) params.set("assignee_id", $("assignee").value);
  return `/board?${params}`;
}
async function loadStage(stage, offset) {
  const generation = ++loadGeneration, epoch = authorizationEpoch;
  const next = await api(boardQuery(stage, offset));
  if (generation !== loadGeneration || epoch !== authorizationEpoch) return;
  if (editing || moving || dragged) { pendingRefresh = true; return; }
  data.cards = [...data.cards.filter(c => c.stage_id !== stage), ...next.cards];
  data.totals = [...(data.totals || []).filter(t => t.stage_id !== stage), ...next.totals];
  stageOffsets.set(stage, offset);
  render();
  enrichCards();
}
async function load(force = false) {
  if (user?.activation && user.activation.activation_status !== "ready") return;
  if (!force && (editing || dragged || moving)) {
    pendingRefresh = true;
    return;
  }
  const epoch = authorizationEpoch;
  const generation = ++loadGeneration;
  if (force && editing && editingCardId) {
    try { await api(`/cards/${editingCardId}`); }
    catch (error) { if ([401,403,404].includes(error.status)) clearRestrictedData(); throw error; }
  }
  if (force && editing && refreshHistory) await refreshHistory();
  const early =
    prefetchedBoard?.query === boardQuery() ? await prefetchedBoard.result : null;
  prefetchedBoard = null;
  const next = early || (await api(boardQuery()));
  if (epoch !== authorizationEpoch || generation !== loadGeneration) return;
  const removed = !next.totals && data.cards.some((card) => !next.cards.some((c) => c.id === card.id));
  if (removed) {
    // Remoção de acesso precisa limpar inclusive um detalhe ou histórico aberto.
    clearRestrictedData();
  } else if (editing || dragged || moving) {
    pendingRefresh = true;
    if (editing && !dragged && !moving) { data = next; stageOffsets.clear(); render(); }
    return;
  }
  if (!selected && next.funnel_id) selected = next.funnel_id;
  const unchanged = JSON.stringify(data) === JSON.stringify(next);
  data = next;
  stageOffsets.clear();
  if (unchanged && renderedFunnel === selected && $("board").childElementCount) return;
  if (!data.funnels.some((f) => f.id === selected)) {
    selected = data.funnels[0]?.id;
    if (selected) return load(force);
  }
  renderFunnelPicker();
  options(
    $("assignee"),
    [
      ["", "Responsável"],
      ...new Map(
        [...(data.agents || []).map(a => [a.id, a.name]),
          ...[...metadata.agents.values()].map(a => [a.id, a.name]),
          ...data.cards.filter(c => c.assignee_id).map(c => [c.assignee_id, c.assignee_name])],
      ).entries(),
    ],
    $("assignee").value,
  );
  renderLabelOptions();
  render();
  enrichCards();
}
function renderLabelOptions() {
  const labels = [...new Set([...metadata.labels.keys(), ...data.cards.flatMap((c) => c.labels || [])])];
  labels.sort((a, b) => a.localeCompare(b, "pt-BR"));
  options($("label"), [["", "Etiqueta"], ...labels.map((name) => [name, name])], $("label").value);
}
function picker(items, value, label, change, heading = false) {
  const root = el("details", null, "picker"),
    trigger = el("summary", null, heading ? "picker-title" : "picker-trigger");
  trigger.setAttribute("aria-label", label);
  const title = el(
    "span",
    items.find((x) => x.id === value)?.name || "Selecione um funil",
  );
  const arrow = el("span", "⌄", "picker-arrow");
  trigger.append(title, arrow);
  const list = el("div", null, "picker-menu");
  list.setAttribute("role", "group");
  list.setAttribute("aria-label", label);
  for (const item of items) {
    const option = button(item.name, () => {
      title.textContent = item.name;
      root.open = false;
      list
        .querySelectorAll("button")
        .forEach((b) => b.setAttribute("aria-pressed", String(b === option)));
      trigger.focus();
      change(item.id);
    });
    option.title = item.name;
    option.setAttribute("aria-pressed", String(item.id === value));
    list.append(option);
  }
  root.append(trigger, list);
  root.onkeydown = (event) => {
    if (event.key === "Escape" && root.open) {
      event.stopPropagation();
      event.preventDefault();
      root.open = false;
      trigger.focus();
    }
    if (["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      root.open = true;
      const buttons = [...list.querySelectorAll("button")];
      const index = buttons.indexOf(document.activeElement);
      buttons[
        (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) %
          buttons.length
      ]?.focus();
    }
  };
  root.addEventListener("focusout", () =>
    setTimeout(() => {
      if (!root.contains(document.activeElement)) root.open = false;
    }, 0),
  );
  return root;
}
function renderFunnelPicker() {
  $("funnel-picker").replaceChildren(
    picker(
      data.funnels,
      selected,
      "Selecionar funil",
      (id) => {
        selected = id;
        rememberFunnel(id);
        load().catch(showError);
      },
      true,
    ),
  );
}
document.addEventListener("click", (event) => {
  document.querySelectorAll(".picker[open]").forEach((node) => {
    if (!node.contains(event.target)) node.open = false;
  });
});
let filterTimer;
["search", "assignee", "label", "task-filter"].forEach(id => {
  $(id).oninput = () => {
    clearTimeout(filterTimer);
    ++loadGeneration;
    filterTimer = setTimeout(() => load().catch(showError), id === "search" ? 250 : 0);
  };
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && dragged) {
    clearDrag();
    return;
  }
  if (e.key === "Escape" && !editing)
    parent.postMessage({ event: "kanban:close" }, location.origin);
});
$("add-card").onclick = () => {
  let chosen,
    funnelId = selected,
    stageId,
    searchGeneration = 0,
    searchTimer,
    page = 1,
    query = "";
  const intro = el(
    "p",
    "Vincule um contato do Chatwoot e escolha onde a negociação começa.",
    "deal-intro",
  );
  const layout = el("div", null, "deal-layout");
  const contactPane = el("section", null, "deal-contact-pane");
  const [searchLabel, search] = field("1. Buscar contato", "search", "");
  search.placeholder = "Nome, telefone ou e-mail";
  search.autocomplete = "off";
  const results = el("div", null, "contact-results");
  const status = el(
    "p",
    "Digite pelo menos 2 caracteres para buscar nos contatos desta conta.",
    "deal-hint",
  );
  status.setAttribute("role", "status");
  const more = button("Carregar mais contatos", () => findContacts(false));
  more.hidden = true;
  contactPane.append(searchLabel, status, results, more);
  const destination = el("section", null, "deal-destination");
  const placeholder = el(
    "div",
    "Selecione um contato para escolher o funil e a etapa.",
    "deal-placeholder",
  );
  const settings = el("div", null, "deal-settings");
  settings.hidden = true;
  const summary = el("div", null, "selected-contact");
  const funnelLabel = el("div", "2. Funil", "deal-label");
  const funnelPicker = picker(
    data.funnels,
    funnelId,
    "Funil da negociação",
    (id) => {
      funnelId = id;
      updateStages();
    },
  );
  const stageTitle = el("div", "3. Etapa inicial", "deal-label");
  const stages = el("div", null, "deal-stages");
  stages.setAttribute("role", "group");
  stages.setAttribute("aria-label", "Etapa inicial");
  const feedback = el("p", "", "deal-hint");
  feedback.setAttribute("role", "status");
  settings.append(
    summary,
    funnelLabel,
    funnelPicker,
    stageTitle,
    stages,
    feedback,
  );
  destination.append(placeholder, settings);
  layout.append(contactPane, destination);
  function updateStages() {
    stages.replaceChildren();
    const available = data.stages.filter((s) => s.funnel_id === funnelId);
    stageId = available[0]?.id;
    feedback.textContent = "";
    $("dialog-save").disabled = !chosen || !stageId;
    for (const stage of available) {
      const option = button("", () => {
        stageId = stage.id;
        stages
          .querySelectorAll("button")
          .forEach((b) => b.setAttribute("aria-pressed", String(b === option)));
      });
      const dot = el("span", null, "stage-dot");
      if (/^#[0-9a-f]{6}$/i.test(stage.color))
        dot.style.backgroundColor = stage.color;
      option.append(dot, el("span", stage.name));
      option.setAttribute("aria-pressed", String(stage.id === stageId));
      stages.append(option);
    }
  }
  function selectContact(contact, row) {
    chosen = contact;
    results
      .querySelectorAll("button")
      .forEach((b) => b.setAttribute("aria-pressed", String(b === row)));
    summary.replaceChildren(
      avatar(contact.name, contact.thumbnail),
      el("div", contact.name || `Contato ${contact.id}`),
    );
    placeholder.hidden = true;
    settings.hidden = false;
    updateStages();
  }
  async function findContacts(reset) {
    const q = search.value.trim();
    const generation = ++searchGeneration;
    if (reset) {
      results.replaceChildren();
      page = 1;
      query = q;
    }
    more.hidden = true;
    if (q.length < 2) {
      status.textContent =
        "Digite pelo menos 2 caracteres para buscar nos contatos desta conta.";
      return;
    }
    status.textContent = "Buscando contatos…";
    try {
      const response = await nativeApi(
        `/contacts/search?q=${encodeURIComponent(query)}&page=${page}`,
      );
      if (generation !== searchGeneration || !$("dialog").open) return;
      const contacts = response.payload || [];
      for (const contact of contacts) {
        const row = button("", () => selectContact(contact, row));
        row.className = "contact-result";
        row.setAttribute("aria-pressed", String(contact.id === chosen?.id));
        const text = el("span", null, "contact-result-text");
        text.append(
          el("strong", contact.name || `Contato ${contact.id}`),
          el(
            "small",
            [contact.phone_number, contact.email].filter(Boolean).join(" · ") ||
              "Sem telefone ou e-mail",
          ),
        );
        row.append(avatar(contact.name, contact.thumbnail), text);
        results.append(row);
      }
      status.textContent = results.children.length
        ? "Selecione o contato da negociação."
        : "Nenhum contato encontrado. Tente outro nome, telefone ou e-mail.";
      more.hidden =
        !contacts.length ||
        results.children.length >= (response.meta?.count ?? Infinity);
      page += 1;
    } catch {
      if (generation === searchGeneration)
        status.textContent =
          "Não foi possível buscar contatos. Tente novamente.";
    }
  }
  search.oninput = () => {
    clearTimeout(searchTimer);
    searchGeneration += 1;
    searchTimer = setTimeout(() => findContacts(true), 250);
  };
  dialog("Adicionar negociação", [intro, layout], async () => {
    if (!chosen || !stageId)
      throw new Error("Selecione um contato e uma etapa.");
    try {
      await api("/cards", "POST", {
        contact_id: chosen.id,
        funnel_id: funnelId,
        stage_id: stageId,
      });
      selected = funnelId;
    } catch (error) {
      feedback.textContent = error.message;
      throw error;
    }
  });
  $("dialog").classList.add("deal-dialog");
  $("dialog-save").textContent = "Criar negociação";
  $("dialog-save").disabled = true;
  search.focus();
};
// Lead novo vira negociação só no primeiro contato; filtro vazio aceita todas as caixas.
function automationFields(funnel, inboxes) {
  const section = el("fieldset", null, "automation");
  section.append(el("legend", "Entrada automática"));
  const toggle = el("label", null, "check-row");
  const enabled = el("input");
  enabled.type = "checkbox";
  enabled.checked = Boolean(funnel?.auto_create_stage_id);
  toggle.append(enabled, el("span", "Criar negociação quando um lead novo abrir conversa"));
  const body = el("div", null, "automation-body");
  const stages = funnel
    ? data.stages.filter((s) => s.funnel_id === funnel.id && s.kind === "open")
    : [{ id: "", name: "Novo" }];
  const [stageLabel, stage] = selectField(
    "Etapa de entrada",
    stages.map((s) => [s.id, s.name]),
    funnel?.auto_create_stage_id ?? stages[0]?.id,
  );
  stage.disabled = !funnel;
  const boxes = el("div", null, "inbox-list");
  boxes.setAttribute("role", "group");
  boxes.setAttribute("aria-label", "Caixas de entrada");
  const chosen = new Set(funnel?.auto_create_inboxes || []);
  const checks = (inboxes || []).map((inbox) => {
    const row = el("label", null, "check-row");
    const input = el("input");
    input.type = "checkbox";
    input.value = inbox.id;
    input.checked = chosen.has(inbox.id);
    row.append(input, el("span", inbox.name));
    boxes.append(row);
    return input;
  });
  body.append(
    stageLabel,
    el("span", "Caixas de entrada", "automation-label"),
    inboxes
      ? checks.length
        ? boxes
        : el("p", "Nenhuma caixa de entrada encontrada.", "field-hint")
      : el("p", "Não foi possível carregar as caixas. O filtro atual foi mantido.", "field-hint"),
    el("p", "Nenhuma caixa marcada: vale para todas. Quem já teve negociação neste funil não recebe outra.", "field-hint"),
  );
  if (!funnel)
    body.prepend(el("p", "Funil novo começa pela etapa Novo; troque depois em Editar funil.", "field-hint"));
  const sync = () => (body.hidden = !enabled.checked);
  enabled.onchange = sync;
  sync();
  section.append(toggle, body);
  return {
    node: section,
    value: () => ({
      auto_create: enabled.checked,
      auto_create_stage_id: enabled.checked && stage.value ? Number(stage.value) : null,
      auto_create_inboxes: inboxes
        ? checks.filter((c) => c.checked).map((c) => Number(c.value))
        : funnel?.auto_create_inboxes || [],
    }),
  };
}
async function editFunnel(funnel) {
  const inboxes = await api("/inboxes").catch(() => null);
  const [name, n] = field("Nome do funil", "text", funnel?.name);
  n.required = true;
  n.maxLength = 100;
  const [stale, days] = field(
    "Considerar negociação parada após (dias)",
    "number",
    funnel?.stale_days || 7,
  );
  days.min = 1;
  days.max = 365;
  days.required = true;
  const automation = automationFields(funnel, inboxes);
  const last = Math.max(0, ...data.funnels.map((f) => Number(f.position)));
  dialog(
    funnel ? "Editar funil" : "Novo funil",
    [name, stale, automation.node],
    () =>
      api(
        funnel ? `/funnels/${funnel.id}` : "/funnels",
        funnel ? "PUT" : "POST",
        {
          name: n.value,
          position: funnel ? funnel.position : last + 1024,
          stale_days: Number(days.value),
          ...automation.value(),
        },
      ),
    funnel ? manage : null,
  );
}
const STAGE_COLORS = [
  "#6366f1", "#3b82f6", "#06b6d4", "#10b981",
  "#84cc16", "#f59e0b", "#f97316", "#ef4444", "#ec4899", "#64748b",
];
// Paleta com opção livre: o seletor nativo sozinho escondia as cores comuns.
function colorField(value) {
  const state = { value: value || STAGE_COLORS[0] };
  const wrapper = el("div", null, "stage-field");
  const swatches = el("div", null, "swatches");
  swatches.setAttribute("role", "radiogroup");
  swatches.setAttribute("aria-label", "Cor");
  const custom = el("input");
  custom.type = "color";
  custom.value = state.value;
  custom.title = "Outra cor";
  custom.setAttribute("aria-label", "Outra cor");
  const mark = () =>
    swatches.querySelectorAll("button").forEach((b) =>
      b.setAttribute("aria-checked", String(b.dataset.color === state.value)),
    );
  for (const color of STAGE_COLORS) {
    const swatch = button("", () => {
      state.value = color;
      custom.value = color;
      mark();
    });
    swatch.className = "swatch";
    swatch.dataset.color = color;
    swatch.style.setProperty("--swatch", color);
    swatch.setAttribute("role", "radio");
    swatch.setAttribute("aria-label", color);
    swatches.append(swatch);
  }
  custom.oninput = () => {
    state.value = custom.value;
    mark();
  };
  swatches.append(custom);
  mark();
  wrapper.append(el("span", "Cor", "field-caption"), swatches);
  return [wrapper, state];
}
function kindField(value) {
  const state = { value: value || "open" };
  const wrapper = el("div", null, "stage-field");
  const group = el("div", null, "segmented");
  group.setAttribute("role", "radiogroup");
  group.setAttribute("aria-label", "Tipo da etapa");
  for (const [kind, label] of [
    ["open", "Em andamento"],
    ["won", "Ganho"],
    ["lost", "Perdido"],
  ]) {
    const option = button(label, () => {
      state.value = kind;
      group
        .querySelectorAll("button")
        .forEach((b) => b.setAttribute("aria-checked", String(b === option)));
    });
    option.className = `segment ${kind}`;
    option.setAttribute("role", "radio");
    option.setAttribute("aria-checked", String(kind === state.value));
    group.append(option);
  }
  wrapper.append(
    el("span", "Tipo da etapa", "field-caption"),
    group,
    el("p", "Ganho e Perdido encerram a negociação; Perdido pede um motivo.", "field-hint"),
  );
  return [wrapper, state];
}
function funnelStages() {
  return data.stages.filter((s) => s.funnel_id === selected);
}
function stageBody(stage, changes = {}) {
  return {
    name: stage.name,
    color: stage.color,
    kind: stage.kind,
    position: stage.position,
    ...changes,
  };
}
function editStage(stage) {
  const [name, n] = field("Nome da etapa", "text", stage?.name);
  n.required = true;
  n.maxLength = 100;
  const [color, c] = colorField(stage?.color);
  const [kind, k] = kindField(stage?.kind);
  const last = Math.max(0, ...funnelStages().map((s) => Number(s.position)));
  dialog(
    stage ? "Editar etapa" : "Nova etapa",
    [name, color, kind],
    () =>
      api(
        stage ? `/stages/${stage.id}` : `/funnels/${selected}/stages`,
        stage ? "PUT" : "POST",
        stageBody(stage || { position: last + 1024 }, {
          name: n.value,
          color: c.value,
          kind: k.value,
        }),
      ),
    manage,
  );
}
function archiveStage(stage) {
  const others = funnelStages().filter((s) => s.id !== stage.id);
  const [destination, d] = selectField(
    "Se houver negociações nesta etapa, mover para",
    others.map((s) => [s.id, s.name]),
  );
  dialog(
    `Arquivar etapa "${stage.name}"?`,
    [
      el("p", "A etapa sai do quadro. Negociações e histórico são preservados."),
      destination,
    ],
    () =>
      api(`/stages/${stage.id}/archive`, "POST", {
        destination_id: Number(d.value) || null,
      }),
    manage,
  );
  $("dialog-save").textContent = "Arquivar etapa";
  $("dialog-save").classList.add("danger");
}
async function moveStage(stage, step) {
  const stages = funnelStages();
  const index = stages.findIndex((s) => s.id === stage.id);
  const other = stages[index + step];
  if (!other) return;
  let [a, b] = [Number(stage.position), Number(other.position)];
  if (a === b) b = a + step * 1024;
  await api(`/stages/${stage.id}`, "PUT", stageBody(stage, { position: b }));
  await api(`/stages/${other.id}`, "PUT", stageBody(other, { position: a }));
  // A janela continua aberta: forçar a recarga em vez de adiá-la.
  await load(true);
  manage();
}
function lossReasons() {
  return api("/metrics/configuration").then((config) => {
    const [reasons, input] = field(
      "Um motivo por linha",
      "textarea",
      config.loss_reasons.join("\n"),
    );
    dialog(
      "Motivos de perda",
      [el("p", "\"Outro\" com descrição estará sempre disponível.", "field-hint"), reasons],
      () =>
        api("/metrics/configuration", "PUT", {
          loss_reasons: input.value
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      manage,
    );
  });
}
function iconButton(glyph, label, fn, cls = "") {
  const node = button("", fn);
  node.className = `icon-button ghost ${cls}`.trim();
  node.title = label;
  node.setAttribute("aria-label", label);
  node.append(icon(glyph));
  return node;
}
function automationSummary(funnel, stages) {
  const stage = stages.find((s) => s.id === funnel.auto_create_stage_id);
  if (!stage) return "Entrada automática desligada";
  const count = funnel.auto_create_inboxes.length;
  const scope = count ? `${count} ${count === 1 ? "caixa" : "caixas"}` : "todas as caixas";
  return `Entrada automática em ${stage.name} · ${scope}`;
}
function manage() {
  const funnel = data.funnels.find((f) => f.id === selected);
  if (!funnel) return accountSettings();
  const stages = funnelStages();
  const header = el("section", null, "manage-funnel");
  const info = el("div", null, "manage-funnel-info");
  info.append(
    el("strong", funnel.name),
    el(
      "span",
      `${stages.length} ${stages.length === 1 ? "etapa" : "etapas"} · parada após ${funnel.stale_days} dias${funnel.is_primary ? " · funil principal" : ""}`,
      "muted",
    ),
    el("span", automationSummary(funnel, stages), "muted"),
  );
  const funnelActions = el("div", null, "manage-actions");
  const editButton = button("Editar funil", () => editFunnel(funnel));
  editButton.prepend(icon("edit"));
  funnelActions.append(editButton);
  if (!funnel.is_primary) {
    const archive = button("Arquivar", () => {
      dialog(
        `Arquivar funil "${funnel.name}"?`,
        [el("p", "O funil sai do quadro. Negociações e histórico são preservados.")],
        () => api(`/funnels/${funnel.id}/archive`, "POST"),
      );
      $("dialog-save").textContent = "Arquivar funil";
      $("dialog-save").classList.add("danger");
    });
    archive.className = "danger-ghost";
    archive.prepend(icon("archive"));
    funnelActions.append(archive);
  }
  header.append(info, funnelActions);

  const list = el("ol", null, "manage-stages");
  list.setAttribute("aria-label", "Etapas do funil");
  stages.forEach((stage, index) => {
    const row = el("li", null, "manage-stage");
    const order = el("div", null, "manage-order");
    const up = iconButton("up", "Mover para cima", () => moveStage(stage, -1));
    const down = iconButton("down", "Mover para baixo", () => moveStage(stage, 1));
    up.disabled = index === 0;
    down.disabled = index === stages.length - 1;
    order.append(up, down);
    const name = el("button", null, "manage-stage-name");
    name.type = "button";
    name.title = "Editar etapa";
    name.onclick = () => editStage(stage);
    name.append(...stageOption(stage));
    const actions = el("div", null, "manage-actions");
    actions.append(iconButton("edit", `Editar ${stage.name}`, () => editStage(stage)));
    const archive = iconButton(
      "archive",
      stages.length < 2 ? "O funil precisa de pelo menos uma etapa" : `Arquivar ${stage.name}`,
      () => archiveStage(stage),
      "danger-ghost",
    );
    archive.disabled = stages.length < 2;
    actions.append(archive);
    row.append(order, name, actions);
    list.append(row);
  });

  // Criação rápida: nome e Enter; cor e tipo continuam editáveis depois.
  const quick = el("div", null, "manage-add");
  const input = el("input");
  input.placeholder = "Nome da nova etapa";
  input.maxLength = 100;
  input.setAttribute("aria-label", "Nome da nova etapa");
  const add = button("Adicionar etapa", async () => {
    const name = input.value.trim();
    if (!name) return input.focus();
    add.disabled = true;
    try {
      const last = Math.max(0, ...stages.map((s) => Number(s.position)));
      await api(`/funnels/${selected}/stages`, "POST", {
        name,
        color: STAGE_COLORS[stages.length % STAGE_COLORS.length],
        kind: "open",
        position: last + 1024,
      });
      await load(true);
      manage();
      $("dialog-content").querySelector(".manage-add input")?.focus();
    } finally {
      add.disabled = false;
    }
  });
  add.className = "primary";
  add.prepend(icon("plus"));
  input.onkeydown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      add.click();
    }
  };
  quick.append(input, add);

  const footer = el("div", null, "manage-footer");
  const create = button("Novo funil", () => editFunnel());
  create.prepend(icon("plus"));
  const reasons = button("Motivos de perda", lossReasons);
  const settings = button("Configuração da conta", accountSettings);
  settings.prepend(icon("settings"));
  footer.append(create, reasons, settings);

  dialog("Gerenciar funil", [
    header,
    el("h3", "Etapas", "manage-section-title"),
    list,
    quick,
    footer,
  ]);
  $("dialog").classList.add("manage-dialog");
}
$("manage").onclick = manage;
const actionNames = {
  cartao_movido: "Cartão movimentado",
  tarefa_criada: "Tarefa criada",
  tarefa_editada: "Tarefa editada",
  tarefa_encerrada: "Tarefa concluída",
  contato_importado: "Contato importado",
  sincronizado: "Sincronização concluída",
  sincronizacao_falhou: "Falha na sincronização",
  conflito_externo: "Conflito com alteração externa",
  movimento_externo: "Etapa alterada no Chatwoot",
  atributos_importados: "Atributos importados",
  alteracao_externa: "Alteração externa",
  vencimento_atualizado: "Vencimento atualizado",
  funil_criado: "Funil criado",
  funil_editado: "Funil editado",
  funil_arquivado: "Funil arquivado",
  etapa_criada: "Etapa criada",
  etapa_editada: "Etapa editada",
  etapa_arquivada: "Etapa arquivada",
  configuracao_atualizada: "Configuração atualizada",
  negociacao_excluida: "Negociação excluída",
  negociacao_restaurada: "Negociação restaurada",
  cartao_criado: "Cartão criado",
  etapa_arquivada_movimento: "Cartão transferido por arquivamento",
};
async function history(contact) {
  editingCardId = null;
  refreshHistory = () => fetchPage(true);
  const [funnel, f] = selectField("Funil", [
    ["", "Todos"],
    ...data.funnels.map((x) => [x.id, x.name]),
  ]);
  const [stage, s] = selectField("Etapa", [
    ["", "Todas"],
    ...data.stages.map((x) => [x.id, x.name]),
  ]);
  const [author, a] = field("ID do autor (opcional)", "number", "");
  const [result, r] = selectField("Evento", [
    ["", "Todos"],
    ["sincronizado", "Sincronizado"],
    ["sincronizacao_falhou", "Falha de sincronização"],
    ["conflito_externo", "Conflito"],
    ["cartao_movido", "Movimentação"],
    ["tarefa_criada", "Tarefa criada"],
  ]);
  const list = el("div");
  let before;
  const fetchPage = async (reset) => {
    if (reset) {
      before = undefined;
      list.replaceChildren();
    }
    const q = new URLSearchParams();
    if (contact) q.set("contact_id", contact);
    if (before) q.set("before", before);
    if (f.value) q.set("funnel_id", f.value);
    if (s.value) q.set("stage_id", s.value);
    if (a.value) q.set("actor_id", a.value);
    if (r.value) q.set("action", r.value);
    const rows = await api("/history?" + q);
    for (const row of rows) {
      const item = el("div", null, "history-item");
      item.append(
        el("strong", actionNames[row.action] || row.action),
        el(
          "div",
          `${row.actor_name} · ${new Date(row.created_at).toLocaleString("pt-BR")} · Contato ${row.contact_id || "—"}`,
          "muted",
        ),
      );
      list.append(item);
    }
    before = rows.at(-1)?.id;
    more.hidden = rows.length < 50;
    if (!rows.length && reset) list.append(el("p", "Nenhum registro."));
  };
  const more = button("Carregar mais", () => fetchPage(false));
  [f, s, a, r].forEach(
    (input) => (input.onchange = () => fetchPage(true).catch(showError)),
  );
  dialog("Histórico", [funnel, stage, author, result, list, more]);
  await fetchPage(true);
}
$("history").onclick = () =>
  history(compact ? contactContext : undefined).catch(showError);
$("retry").onclick = () =>
  api("/sync/retry", "POST")
    .then(async () => {
      notice("Nova tentativa agendada.");
      await load();
    })
    .catch(showError);
$("reimport").onclick = async () => {
  try {
    const status = await api("/provisioning");
    if (["pending", "running", "failed"].includes(status.import_status)) {
      dialog("Retomar importação", [
        el("p", `${status.imported_count} contatos processados. ${status.import_error || "Importação em andamento."}`),
      ], async () => { await api("/import", "POST", { resume: true }); });
      return;
    }
    const estimate = await api("/import/estimate");
    const [modeLabel, mode] = selectField("O que importar", [
      ["metadata", "Somente metadados dos contatos"],
      ["cards", "Metadados e negociações ausentes no funil"],
    ], "metadata");
    const [funnelLabel, funnel] = selectField("Funil de destino", data.funnels
      .filter((f) => !f.archived).map((f) => [f.id, f.name]), selected);
    const [stageLabel, stage] = selectField("Etapa de destino", []);
    const update = () => {
      funnelLabel.hidden = stageLabel.hidden = mode.value !== "cards";
      options(stage, data.stages.filter((s) => !s.archived && s.kind === "open" &&
        s.funnel_id === Number(funnel.value)).map((s) => [s.id, s.name]));
    };
    mode.onchange = funnel.onchange = update;
    update();
    dialog("Importar contatos", [
      el("p", `Estimativa: ${estimate.contacts} contatos. A importação pode ser retomada após falhas.`),
      el("p", "Etapas e tarefas existentes permanecem locais. Negociações existentes não serão duplicadas."),
      modeLabel, funnelLabel, stageLabel,
    ], async () => {
      await api("/import", "POST", { mode: mode.value,
        funnel_id: mode.value === "cards" ? Number(funnel.value) : null,
        stage_id: mode.value === "cards" ? Number(stage.value) : null });
      notice("Importação agendada; consulte o progresso na configuração da conta.");
    });
  } catch (error) { showError(error); }
};
const phaseStatus = (status) => ({
  ready: "pronto", pending: "na fila", failed: "falhou", idle: "não iniciada",
  running: "em andamento", complete: "concluída",
}[status] || status);
async function accountSettings() {
  try {
    const state = await api("/session");
    const provisioning = await api("/provisioning");
    const mappings = ["origem", "campanha", "temperatura"].map((key) => {
      const [label, input] = field(`Atributo de ${key} (vazio desativa)`, "text",
        provisioning.attribute_mappings[key] || "");
      return { key, label, input };
    });
    const [limitLabel, limit] = field("Contatos por lote e por conta", "number", provisioning.processing_limit);
    limit.min = 1; limit.max = 100;
    const [label, token] = field(
      "Novo token de serviço (opcional)",
      "password",
      "",
    );
    token.autocomplete = "off";
    dialog(
      "Configuração da conta",
      [
        el(
          "p",
          `Conta ${account} · ${state.activation?.imported_count || 0} contatos importados.`,
        ),
        el("p", "Fuso horário: Brasília (America/Sao_Paulo)."),
        el("p", `Provisionamento: ${phaseStatus(provisioning.activation_status)}. ${provisioning.activation_error || ""}`),
        el("p", `Importação: ${phaseStatus(provisioning.import_status)} · ${provisioning.imported_count} contatos. ${provisioning.import_error || ""}`),
        ...provisioning.provisioning_warnings.map((w) => el("p", w)),
        ...mappings.map((m) => m.label), limitLabel,
        el("p", "Recursos registrados nesta conta:"),
        ...provisioning.resources.map((r) => el("p", `${r.resource_key}: ${r.ownership === "created" ? "criado pelo Kanban" : "preexistente"}`)),
        button("Repetir provisionamento", async () => {
          await api("/provisioning/retry", "POST"); closeDialog(); await init();
        }),
        label,
        button(state.activation?.enabled ? "Desativar conta" : "Habilitar conta", async () => {
          await api("/activation", "PUT", { enabled: !state.activation?.enabled });
          closeDialog();
          clearRestrictedData();
          await init();
        }),
      ],
      async () => {
        const values = Object.fromEntries(mappings.map((m) => [m.key, m.input.value.trim() || null]));
        if (JSON.stringify(values) !== JSON.stringify(provisioning.attribute_mappings) ||
            Number(limit.value) !== provisioning.processing_limit) {
          await api("/provisioning", "PUT", { mappings: values, processing_limit: Number(limit.value) });
        }
        if (token.value) await api("/activate", "POST", { token: token.value });
        token.value = "";
        await init();
      },
    );
  } catch (error) {
    showError(error);
  }
}
$("activate-form").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api("/activate", "POST", { token: $("service-token").value });
    $("service-token").value = "";
    notice("Ativação agendada. A importação de contatos é uma ação separada.");
    await init();
  } catch (err) {
    showError(err);
  }
};
window.addEventListener("message", (event) => {
  if (event.origin !== location.origin || event.source !== parent) return;
  if (event.data?.event === "kanban:visibility") {
    // Escondido pelo loader: sem SSE; ao reaparecer, reconecta e atualiza.
    if (event.data.visible) {
      if (!stream || stream.readyState === EventSource.CLOSED) connect();
    } else {
      clearTimeout(reconnectTimer);
      stream?.close();
      stream = null;
      connectionStatus("Pausado enquanto oculto", "connecting");
    }
    return;
  }
  let context = event.data;
  try {
    if (typeof context === "string") context = JSON.parse(context);
  } catch {
    return;
  }
  if (compact && context?.event === "appContext") {
    const conversation = context.data?.conversation;
    if (
      conversation?.account_id != null &&
      Number(conversation.account_id) !== account
    )
      return;
    const id = context.data?.contact?.id || conversation?.meta?.sender?.id;
    if (Number.isSafeInteger(id) && id > 0) {
      contactContext = id;
      load().catch(showError);
    }
  }
});
let reconnectAttempt = 0;
function scheduleReconnect() {
  const delay = Math.min(30000, 1000 * 2 ** Math.min(reconnectAttempt++, 5));
  reconnectTimer = setTimeout(connect, delay + Math.random() * 1000);
}
let stream = null;
function connect() {
  clearTimeout(reconnectTimer);
  stream?.close();
  const source = new EventSource(`/kanban/events?account=${account}`);
  stream = source;
  source.addEventListener("ready", () => {
    reconnectAttempt = 0;
    connectionStatus("Atualização em tempo real", "ready");
    load().catch(showError);
  });
  source.addEventListener("change", () => {
    load(true).catch(showError);
  });
  source.addEventListener("expired", () => {
    source.close();
    clearRestrictedData();
    connectionStatus("Sessão expirada", "expired");
    notice("Entre novamente no Chatwoot para continuar.");
  });
  source.addEventListener("unavailable", () => {
    source.close();
    clearRestrictedData();
    connectionStatus("Chatwoot indisponível · reconectando…", "connecting");
    scheduleReconnect();
  });
  source.onerror = () => {
    source.close();
    connectionStatus("Reconectando…", "connecting");
    scheduleReconnect();
  };
  window.addEventListener("pagehide", () => source.close(), { once: true });
}
let prefetchedBoard;
async function init() {
  // Primeira abertura: quadro e sessão em paralelo; o quadro já valida a sessão.
  if (loadGeneration === 0 && !prefetchedBoard) {
    const query = boardQuery();
    prefetchedBoard = { query, result: api(query).catch(() => null) };
  }
  user = await api("/session");
  const admin = user.role === "administrator";
  ["manage", "reimport"].forEach((id) => ($(id).hidden = !admin));
  $("activation").hidden = Boolean(user.activation) || !admin;
  if (!user.activation && !admin)
    notice("Peça a um administrador para ativar o Kanban nesta conta.");
  if (user.activation && user.activation.activation_status !== "ready") {
    notice(
      `Provisionamento: ${user.activation.activation_error || "em andamento"}. Consulte a configuração da conta.`,
    );
    setTimeout(() => {
      if (!editing) init().catch(showError);
    }, 5000);
  }
  if (
    user.activation?.activation_status === "ready" &&
    $("notice").textContent.startsWith("Provisionamento:")
  )
    notice("");
  if (user.activation?.enabled === false) {
    clearRestrictedData();
    notice("Kanban desativado nesta conta.");
    if (admin) accountSettings();
    return;
  }
  if (user.activation?.activation_status !== "ready") {
    clearRestrictedData();
    return;
  }
  await load();
  const focusCard = Number(params.get("card"));
  if (focusCard) {
    const card = data.cards.find((c) => c.id === focusCard) || await api(`/cards/${focusCard}`);
    if (card) {
      selected = card.funnel_id;
      renderFunnelPicker();
      render();
      details(card);
    }
  }
}
if (compact) {
  document.body.classList.add("compact");
  parent.postMessage("chatwoot-dashboard-app:fetch-info", location.origin);
}
init().then(connect).catch(showError);

$("more-actions").addEventListener("click", (event) => {
  if (event.target.closest("button")) $("more-actions").open = false;
});
document.addEventListener("click", (event) => {
  if (!$("more-actions").contains(event.target)) $("more-actions").open = false;
});
const activityTimer = setInterval(() => {
  document.querySelectorAll("[data-activity-at]").forEach((node) => {
    node.textContent = relativeTime(node.dataset.activityAt);
  });
}, 60000);
window.addEventListener("pagehide", () => clearInterval(activityTimer), {
  once: true,
});
