"use strict";
const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const account = Number(params.get("account"));
const compact = params.has("compact");
let user,
  data = { funnels: [], stages: [], cards: [], contacts: [] },
  selected,
  contactContext;
let editing = false,
  pendingRefresh = false,
  dragged,
  moving = false,
  landingCard,
  landingTimer,
  reconnectTimer;
const { money, dateBR } = window.KanbanHelpers;
const el = (tag, text, cls) => {
  const n = document.createElement(tag);
  if (text != null) n.textContent = String(text);
  if (cls) n.className = cls;
  return n;
};
const metadata = {
  labels: new Map(),
  agents: new Map(),
  conversations: new Map(),
};
let metadataLoaded = false,
  metadataLoading;
function icon(name) {
  const paths = {
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
    headers,
  });
  if (!response.ok) throw new Error("Metadados indisponíveis");
  return response.json();
}
function enrichCards() {
  if (metadataLoading) return;
  metadataLoading = (async () => {
    if (!metadataLoaded) {
      const results = await Promise.allSettled([
        nativeApi("/labels"),
        nativeApi("/agents"),
      ]);
      if (results[0].status === "fulfilled")
        for (const label of results[0].value.payload || [])
          metadata.labels.set(label.title, label);
      if (results[1].status === "fulfilled")
        for (const agent of results[1].value.payload || results[1].value || [])
          metadata.agents.set(agent.id, agent);
      metadataLoaded = results.every((result) => result.status === "fulfilled");
    }
    const ids = [
      ...new Set(
        data.cards
          .filter((card) => card.funnel_id === selected)
          .map((card) => card.conversation_id)
          .filter((id) => id && !metadata.conversations.has(id)),
      ),
    ];
    await Promise.all(
      Array.from({ length: Math.min(4, ids.length) }, async () => {
        while (ids.length) {
          const id = ids.shift();
          try {
            metadata.conversations.set(
              id,
              await nativeApi(`/conversations/${id}`),
            );
          } catch {
            /* Exibir canal genérico sem inventar informação. */
          }
        }
      }),
    );
    if (!editing && !dragged) render();
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
  notice(error.message || String(error));
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
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : `Falha ${response.status}. Atualize e tente novamente.`,
    );
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
function dialog(title, content, save) {
  editing = true;
  $("dialog").classList.remove("deal-dialog");
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
      closeDialog();
      await load();
    } catch (e) {
      showError(e);
    } finally {
      $("dialog-save").disabled = false;
    }
  };
  if (!$("dialog").open) $("dialog").showModal();
}
function closeDialog() {
  $("dialog").close();
  editing = false;
  if (pendingRefresh) {
    pendingRefresh = false;
    load().catch(showError);
  }
}
$("dialog-close").onclick = closeDialog;
$("dialog").addEventListener("cancel", () => {
  editing = false;
  if (pendingRefresh) {
    pendingRefresh = false;
    load().catch(showError);
  }
});
function navigate(card) {
  const resource = card.conversation_id ? "conversations" : "contacts",
    id = card.conversation_id || card.contact_id;
  if (compact)
    window.top.location.assign(`/app/accounts/${account}/${resource}/${id}`);
  else {
    const message = { event: "kanban:navigate", account, resource, id };
    if (window.KanbanHelpers.validNavigation(message, account))
      parent.postMessage(message, location.origin);
  }
}
function taskDialog(card) {
  const [msg, m] = field("Tarefa", "textarea", card.message);
  m.required = true;
  m.maxLength = 4000;
  const [due, d] = field(
    "Vencimento — horário de Brasília",
    "date",
    card.due_date,
  );
  d.required = true;
  const content = [msg, due];
  if (card.task_id)
    content.push(
      button("Concluir tarefa", async () => {
        await api(`/contacts/${card.contact_id}/task/close`, "POST", {
          version: card.task_version,
        });
        closeDialog();
        await load();
      }),
    );
  dialog(`Tarefa · ${card.name}`, content, () =>
    api(`/contacts/${card.contact_id}/task`, "PUT", {
      mensaje: m.value,
      fecha_vencimiento: d.value,
      version: card.task_version || null,
    }),
  );
}
function details(card) {
  const [stage, s] = selectField(
    "Etapa",
    data.stages
      .filter((x) => x.funnel_id === card.funnel_id)
      .map((x) => [x.id, x.name]),
    card.stage_id,
  );
  const [value, v] = field(
    "Valor em reais",
    "number",
    (card.value_cents / 100).toFixed(2),
  );
  v.min = 0;
  v.step = "0.01";
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
    button("Abrir conversa ou contato", () => navigate(card)),
    button("Ver histórico deste contato", () => history(card.contact_id)),
    button(card.task_id ? "Editar tarefa" : "Criar tarefa", () =>
      taskDialog(card),
    ),
  ];
  dialog(card.name, content, () =>
    api(`/cards/${card.id}`, "PATCH", {
      version: card.version,
      stage_id: Number(s.value),
      value_cents: Math.round(Number(v.value) * 100),
    }),
  );
}
const syncLabel = (status) =>
  ({
    synced: "Sincronizado",
    pending: "Sincronização pendente",
    failed: "Falha na sincronização",
  })[status] || status;
