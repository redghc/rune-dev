// RUNE sidebar panel — minimal JS shim.
//
// HA's panel framework requires a JS module that registers a custom
// element matching ``webcomponent_name``. This shim defines
// ``<rune-panel>`` which embeds the actual SPA as an iframe and bridges
// iframe <-> parent via postMessage so the SPA can call HA's WebSocket
// API without managing auth tokens itself.
//
// The actual UI lives in ``rune-panel.html`` (vanilla JS, no build).
class RunePanel extends HTMLElement {
  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._mounted = false;
  }

  set hass(hass) {
    this._hass = hass;
    // If we're already mounted, re-send the iframe the new hass.
    if (this._iframe) this._iframe.contentWindow.postMessage({ type: "hass-ready" }, "*");
  }

  setConfig(config) {
    this._config = config || {};
  }

  connectedCallback() {
    if (this._mounted) return;
    this._mounted = true;

    const root = this.attachShadow({ mode: "open" });
    const wrap = document.createElement("div");
    wrap.style.cssText = "width:100%;height:100%;display:flex;flex-direction:column;";
    root.appendChild(wrap);

    // ---- error surface ----
    // The iframe is sandboxed; if the SPA fails to load we won't see
    // anything. We log to the parent console (which HA's panel
    // framework surfaces as a yellow banner in the frontend) so the
    // operator can see what's broken.
    const errorEl = document.createElement("div");
    errorEl.style.cssText = "padding:16px;font:14px/1.4 system-ui;color:#b71c1c;background:#ffebee;display:none;";
    errorEl.id = "rune-panel-error";
    wrap.appendChild(errorEl);

    const iframe = document.createElement("iframe");
    iframe.src = "/rune/panel.html";
    iframe.style.cssText = "width:100%;height:100%;border:0;display:block;flex:1;";
    iframe.title = "RUNE";
    iframe.addEventListener("error", () => {
      errorEl.textContent = "RUNE: failed to load " + iframe.src;
      errorEl.style.display = "block";
      console.error("[rune] iframe failed to load", iframe.src);
    });
    wrap.appendChild(iframe);
    this._iframe = iframe;

    // ---- postMessage bridge ----
    // The SPA inside the iframe sends requests with an id; we route
    // them to the parent's ``hass.callWS`` / ``hass.callService`` and
    // post the result back.
    const onMsg = (event) => {
      if (event.source !== iframe.contentWindow) return;
      const data = event.data || {};
      if (data.type !== "rune-bridge") return;
      const reply = (payload) =>
        iframe.contentWindow.postMessage(
          { type: "rune-bridge-result", id: data.id, ...payload },
          "*",
        );
      if (data.kind === "ws") {
        if (!this._hass) return reply({ error: "no hass" });
        this._hass
          .callWS(data.message)
          .then((result) => reply({ result }))
          .catch((err) =>
            reply({ error: String((err && err.message) || err) })
          );
      } else if (data.kind === "service") {
        if (!this._hass) return reply({ error: "no hass" });
        this._hass
          .callService(data.domain, data.service, data.service_data || {})
          .then(() => reply({ result: true }))
          .catch((err) =>
            reply({ error: String((err && err.message) || err) })
          );
      } else if (data.kind === "config") {
        reply({ result: this._config });
      } else {
        reply({ error: "unknown bridge kind: " + data.kind });
      }
    };
    window.addEventListener("message", onMsg);
    this._onMsg = onMsg;
  }

  disconnectedCallback() {
    if (this._onMsg) {
      window.removeEventListener("message", this._onMsg);
      this._onMsg = null;
    }
    this._mounted = false;
  }
}

// Surface registration errors to the parent console so HA's banner
// picks them up instead of failing silently.
try {
  customElements.define("rune-panel", RunePanel);
} catch (err) {
  console.error("[rune] failed to register <rune-panel>:", err);
}
