"use strict";
// Configurações da conta do Pipeline (ADR-045): o que não precisa ficar no
// Kanban, em Tarefas ou em Métricas. Só administradores alteram.
const $ = (id) => document.getElementById(id);
const account = Number(new URLSearchParams(location.search).get("account"));
const STATE = {
  ready: ["Pronto", "ok"],
  pending: ["Configurando…", "wait"],
  failed: ["Precisa de atenção", "error"],
};
const IMPORT = {
  idle: "Nenhuma importação feita ainda.",
  pending: "Importação na fila.",
  running: "Importação em andamento.",
  failed: "Importação interrompida.",
  complete: "Importação concluída.",
};
const RESOURCE = { attribute: "Atributo de contato", webhook: "Webhook" };
let provisioning, pollTimer, toastTimer;
const el = (tag, text, cls) => {
  const node = document.createElement(tag);
  if (text != null) node.textContent = String(text);
  if (cls) node.className = cls;
  return node;
};
async function api(path, method = "GET", body) {
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
const message = (error) =>
  error.name === "TimeoutError"
    ? "A consulta demorou demais. Tente novamente."
    : error.message;
// Retorno curto de ação, como o Snackbar do Chatwoot: topo, centralizado, 2,5 s.
function toast(text) {
  clearTimeout(toastTimer);
  $("toast").textContent = text;
  $("toast").hidden = false;
  toastTimer = setTimeout(() => ($("toast").hidden = true), 2500);
}
function openPage(page) {
  parent.postMessage({ event: "kanban:open-page", account, page }, location.origin);
}
async function busy(button, label, fn) {
  const text = button.textContent;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  button.textContent = label;
  try {
    await fn();
  } finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
    button.textContent = text;
  }
}
// Envio padrão de um cartão: erro junto do formulário, sucesso no aviso do topo.
function handle(form, label, fn) {
  const feedback = form.querySelector(".field-error");
  form.onsubmit = (event) => {
    event.preventDefault();
    if (feedback) feedback.hidden = true;
    const submit = form.querySelector("button.primary, button:not([type])");
    return busy(submit, label, fn).catch((error) => {
      if (!feedback) return toast(message(error));
      feedback.textContent = message(error);
      feedback.hidden = false;
    });
  };
}
function gate(text) {
  $("settings").hidden = true;
  $("status").textContent = text;
  const open = el("button", "Abrir Kanban", "primary gate-action");
  open.type = "button";
  open.onclick = () => openPage("kanban");
  $("status").after(open);
}
function renderState() {
  const p = provisioning;
  const [label, tone] = STATE[p.activation_status] || [p.activation_status, "wait"];
  const list = el("dl", null, "state-list");
  const badge = el("span", label, `badge ${tone}`);
  for (const [term, value] of [
    ["Situação", badge],
    ["Contatos importados", String(p.imported_count ?? 0)],
    ["Fuso horário", "Brasília (America/Sao_Paulo)"],
  ]) {
    list.append(el("dt", term));
    const dd = el("dd");
    dd.append(value);
    list.append(dd);
  }
  const content = [list];
  if (p.activation_error) content.push(el("p", `Motivo: ${p.activation_error}.`, "state-error"));
  for (const warning of p.provisioning_warnings || []) content.push(el("p", warning, "muted"));
  if (p.activation_status !== "ready") {
    const retry = el("button", "Tentar novamente");
    retry.type = "button";
    retry.onclick = () =>
      busy(retry, "Enviando…", async () => {
        await api("/provisioning/retry", "POST");
        toast("Configuração reaplicada; acompanhe a situação.");
        await refresh();
      }).catch((error) => toast(message(error)));
    const actions = el("div", null, "settings-actions");
    actions.append(retry);
    content.push(actions);
  }
  $("state").replaceChildren(...content);
}
function renderImport() {
  const p = provisioning;
  const count = p.imported_count ? ` ${p.imported_count} contatos processados.` : "";
  $("import-state").textContent =
    (IMPORT[p.import_status] || p.import_status) + count + (p.import_error ? ` ${p.import_error}` : "");
  const actions = [];
  const ready = p.activation_status === "ready";
  if (["pending", "running", "failed"].includes(p.import_status)) {
    const resume = el("button", "Retomar importação", "primary");
    resume.type = "button";
    resume.disabled = !ready;
    resume.onclick = () =>
      busy(resume, "Enviando…", async () => {
        await api("/import", "POST", { resume: true });
        toast("Importação retomada.");
        await refresh();
      }).catch((error) => toast(message(error)));
    actions.push(resume);
  } else if ($("import").hidden) {
    const start = el("button", "Importar contatos", "primary");
    start.type = "button";
    start.disabled = !ready;
    start.title = ready ? "" : "Disponível quando a configuração estiver pronta";
    start.onclick = () => busy(start, "Consultando…", openImport).catch((error) => toast(message(error)));
    actions.push(start);
  }
  $("import-actions").replaceChildren(...actions);
}
function renderResources() {
  $("resources").replaceChildren(
    ...(provisioning.resources || []).map((r) => {
      const item = el("li");
      item.append(
        el("span", RESOURCE[r.resource_type] || r.resource_type, "resource-type"),
        el("code", r.resource_key),
        el("span", r.ownership === "created" ? "criado pelo Pipeline" : "já existia", "muted"),
      );
      return item;
    }),
  );
}
function render() {
  const form = $("attributes");
  for (const key of ["origem", "campanha", "temperatura"])
    if (document.activeElement !== form.elements[key])
      form.elements[key].value = provisioning.attribute_mappings?.[key] || "";
  if (document.activeElement !== $("batch").elements.limit)
    $("batch").elements.limit.value = provisioning.processing_limit;
  renderState();
  renderImport();
  renderResources();
}
async function refresh() {
  clearTimeout(pollTimer);
  provisioning = await api("/provisioning");
  render();
  // Enquanto configura, a situação se atualiza sozinha.
  if (provisioning.activation_status === "pending")
    pollTimer = setTimeout(() => refresh().catch(() => {}), 5000);
}
async function openImport() {
  const [estimate, board] = await Promise.all([
    api("/import/estimate"),
    api("/board?limit=1"),
  ]);
  const form = $("import");
  const funnels = board.funnels.filter((f) => !f.archived);
  const fill = (select, items) =>
    select.replaceChildren(
      ...items.map(([value, text]) => {
        const option = el("option", text);
        option.value = value;
        return option;
      }),
    );
  fill(form.elements.funnel, funnels.map((f) => [f.id, f.name]));
  const stagesFor = () =>
    fill(
      form.elements.stage,
      board.stages
        .filter((s) => !s.archived && s.kind === "open" && s.funnel_id === Number(form.elements.funnel.value))
        .map((s) => [s.id, s.name]),
    );
  stagesFor();
  form.elements.funnel.onchange = stagesFor;
  const target = form.querySelector(".import-target");
  for (const radio of form.elements.mode)
    radio.onchange = () => (target.hidden = form.elements.mode.value !== "cards");
  target.hidden = form.elements.mode.value !== "cards";
  form.querySelector("legend").textContent = `O que importar · ${estimate.contacts} contatos no Chatwoot`;
  form.hidden = false;
  renderImport();
  form.querySelector("input[name=mode]:checked").focus();
}
handle($("attributes"), "Salvando…", async () => {
  const form = $("attributes");
  const mappings = Object.fromEntries(
    ["origem", "campanha", "temperatura"].map((k) => [k, form.elements[k].value.trim() || null]),
  );
  await api("/provisioning", "PUT", { mappings, processing_limit: provisioning.processing_limit });
  toast("Atributos salvos. A configuração do Chatwoot está sendo reaplicada.");
  await refresh();
});
handle($("batch"), "Salvando…", async () => {
  await api("/provisioning", "PUT", {
    mappings: provisioning.attribute_mappings,
    processing_limit: Number($("batch").elements.limit.value),
  });
  toast("Tamanho do lote salvo.");
  await refresh();
});
handle($("reasons"), "Salvando…", async () => {
  const input = $("reasons").elements.reasons;
  const saved = await api("/metrics/configuration", "PUT", {
    loss_reasons: input.value.split("\n").map((s) => s.trim()).filter(Boolean),
  });
  input.value = saved.loss_reasons.join("\n");
  toast("Motivos de perda salvos.");
});
handle($("import"), "Agendando…", async () => {
  const form = $("import");
  const cards = form.elements.mode.value === "cards";
  await api("/import", "POST", {
    mode: form.elements.mode.value,
    funnel_id: cards ? Number(form.elements.funnel.value) : null,
    stage_id: cards ? Number(form.elements.stage.value) : null,
  });
  form.hidden = true;
  toast("Importação agendada.");
  await refresh();
});
$("import").querySelector("[data-cancel]").onclick = () => {
  $("import").hidden = true;
  renderImport();
};
handle($("token"), "Validando…", async () => {
  const input = $("token").elements.token;
  try {
    await api("/activate", "POST", { token: input.value });
  } catch (error) {
    if (error.status === 400)
      error.message = "Este token não tem acesso de administrador a esta conta. Confira se ele foi copiado do perfil de um administrador.";
    throw error;
  }
  input.value = "";
  toast("Token atualizado. A configuração do Chatwoot está sendo reaplicada.");
  await refresh();
});
$("disable").onclick = () => $("confirm").showModal();
$("confirm").addEventListener("close", async () => {
  if ($("confirm").returnValue !== "confirm") return;
  try {
    await api("/activation", "PUT", { enabled: false });
    clearTimeout(pollTimer);
    gate("O Pipeline foi desativado nesta conta. Para reativar, informe o token de acesso no Kanban.");
  } catch (error) {
    toast(message(error));
  }
});
$("retry").onclick = () =>
  busy($("retry"), "Enviando…", async () => {
    await api("/provisioning/retry", "POST");
    toast("Configuração reaplicada; acompanhe a situação.");
    await refresh();
  }).catch((error) => toast(message(error)));