function render() {
  const query = $("search").value.toLocaleLowerCase("pt-BR"),
    assignee = $("assignee").value,
    label = $("label").value,
    task = $("task-filter").value;
  const cards = data.cards.filter(
    (c) =>
      c.funnel_id === selected &&
      (!compact || c.contact_id === contactContext) &&
      (!query ||
        [c.name, c.phone, c.message].some((v) =>
          String(v || "")
            .toLocaleLowerCase("pt-BR")
            .includes(query),
        )) &&
      (!assignee || String(c.assignee_id) === assignee) &&
      (!label || c.labels.includes(label)) &&
      (!task || (task === "none" ? !c.task_id : c.due_state === task)),
  );
  const failures = data.cards.filter((card) => card.sync_status === "failed");
  const failedContacts = new Set(failures.map((card) => card.contact_id)).size;
  $("sync-warning").hidden = !failedContacts;
  $("sync-count").textContent =
    `${failedContacts} ${failedContacts === 1 ? "contato com falha de sincronização" : "contatos com falha de sincronização"}`;
  $("retry").hidden = !failedContacts || user?.role !== "administrator";
  $("board").replaceChildren();
  for (const stage of data.stages.filter((s) => s.funnel_id === selected)) {
    const column = el("section", null, "column");
    column.dataset.stageId = stage.id;
    const rows = cards.filter((c) => c.stage_id === stage.id);
    const head = el("div", null, "column-head");
    const dot = el("span", null, "dot");
    dot.style.backgroundColor = stage.color;
    head.append(
      dot,
      el("span", stage.name),
      el("span", rows.length, "count"),
      el(
        "span",
        money(rows.reduce((n, c) => n + c.value_cents, 0)),
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
      const conversation = metadata.conversations.get(card.conversation_id);
      const channelName =
        conversation?.meta?.channel ||
        conversation?.channel ||
        conversation?.inbox?.channel_type;
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
    $("board").append(column);
  }
  if (!data.funnels.length)
    $("board").append(
      el("p", "Aguardando ativação e importação dos contatos.", "empty"),
    );
  if (compact && !contactContext)
    $("board").replaceChildren(
      el(
        "p",
        "Abra uma conversa para visualizar os funis deste contato.",
        "empty",
      ),
    );
  $("summary").textContent =
    `${cards.length} ${cards.length === 1 ? "negociação" : "negociações"} · ${money(cards.reduce((n, c) => n + c.value_cents, 0))}`;
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
async function load() {
  if (editing || dragged || moving) {
    pendingRefresh = true;
    return;
  }
  data = await api("/board");
  if (!data.funnels.some((f) => f.id === selected))
    selected = data.funnels[0]?.id;
  renderFunnelPicker();
  options(
    $("assignee"),
    [
      ["", "Responsável"],
      ...new Map(
        data.cards
          .filter((c) => c.assignee_id)
          .map((c) => [c.assignee_id, c.assignee_name]),
      ).entries(),
    ],
    $("assignee").value,
  );
  options(
    $("label"),
    [
      ["", "Etiqueta"],
      ...[...new Set(data.cards.flatMap((c) => c.labels))].map((t) => [t, t]),
    ],
    $("label").value,
  );
  render();
  enrichCards();
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
        render();
        enrichCards();
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
["search", "assignee", "label", "task-filter"].forEach(
  (id) => ($(id).oninput = render),
);
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
    const existing = data.cards.find(
      (c) => c.contact_id === chosen?.id && c.funnel_id === funnelId,
    );
    const available = data.stages.filter((s) => s.funnel_id === funnelId);
    stageId = existing ? null : available[0]?.id;
    feedback.textContent = existing
      ? "Este contato já tem uma negociação neste funil. Escolha outro funil ou edite a negociação no quadro."
      : "";
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
      option.disabled = Boolean(existing);
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
function editFunnel(funnel) {
  const [name, n] = field("Nome do funil", "text", funnel?.name);
  n.required = true;
  const [pos, p] = field(
    "Ordem",
    "number",
    funnel?.position || data.funnels.length * 1024 + 1024,
  );
  const [stale, days] = field(
    "Considerar parada após quantos dias",
    "number",
    funnel?.stale_days || 7,
  );
  days.min = 1;
  days.max = 365;
  days.required = true;
  dialog(funnel ? "Editar funil" : "Novo funil", [name, pos, stale], () =>
    api(
      funnel ? `/funnels/${funnel.id}` : "/funnels",
      funnel ? "PUT" : "POST",
      { name: n.value, position: p.value, stale_days: Number(days.value) },
    ),
  );
}
function editStage(stage) {
  const [name, n] = field("Nome da etapa", "text", stage?.name);
  n.required = true;
  const [color, c] = field(
    "Cor",
    "color",
    stage?.color ||
      "#" +
        getComputedStyle(document.documentElement)
          .getPropertyValue("--blue-9")
          .trim()
          .split(/\s+/)
          .map((value) => Number(value).toString(16).padStart(2, "0"))
          .join(""),
  );
  const [kind, k] = selectField(
    "Classificação",
    [
      ["open", "Aberta"],
      ["won", "Ganha"],
      ["lost", "Perdida"],
    ],
    stage?.kind || "open",
  );
  const [position, p] = field(
    "Ordem",
    "number",
    stage?.position ||
      data.stages.filter((s) => s.funnel_id === selected).length * 1024 + 1024,
  );
  dialog(
    stage ? "Editar etapa" : "Nova etapa",
    [name, color, kind, position],
    () =>
      api(
        stage ? `/stages/${stage.id}` : `/funnels/${selected}/stages`,
        stage ? "PUT" : "POST",
        { name: n.value, color: c.value, kind: k.value, position: p.value },
      ),
  );
}
function manage() {
  const funnel = data.funnels.find((f) => f.id === selected);
  if (!funnel) return;
  const rows = [
    button("Criar funil", () => editFunnel()),
    button("Editar este funil", () => editFunnel(funnel)),
    button("Adicionar etapa", () => editStage()),
    button("Configuração da conta", accountSettings),
    button("Motivos de perda", async () => {
      const config = await api("/metrics/configuration");
      const [reasons, input] = field(
        "Um motivo por linha",
        "textarea",
        config.loss_reasons.join("\n"),
      );
      dialog(
        "Motivos de perda da conta",
        [el("p", "Outro com descrição estará sempre disponível."), reasons],
        () =>
          api("/metrics/configuration", "PUT", {
            loss_reasons: input.value
              .split("\n")
              .map((s) => s.trim())
              .filter(Boolean),
          }),
      );
    }),
  ];
  if (!funnel.is_primary)
    rows.push(
      button("Arquivar este funil", () =>
        dialog(
          "Arquivar funil",
          [
            el(
              "p",
              "Os cartões e o histórico serão preservados. O funil deixará de aparecer no quadro.",
            ),
          ],
          () => api(`/funnels/${funnel.id}/archive`, "POST"),
        ),
      ),
    );
  for (const stage of data.stages.filter((s) => s.funnel_id === selected)) {
    const row = el("div", null, "row");
    row.append(
      el("strong", stage.name),
      button("Editar", () => editStage(stage)),
      button("Arquivar", () => {
        const [destination, d] = selectField(
          "Mover cartões para",
          data.stages
            .filter((s) => s.funnel_id === selected && s.id !== stage.id)
            .map((s) => [s.id, s.name]),
        );
        dialog(
          "Arquivar etapa",
          [destination, el("p", "O histórico será preservado.")],
          () =>
            api(`/stages/${stage.id}/archive`, "POST", {
              destination_id: Number(d.value) || null,
            }),
        );
      }),
    );
    rows.push(row);
  }
  dialog("Gerenciar · " + funnel.name, rows);
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
  cartao_criado: "Cartão criado",
  etapa_arquivada_movimento: "Cartão transferido por arquivamento",
};
async function history(contact) {
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
$("reimport").onclick = () =>
  api("/import", "POST")
    .then(() =>
      notice("Importação agendada. O progresso aparece ao atualizar a conta."),
    )
    .catch(showError);
async function accountSettings() {
  try {
    const state = await api("/session");
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
        label,
      ],
      async () => {
        if (token.value) await api("/activate", "POST", { token: token.value });
        token.value = "";
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
    notice("Conta ativada. Importando contatos…");
    await init();
  } catch (err) {
    showError(err);
  }
};
window.addEventListener("message", (event) => {
  if (event.origin !== location.origin || event.source !== parent) return;
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
      render();
    }
  }
});
function connect() {
  clearTimeout(reconnectTimer);
  const source = new EventSource(`/kanban/events?account=${account}`);
  source.addEventListener("ready", () => {
    connectionStatus("Atualização em tempo real", "ready");
    load().catch(showError);
  });
  source.addEventListener("change", () => load().catch(showError));
  source.addEventListener("expired", () => {
    source.close();
    connectionStatus("Sessão expirada", "expired");
    notice("Entre novamente no Chatwoot para continuar.");
  });
  source.addEventListener("unavailable", () => {
    source.close();
    connectionStatus("Chatwoot indisponível · reconectando…", "connecting");
    reconnectTimer = setTimeout(connect, 5000);
  });
  source.onerror = () => {
    source.close();
    connectionStatus("Reconectando…", "connecting");
    reconnectTimer = setTimeout(connect, 5000);
  };
  window.addEventListener("pagehide", () => source.close(), { once: true });
}
async function init() {
  user = await api("/session");
  const admin = user.role === "administrator";
  ["manage", "reimport"].forEach((id) => ($(id).hidden = !admin));
  $("activation").hidden = Boolean(user.activation) || !admin;
  if (!user.activation && !admin)
    notice("Peça a um administrador para ativar o Kanban nesta conta.");
  if (user.activation && user.activation.activation_status !== "ready") {
    notice(
      `Importação: ${user.activation.imported_count} contatos · ${user.activation.activation_status === "failed" ? "falhou; use Importar contatos para repetir" : "em andamento"}`,
    );
    setTimeout(() => {
      if (!editing) init().catch(showError);
    }, 5000);
  }
  if (
    user.activation?.activation_status === "ready" &&
    $("notice").textContent.startsWith("Importação:")
  )
    notice("");
  await load();
  const focusCard = Number(params.get("card"));
  if (focusCard) {
    const card = data.cards.find((c) => c.id === focusCard);
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
