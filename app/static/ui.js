"use strict";
// Componentes compartilhados pelas páginas do Pipeline (Kanban e Métricas).
(function (root) {
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text != null) node.textContent = String(text);
    if (cls) node.className = cls;
    return node;
  };
  // Traços do Lucide usados pelos componentes (chevron-down e check).
  const paths = { down: "m6 9 6 6 6-6", check: "m5 12 4 4L19 6" };
  const icon = (name) => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", "icon");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS(svg.namespaceURI, "path");
    path.setAttribute("d", paths[name]);
    svg.append(path);
    return svg;
  };
  // Menu de filtro no padrão DropdownMenu do Chatwoot 4.18. O <select> continua
  // como fonte do valor (e dos eventos de filtro), só que invisível.
  function filterMenu(select, allLabel, emptyText, dotColor) {
    const root = el("div", null, "filter"),
      trigger = el("button", null, "filter-trigger"),
      text = el("span", null, "filter-text"),
      menu = el("div", null, "filter-menu"),
      search = el("input"),
      list = el("div", null, "filter-options");
    const name = select.getAttribute("aria-label");
    trigger.type = "button";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    trigger.append(text, icon("down"));
    search.type = "search";
    search.placeholder = "Pesquisar...";
    search.setAttribute("aria-label", `Pesquisar em ${name}`);
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-label", name);
    menu.append(search, list);
    menu.hidden = true;
    select.replaceWith(root);
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");
    root.append(select, trigger, menu);
    const choices = () =>
      [...select.options].map((o) => [o.value, o.value ? o.textContent : allLabel]);
    const sync = () => {
      const current = select.selectedOptions[0];
      const chosen = select.value && current ? current.textContent : "";
      text.textContent = chosen || select.options[0]?.textContent || name;
      trigger.setAttribute("aria-label", chosen ? `${name}: ${chosen}` : name);
      root.classList.toggle("active", Boolean(chosen));
    };
    const items = () => [...list.querySelectorAll("[role=option]")];
    const close = (focus = true) => {
      if (menu.hidden) return;
      menu.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
      if (focus) trigger.focus();
    };
    const choose = (value) => {
      if (select.value !== value) {
        select.value = value;
        select.dispatchEvent(new Event("input", { bubbles: true }));
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
      close();
    };
    const render = () => {
      const query = search.value.trim().toLocaleLowerCase("pt-BR");
      const all = choices();
      const rows = all.filter(([v, t], i) => i === 0 || t.toLocaleLowerCase("pt-BR").includes(query));
      search.hidden = all.length <= 8;
      list.replaceChildren(
        ...rows.map(([value, label]) => {
          const option = el("div", null, "filter-option");
          option.setAttribute("role", "option");
          option.tabIndex = -1;
          option.setAttribute("aria-selected", String(value === select.value));
          const color = value && dotColor?.(value);
          if (color) {
            const dot = el("span", null, "label-dot");
            dot.style.setProperty("--label-color", color);
            option.append(dot);
          }
          option.append(el("span", label, "filter-label"));
          if (value === select.value) option.append(icon("check"));
          option.onclick = () => choose(value);
          return option;
        }),
      );
      if (all.length === 1) list.append(el("p", emptyText, "filter-empty"));
      else if (rows.length === 1 && query) list.append(el("p", "Nenhum resultado encontrado.", "filter-empty"));
    };
    const open = () => {
      search.value = "";
      render();
      menu.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
      (search.hidden ? items().find((o) => o.getAttribute("aria-selected") === "true") || items()[0] : search).focus();
    };
    trigger.onclick = () => (menu.hidden ? open() : close());
    trigger.onkeydown = (event) => {
      if (["ArrowDown", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        open();
      }
    };
    search.oninput = render;
    menu.onkeydown = (event) => {
      const options = items(),
        index = options.indexOf(document.activeElement);
      if (event.key === "Escape") {
        event.stopPropagation();
        event.preventDefault();
        close();
      } else if (["ArrowDown", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        options[(index + step + options.length) % options.length]?.focus();
      } else if ((event.key === "Enter" || event.key === " ") && index >= 0) {
        event.preventDefault();
        options[index].click();
      } else if (event.key === "Tab") close(false);
    };
    root.addEventListener("focusout", () =>
      setTimeout(() => {
        if (!root.contains(document.activeElement)) close(false);
      }, 0),
    );
    document.addEventListener("click", (event) => {
      if (!root.contains(event.target)) close(false);
    });
    select.addEventListener("change", sync);
    new MutationObserver(() => {
      sync();
      if (!menu.hidden) render();
    }).observe(select, { childList: true });
    sync();
  }
  root.PipelineUI = { filterMenu };
})(window);