async function load() {
  try {
    const session = await api("/session");
    if (session.role !== "administrator") {
      $("status").textContent = "Apenas administradores da conta podem alterar as configurações do Pipeline.";
      return;
    }
    if (!session.activation) return gate("O Pipeline ainda não foi ativado nesta conta. Ative pelo Kanban.");
    if (session.activation.enabled === false)
      return gate("O Pipeline está desativado nesta conta. Para reativar, informe o token de acesso no Kanban.");
    await refresh();
    // Motivos de perda dependem da conta pronta; sem ela, o cartão explica.
    try {
      const config = await api("/metrics/configuration");
      $("reasons").elements.reasons.value = config.loss_reasons.join("\n");
    } catch {
      $("reasons").elements.reasons.disabled = true;
      $("reasons").querySelector("button").disabled = true;
      $("reasons").querySelector(".field-error").textContent = "Disponível quando a configuração estiver pronta.";
      $("reasons").querySelector(".field-error").hidden = false;
    }
    $("status").textContent = "";
    $("settings").hidden = false;
  } catch (error) {
    $("status").textContent =
      error.status === 401 ? "Sessão expirada. Entre novamente no Chatwoot." : message(error);
  }
}
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("confirm").open)
    parent.postMessage({ event: "kanban:close" }, location.origin);
});
load();
