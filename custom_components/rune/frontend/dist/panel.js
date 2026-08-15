// RUNE sidebar panel — minimal JS shim.
//
// HA's panel framework requires a JS module that registers a custom
// element matching ``webcomponent_name``. This shim defines
// ``<rune-panel>`` which embeds the actual SPA as an iframe and
// bridges iframe <-> parent via postMessage so the SPA can call HA's
// WebSocket API without managing auth tokens itself.
//
// The actual UI lives in ``panel.html`` (vanilla JS, no build).
//
// Bridge protocol (window.postMessage, same-origin):
//
//   iframe -> parent:  { type: "rune-bridge", id: <uuid>, kind: "ws"|"service",
//                        message|domain|service|service_data }
//   parent -> iframe:  { type: "rune-bridge-result", id: <uuid>,
//                        result: <json> | error: <string> }
//
// No source/origin checks: the iframe is same-origin, and the parent
// trusts every message that lands on the listener. (Same-origin
// postMessage is reliable across reloads — only the ``event.source``
// reference becomes stale, which we don't use.)
(function () {
  class RunePanel extends HTMLElement {
    constructor() {
      super();
      this._config = null;
      this._hass = null;
      this._iframe = null;
      this._listeners = [];
    }

    set hass(hass) {
      this._hass = hass;
    }

    setConfig(config) {
      this._config = config || {};
    }

    set panelVersion(version) {
      this._version = version || "0";
    }

    connectedCallback() {
      if (this._iframe) return;
      const root = this.attachShadow({ mode: "open" });

      // ---- error surface (visible if the SPA fails) ----
      const errorEl = document.createElement("div");
      errorEl.style.cssText =
        "padding:16px;font:14px/1.4 system-ui;color:#b71c1c;background:#ffebee;display:none;white-space:pre-wrap;";
      errorEl.id = "rune-panel-error";
      root.appendChild(errorEl);

      // ---- iframe ----
      const iframe = document.createElement("iframe");
      iframe.src = "/rune/panel.html";
      iframe.style.cssText = "width:100%;height:100%;border:0;display:block;";
      iframe.title = "RUNE";
      iframe.addEventListener("error", () => {
        errorEl.textContent = "RUNE: failed to load " + iframe.src;
        errorEl.style.display = "block";
        console.error("[rune] iframe failed to load", iframe.src);
      });
      root.appendChild(iframe);
      this._iframe = iframe;

      // ---- postMessage bridge ----
      // The listener is added to ``window`` so the iframe can reach
      // the parent regardless of how HA wraps the custom element.
      const onMsg = (event) => {
        const data = event.data || {};
        if (typeof data !== "object") return;
        if (data.type !== "rune-bridge") return;

        const id = data.id;
        // Always reply through the LIVE contentWindow so the
        // Promise on the iframe side resolves even if the iframe
        // was reloaded mid-request.
        const reply = (payload) => {
          const win = iframe.contentWindow;
          if (win) {
            win.postMessage(
              { type: "rune-bridge-result", id, ...payload },
              "*"
            );
          }
        };

        if (!this._hass) {
          reply({ error: "hass not yet set" });
          return;
        }

        if (data.kind === "ws") {
          this._hass
            .callWS(data.message)
            .then((result) => reply({ result: result === undefined ? null : result }))
            .catch((err) =>
              reply({ error: String((err && err.message) || err) })
            );
        } else if (data.kind === "service") {
          this._hass
            .callService(data.domain, data.service, data.service_data || {})
            .then(() => reply({ result: true }))
            .catch((err) =>
              reply({ error: String((err && err.message) || err) })
            );
        } else {
          reply({ error: "unknown bridge kind: " + data.kind });
        }
      };
      window.addEventListener("message", onMsg);
      this._listeners.push(onMsg);
    }

    disconnectedCallback() {
      for (const fn of this._listeners) window.removeEventListener("message", fn);
      this._listeners = [];
    }
  }

  try {
    customElements.define("rune-panel", RunePanel);
  } catch (err) {
    console.error("[rune] failed to register <rune-panel>:", err);
  }
})();
