(() => {
  if (window.__chatwootKanbanInstalled) return;
  window.__chatwootKanbanInstalled = true;
  const menuId = "chatwoot-kanban-menu";
  const storageKey = "bee-pipeline-open";
  const pages = [
    { key: "kanban", label: "Kanban", path: "/kanban", icon: "columns-3" },
    {
      key: "tarefas",
      label: "Tarefas",
      path: "/kanban/tarefas",
      icon: "list-checks",
    },
    {
      key: "metricas",
      label: "Métricas",
      path: "/kanban/metricas",
      icon: "chart-column",
    },
    {
      key: "configuracoes",
      label: "Configurações",
      path: "/kanban/configuracoes",
      icon: "settings",
    },
  ];
  let overlay, frame, currentAccount, sidebar, selectedPage, templates;
  // Painel escondido da última página: reabrir não recarrega o quadro do zero.
  let parked = null;
  let menu,
    collapsed,
    flyout = false;
  let expanded = true;
  try {
    expanded = localStorage.getItem(storageKey) !== "false";
  } catch {
    /* Armazenamento pode estar desabilitado. */
  }
  const suppressed = new Map();
  const anchors = new Map();
  const activeTokens = new Set([
    "router-link-active",
    "router-link-exact-active",
    "active",
    "text-n-slate-12",
    "bg-n-alpha-2",
  ]);
  let activeAttributes = { "aria-current": "page" };
  const account = () =>
    location.pathname.match(/^\/app\/accounts\/(\d+)(?:\/|$)/)?.[1];
  const native = (node) => !node.closest(`#${menuId}`);
  const setAttribute = (node, name, value) => {
    if (value === null) node.removeAttribute(name);
    else if (node.getAttribute(name) !== value) node.setAttribute(name, value);
  };
  const restore = () => {
    for (const [node, attrs] of suppressed) {
      if (!node.isConnected) continue;
      for (const [name, { before, after }] of Object.entries(attrs)) {
        if (node.getAttribute(name) === after) setAttribute(node, name, before);
      }
    }
    suppressed.clear();
  };
  const temporarily = (node, name, value) => {
    if (node.getAttribute(name) === value) return;
    const attrs = suppressed.get(node) || {};
    const previous = attrs[name];
    attrs[name] = {
      before:
        previous && node.getAttribute(name) === previous.after
          ? previous.before
          : node.getAttribute(name),
      after: value,
    };
    suppressed.set(node, attrs);
    setAttribute(node, name, value);
  };
  const inactiveClass = (node) =>
    [...node.classList].filter((c) => !activeTokens.has(c)).join(" ");
  const suppressNative = () => {
    if (!overlay || !sidebar) return;
    for (const node of sidebar.querySelectorAll(
      'nav [aria-current="page"], nav .active, nav .router-link-exact-active, nav .bg-n-alpha-2',
    )) {
      if (!native(node)) continue;
      temporarily(node, "class", inactiveClass(node));
      if (node.hasAttribute("aria-current"))
        temporarily(node, "aria-current", null);
    }
    for (const node of sidebar.querySelectorAll(
      'nav [role="button"].font-medium, nav [role="button"] .font-medium',
    )) {
      if (!native(node)) continue;
      let classes = inactiveClass(node)
        .split(" ")
        .filter((c) => c !== "font-medium");
      if (node.matches('[role="button"]'))
        classes.push("text-n-slate-11", "hover:bg-n-alpha-2");
      temporarily(node, "class", [...new Set(classes)].join(" "));
    }
  };
  const visibility = (target, visible) =>
    target?.contentWindow?.postMessage(
      { event: "kanban:visibility", visible },
      location.origin,
    );
  const discard = () => {
    parked?.overlay.remove();
    parked = null;
  };
  const close = () => {
    if (overlay && frame) {
      discard();
      overlay.style.display = "none";
      visibility(frame, false);
      parked = { overlay, frame, key: selectedPage, account: currentAccount };
    }
    overlay = frame = selectedPage = null;
    restore();
    renderState();
  };
  const layout = () => {
    if (!sidebar) return;
    const edge = sidebar.getBoundingClientRect().right;
    if (collapsed && flyout && menu) {
      const list = menu.querySelector("ul");
      list.style.left = `${edge + 8}px`;
      list.style.top = `${Math.min(menu.getBoundingClientRect().top, innerHeight - 120)}px`;
    }
    if (!overlay) return;
    overlay.style.left = `${Math.max(0, edge)}px`;
    frame?.contentWindow?.postMessage(
      {
        event: "kanban:theme",
        theme: document.body.classList.contains("dark") ? "dark" : "light",
      },
      location.origin,
    );
  };
  const open = (page, cardId) => {
    close();
    currentAccount = account();
    if (!currentAccount) return;
    selectedPage = page.key;
    flyout = false;
    if (
      !cardId &&
      parked?.key === page.key &&
      parked.account === currentAccount &&
      parked.overlay.isConnected
    ) {
      ({ overlay, frame } = parked);
      parked = null;
      overlay.style.display = "";
      visibility(frame, true);
      renderState();
      suppressNative();
      layout();
      return;
    }
    discard();
    overlay = document.createElement("section");
    overlay.id = "chatwoot-kanban-panel";
    Object.assign(overlay.style, {
      position: "fixed",
      top: "0",
      right: "0",
      bottom: "0",
      zIndex: "40",
      background: "rgb(var(--surface-1))",
    });
    overlay.setAttribute("aria-label", page.label);
    frame = document.createElement("iframe");
    frame.title = `${page.label} da conta`;
    frame.src = `${page.path}?account=${currentAccount}${cardId ? "&card=" + cardId : ""}`;
    Object.assign(frame.style, { width: "100%", height: "100%", border: "0" });
    frame.addEventListener("load", layout);
    overlay.append(frame);
    document.body.append(overlay);
    renderState();
    suppressNative();
    layout();
  };
  const sanitize = (root) => {
    for (const node of [root, ...root.querySelectorAll("*")]) {
      for (const attr of [...node.attributes]) {
        if (
          /^(href|to|id|name|activeon|aria-current|aria-controls|on.*)$/i.test(
            attr.name,
          )
        )
          node.removeAttribute(attr.name);
      }
      for (const cls of [...node.classList])
        if (activeTokens.has(cls)) node.classList.remove(cls);
    }
    return root;
  };
  const icon = (root, name) => {
    const old = root.querySelector(
      '[class*="i-lucide-"], [class*="i-woot-"], svg',
    );
    if (!old) return;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    for (const attr of [...old.attributes]) {
      if (attr.name.startsWith("data-v-") || attr.name === "class")
        svg.setAttribute(attr.name, attr.value);
    }
    for (const cls of [...svg.classList])
      if (/^i-/.test(cls)) svg.classList.remove(cls);
    for (const [key, value] of Object.entries({
      viewBox: "0 0 24 24",
      width: "24",
      height: "24",
      fill: "none",
      stroke: "currentColor",
      "stroke-width": old.getAttribute("stroke-width") || "2",
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
      "aria-hidden": "true",
      focusable: "false",
      "data-pipeline-icon": name,
    }))
      svg.setAttribute(key, value);
    const shapes = {
      "square-kanban": [
        ["rect", { x: 3, y: 3, width: 18, height: 18, rx: 2 }],
        ["path", { d: "M8 7v7M12 7v4M16 7v9" }],
      ],
      "columns-3": [
        ["rect", { x: 3, y: 3, width: 18, height: 18, rx: 2 }],
        ["path", { d: "M9 3v18M15 3v18" }],
      ],
      "chart-column": [
        ["path", { d: "M3 3v16a2 2 0 0 0 2 2h16M9 17V9M14 17V5M19 17v-3" }],
      ],
      "list-checks": [
        ["path", { d: "m3 17 2 2 4-4M3 7l2 2 4-4M13 6h8M13 12h8M13 18h8" }],
      ],
      settings: [
        [
          "path",
          {
            d: "M12.2 2h-.4a2 2 0 0 0-2 2v.2a2 2 0 0 1-1 1.7l-.4.3a2 2 0 0 1-2 0l-.2-.1a2 2 0 0 0-2.7.7l-.2.4a2 2 0 0 0 .7 2.7l.2.1a2 2 0 0 1 1 1.7v.6a2 2 0 0 1-1 1.7l-.2.1a2 2 0 0 0-.7 2.7l.2.4a2 2 0 0 0 2.7.7l.2-.1a2 2 0 0 1 2 0l.4.3a2 2 0 0 1 1 1.7v.2a2 2 0 0 0 2 2h.4a2 2 0 0 0 2-2v-.2a2 2 0 0 1 1-1.7l.4-.3a2 2 0 0 1 2 0l.2.1a2 2 0 0 0 2.7-.7l.2-.4a2 2 0 0 0-.7-2.7l-.2-.1a2 2 0 0 1-1-1.7v-.6a2 2 0 0 1 1-1.7l.2-.1a2 2 0 0 0 .7-2.7l-.2-.4a2 2 0 0 0-2.7-.7l-.2.1a2 2 0 0 1-2 0l-.4-.3a2 2 0 0 1-1-1.7V4a2 2 0 0 0-2-2Z",
          },
        ],
        ["circle", { cx: 12, cy: 12, r: 3 }],
      ],
    };
    for (const [tag, attrs] of shapes[name]) {
      const shape = document.createElementNS(svg.namespaceURI, tag);
      for (const [key, value] of Object.entries(attrs))
        shape.setAttribute(key, value);
      svg.append(shape);
    }
    old.replaceWith(svg);
  };
  const action = (node, label, handler) => {
    node.setAttribute("role", "button");
    node.setAttribute("tabindex", "0");
    node.setAttribute("title", label);
    node.setAttribute("aria-label", label);
    if (node.tagName === "BUTTON") node.type = "button";
    node.addEventListener("click", handler);
    node.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        handler();
      }
    });
  };
  const renderState = () => {
    if (!menu) return;
    const header = menu.querySelector("[data-pipeline-header]");
    const list = menu.querySelector("ul");
    const visible = collapsed ? flyout : expanded;
    const base = header.dataset.baseClass;
    setAttribute(
      header,
      "class",
      selectedPage
        ? base
            .split(" ")
            .filter(
              (c) => c !== "text-n-slate-11" && c !== "hover:bg-n-alpha-2",
            )
            .join(" ") +
            (collapsed
              ? " text-n-slate-12 bg-n-alpha-2"
              : " text-n-slate-12 font-medium")
        : base,
    );
    const label = header.querySelector(".truncate");
    if (label)
      setAttribute(
        label,
        "class",
        label.dataset.baseClass + (selectedPage ? " font-medium text-sm" : ""),
      );
    setAttribute(header, "aria-expanded", String(visible));
    list.style.display = visible ? "grid" : "none";
    const arrow = header.querySelector('[class*="i-lucide-chevron"]');
    if (arrow) {
      arrow.style.display = visible ? "" : "none";
      arrow.style.transform = visible ? "rotate(0deg)" : "rotate(180deg)";
    }
    for (const child of menu.querySelectorAll("[data-pipeline-page]")) {
      const active = child.dataset.pipelinePage === selectedPage;
      setAttribute(
        child,
        "class",
        child.dataset.baseClass +
          (active ? " " + [...activeTokens].join(" ") : ""),
      );
      for (const [key, value] of Object.entries(activeAttributes))
        setAttribute(child, key, active ? value : null);
    }
  };
  const topItem = (list, part) => {
    const link = [...list.querySelectorAll(`a[href*="/${part}"]`)].find(native);
    if (!link) {
      if (!collapsed) return null;
      const cached = anchors.get(part);
      if (cached?.parentElement === list) return cached;
      // Em 4.16.2, grupos recolhidos são botões e não possuem href.
      const glyphs = {
        contacts: "i-lucide-contact",
        reports: "i-lucide-chart-spline",
        settings: "i-lucide-bolt",
      };
      return collapsed
        ? [...list.children].find(
            (node) => native(node) && node.querySelector(`.${glyphs[part]}`),
          ) || null
        : null;
    }
    let node = link;
    while (node.parentElement !== list) node = node.parentElement;
    anchors.set(part, node);
    return node;
  };
  const positionMenu = (list) => {
    const contacts = topItem(list, "contacts");
    const before = contacts
      ? contacts.nextSibling
      : topItem(list, "reports") || topItem(list, "settings");
    if (
      before === menu ||
      (menu.parentElement === list && menu.nextSibling === before)
    )
      return;
    list.insertBefore(menu, before);
  };
  const install = () => {
    const selected = account();
    if (overlay && selected !== currentAccount) close();
    if (parked && parked.account !== selected) discard();
    if (!selected) {
      menu?.remove();
      menu = null;
      return;
    }
    const nav = document.querySelector("aside nav");
    const nextSidebar = nav?.closest("aside");
    if (sidebar !== nextSidebar) {
      sidebar = nextSidebar;
      resizeObserver.disconnect();
      if (sidebar) resizeObserver.observe(sidebar);
    }
    const list = nav?.querySelector(":scope > ul");
    if (!list) return;
    const groups = [...list.children].filter(native);
    const group = groups.find((node) =>
      node.querySelector(":scope > ul > li a[href] .size-4"),
    );
    const isCollapsed = !groups.some((node) =>
      node.querySelector(':scope > [role="button"]'),
    );
    const active = [
      ...list.querySelectorAll('li.child-item > a[aria-current="page"]'),
    ].find(native);
    if (active) {
      const inactive = [
        ...list.querySelectorAll("li.child-item > a:not([aria-current])"),
      ].find((node) => native(node) && !suppressed.has(node));
      if (inactive)
        for (const cls of active.classList)
          if (!inactive.classList.contains(cls)) activeTokens.add(cls);
      activeAttributes = Object.fromEntries(
        [...active.attributes]
          .filter(
            (attr) =>
              attr.name === "aria-current" || attr.name === "data-active",
          )
          .map((attr) => [attr.name, attr.value]),
      );
    }
    if (group && (!overlay || !templates)) {
      const leaf = [...group.querySelectorAll(":scope > ul > li")].find(
        (node) => node.querySelector("a[href] .size-4"),
      );
      const neutral = groups
        .map((node) => node.querySelector(':scope > [role="button"]'))
        .find(
          (node) =>
            node &&
            !node.classList.contains("font-medium") &&
            !node.classList.contains("bg-n-alpha-2"),
        );
      templates = {
        group: group.cloneNode(true),
        leaf: leaf.cloneNode(true),
        neutral: neutral?.cloneNode(true),
      };
    }
    if (menu?.isConnected && collapsed === isCollapsed) {
      positionMenu(list);
      suppressNative();
      return;
    }
    menu?.remove();
    collapsed = isCollapsed;
    flyout = false;
    const compact = groups.find((node) =>
      node.querySelector(":scope > div.relative > button"),
    );
    if ((!collapsed && !templates) || (collapsed && !compact)) return;
    menu = sanitize((collapsed ? compact : templates.group).cloneNode(true));
    menu.id = menuId;
    let header;
    let children;
    if (collapsed) {
      header = menu.querySelector("button");
      menu.replaceChildren(header.parentElement);
      header.replaceChildren(
        header.querySelector('[class*="i-"]').cloneNode(true),
      );
      header.classList.add("text-n-slate-11", "hover:bg-n-alpha-2");
      children = document.createElement("ul");
      children.className =
        "fixed bg-n-alpha-3 backdrop-blur-[100px] outline outline-1 -outline-offset-1 w-56 outline-n-weak rounded-xl shadow-lg py-2 px-2 m-0 list-none";
      children.style.zIndex = "100";
      menu.append(children);
    } else {
      header = menu.querySelector(':scope > [role="button"]');
      children = menu.querySelector(":scope > ul");
      if (templates.neutral) {
        header.className = templates.neutral.className;
        header.querySelector(".truncate").className =
          templates.neutral.querySelector(".truncate").className;
      }
      header.querySelector(".truncate").textContent = "Pipeline";
      const glyph = header.querySelector('[class*="i-"]');
      glyph.parentElement.replaceChildren(glyph);
      const label = header.querySelector(".truncate");
      label.parentElement.replaceChildren(label);
    }
    children.replaceChildren();
    children.id = "bee-pipeline-children";
    header.dataset.pipelineHeader = "";
    header.dataset.baseClass = header.className;
    const headerLabel = header.querySelector(".truncate");
    if (headerLabel) headerLabel.dataset.baseClass = headerLabel.className;
    header.setAttribute("aria-controls", children.id);
    icon(header, "square-kanban");
    action(header, "Pipeline", () => {
      if (collapsed) flyout = !flyout;
      else {
        // Como o SidebarGroup do Chatwoot 4.18: sem página do Pipeline aberta,
        // o clique no grupo já abre o primeiro item; com página aberta, recolhe.
        expanded = selectedPage ? !expanded : true;
        try {
          localStorage.setItem(storageKey, String(expanded));
        } catch {
          /* Estado em memória continua funcional. */
        }
        if (!selectedPage) return open(pages[0]);
      }
      renderState();
      layout();
    });
    for (const page of pages) {
      // Na primeira carga recolhida, o Vue não monta folhas: clonar o botão nativo visível.
      const leaf = templates
        ? sanitize(templates.leaf.cloneNode(true))
        : document.createElement("li");
      let button = leaf.querySelector("a, [role=button]");
      if (!button) {
        button = sanitize(compact.querySelector("button").cloneNode(true));
        leaf.append(button);
      }
      const nativeLabel = button.querySelector(".truncate");
      nativeLabel?.remove();
      const glyph = button.querySelector('[class*="i-"]');
      const wrapper =
        glyph?.parentElement === button ? glyph : glyph?.parentElement;
      button.replaceChildren(...(wrapper ? [wrapper] : []));
      const label = nativeLabel || document.createElement("div");
      label.className = "flex-1 truncate min-w-0 text-sm";
      label.textContent = page.label;
      button.append(label);
      leaf.style.removeProperty("display");
      if (collapsed) {
        leaf.className = "py-0.5";
        button.className =
          "flex items-center gap-2 px-2 py-1.5 w-full rounded-lg text-sm text-left text-n-slate-11 hover:bg-n-alpha-2";
      }
      icon(button, page.icon);
      button.dataset.pipelinePage = page.key;
      button.dataset.baseClass = button.className;
      action(button, page.label, () => open(page));
      children.append(leaf);
    }
    positionMenu(list);
    renderState();
    suppressNative();
    layout();
  };
  window.addEventListener("message", (event) => {
    if (
      event.origin !== location.origin ||
      event.source !== frame?.contentWindow
    )
      return;
    const data = event.data;
    if (
      data?.event === "kanban:open-card" &&
      String(data.account) === account() &&
      Number.isSafeInteger(data.id) &&
      data.id > 0
    ) {
      open({ key: "kanban", label: "Kanban", path: "/kanban" }, data.id);
      return;
    }
    if (
      data?.event === "kanban:open-page" &&
      String(data.account) === account()
    ) {
      const target = pages.find((page) => page.key === data.page);
      if (target) open(target);
      return;
    }
    if (data?.event === "kanban:close") close();
    if (
      data?.event === "kanban:navigate" &&
      String(data.account) === account() &&
      /^(conversations|contacts)$/.test(data.resource) &&
      Number.isSafeInteger(data.id) &&
      data.id > 0
    )
      location.assign(`/app/accounts/${account()}/${data.resource}/${data.id}`);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      flyout = false;
      close();
    }
  });
  document.addEventListener(
    "click",
    (event) => {
      if (menu?.contains(event.target)) return;
      if (flyout) {
        flyout = false;
        renderState();
      }
      if (
        overlay &&
        sidebar?.contains(event.target) &&
        event.target.closest('a[href], [role="button"], button')
      )
        close();
    },
    true,
  );
  window.addEventListener("resize", () => requestAnimationFrame(layout));
  document.addEventListener("transitionend", (event) => {
    if (event.target === sidebar) layout();
  });
  let scheduled = false;
  const run = () => {
    if (!scheduled) return;
    scheduled = false;
    observer.disconnect();
    try {
      install();
      layout();
    } finally {
      observe();
    }
  };
  // Aba oculta não executa requestAnimationFrame: o temporizador garante o menu.
  const observer = new MutationObserver(() => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(run);
    setTimeout(run, 100);
  });
  const observe = () =>
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "aria-current", "href"],
    });
  const resizeObserver = new ResizeObserver(layout);
  install();
  observe();
})();
