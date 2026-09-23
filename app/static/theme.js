(() => {
  if (window.parent === window) return;
  let observer;
  const copied = new Set();
  function copyTheme() {
    try {
      const doc = window.parent.document;
      const root = document.documentElement;
      const values = new Map();
      // O v4.16.2 sobrescreve a paleta em body.dark; versões futuras podem usar html.dark.
      for (const element of [doc.documentElement, doc.body]) {
        if (!element) continue;
        const styles = window.parent.getComputedStyle(element);
        for (const name of styles) {
          if (name.startsWith("--"))
            values.set(name, styles.getPropertyValue(name));
        }
      }
      for (const name of copied)
        if (!values.has(name)) root.style.removeProperty(name);
      copied.clear();
      for (const [name, value] of values) {
        root.style.setProperty(name, value);
        copied.add(name);
      }
      root.style.setProperty(
        "--cw-font-family",
        window.parent.getComputedStyle(doc.body).fontFamily,
      );
      const primary = doc.querySelector(".bg-n-brand.text-white");
      root.style.setProperty(
        "--cw-on-action",
        primary
          ? window.parent.getComputedStyle(primary).color
          : `rgb(${window.parent.getComputedStyle(doc.documentElement).getPropertyValue("--solid-2")})`,
      );
      const dark =
        doc.documentElement.classList.contains("dark") ||
        doc.body.classList.contains("dark");
      root.style.colorScheme = dark ? "dark" : "light";
      document.body.classList.toggle("dark", dark);
      // A família computada não transfere as declarações @font-face para o iframe.
      for (const face of doc.fonts) {
        if (!document.fonts.has(face)) document.fonts.add(face);
      }
    } catch {
      // A integração exige mesma origem. Não ler documentos de outras origens.
    }
  }
  copyTheme();
  try {
    observer = new MutationObserver(copyTheme);
    for (const element of [
      parent.document.documentElement,
      parent.document.body,
    ])
      observer.observe(element, {
        attributes: true,
        attributeFilter: ["class", "style"],
      });
  } catch {
    /* O quadro continua acessível se o pai não estiver disponível. */
  }
  window.addEventListener("pagehide", () => observer?.disconnect(), {
    once: true,
  });
})();
