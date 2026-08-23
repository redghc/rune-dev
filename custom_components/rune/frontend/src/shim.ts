// RUNE sidebar panel — HA custom-element shim.
//
// HA's panel_custom loader expects a JS module URL that registers a
// custom element whose name matches the ``webcomponent_name`` passed
// to ``async_register_panel``. This shim defines ``<rune-panel>``,
// embeds the Lit SPA as an iframe, and bridges iframe <-> parent via
// postMessage so the SPA can call HA's WebSocket API and callService
// without juggling auth tokens itself.
//
// Bridge protocol (window.postMessage, same-origin):
//
//   iframe -> parent:  { type: "rune-bridge", id: <int>, kind: "ws"|"service",
//                        message|domain|service|service_data }
//   parent -> iframe:  { type: "rune-bridge-result", id: <int>,
//                        result: <json> | error: <string> }
//
// No source/origin checks: the iframe is same-origin, and the parent
// trusts every message on the listener. (Same-origin postMessage is
// reliable across reloads — only the ``event.source`` reference
// becomes stale, which we don't use.)

interface RunePanelConfig {
  entry_id?: string;
  version?: string;
}

interface BridgeRequest {
  type: "rune-bridge";
  id: number;
  kind: "ws" | "service";
  message?: Record<string, unknown>;
  domain?: string;
  service?: string;
  service_data?: Record<string, unknown>;
}

interface HassLike {
  callWS: (msg: Record<string, unknown>) => Promise<unknown>;
  callService: (
    domain: string,
    service: string,
    data?: Record<string, unknown>,
  ) => Promise<unknown>;
}

class RunePanel extends HTMLElement {
  private _hass: HassLike | null = null;
  private _iframe: HTMLIFrameElement | null = null;
  private _listeners: Array<(event: MessageEvent) => void> = [];
  private _version: string | null = null;
  private _entryId: string | null = null;

  set hass(hass: HassLike) {
    this._hass = hass;
  }

  setConfig(config: RunePanelConfig) {
    // HA supplies the panel config (``entry_id``, ``version``); stash
    // them so the iframe can pull them via postMessage once it loads.
    this._version = config.version ?? null;
    this._entryId = config.entry_id ?? null;
  }

  connectedCallback(): void {
    if (this._iframe) return;
    const root = this.attachShadow({ mode: "open" });

    // ``:host { display: block }`` so the panel stretches to fill the
    // slot HA gives us. Without it the host collapses to ``inline``
    // and the iframe's ``height: 100%`` has nothing to fill against.
    const style = document.createElement("style");
    style.textContent = `:host{display:block;width:100%;height:100%;}:host>iframe{display:block;width:100%;height:100%;min-height:100vh;border:0;}`;
    root.appendChild(style);

    const errorEl = document.createElement("div");
    errorEl.style.cssText =
      "padding:16px;font:14px/1.4 system-ui;color:#b71c1c;background:#ffebee;display:none;white-space:pre-wrap;";
    errorEl.id = "rune-panel-error";
    root.appendChild(errorEl);

    const iframe = document.createElement("iframe");
    // Cache-bust the inner iframe so HA never serves a stale
    // ``panel.html`` after a bump to ``__version__``.
    iframe.src = this._version
      ? `/rune/panel.html?v=${encodeURIComponent(this._version)}`
      : "/rune/panel.html";
    iframe.style.cssText = "width:100%;height:100%;min-height:100vh;border:0;display:block;";
    iframe.title = "RUNE";
    iframe.addEventListener("error", () => {
      errorEl.textContent = `RUNE: failed to load ${iframe.src}`;
      errorEl.style.display = "block";
      console.error("[rune] iframe failed to load", iframe.src);
    });
    iframe.addEventListener("load", () => {
      // Push the integration version + entry_id into the iframe so the
      // Lit SPA can render accurate version pills, route calls back to
      // this entry, etc. The panel listens for ``rune-init`` and
      // hydrates its store from there.
      iframe.contentWindow?.postMessage(
        { type: "rune-init", version: this._version ?? null, entry_id: this._entryId ?? null },
        "*",
      );
    });
    root.appendChild(iframe);
    this._iframe = iframe;

    const onMsg = (event: MessageEvent): void => {
      const data = (event.data ?? {}) as Partial<BridgeRequest>;
      if (typeof data !== "object" || data === null) return;
      if (data.type !== "rune-bridge") return;
      if (typeof data.id !== "number") return;

      const id = data.id;
      const reply = (payload: Record<string, unknown>): void => {
        const win = iframe.contentWindow;
        if (win) {
          win.postMessage({ type: "rune-bridge-result", id, ...payload }, "*");
        }
      };

      if (!this._hass) {
        reply({ error: "hass not yet set" });
        return;
      }

      if (data.kind === "ws" && data.message) {
        console.debug(`[rune-shim] ws -> ${JSON.stringify(data.message)}`);
        this._hass
          .callWS(data.message)
          .then((result) => {
            console.debug(`[rune-shim] ws <- ok ${JSON.stringify(data.message)}`);
            reply({ result: result === undefined ? null : result });
          })
          .catch((err) => {
            const raw = String((err as Error)?.message ?? err);
            console.warn(
              `[rune-shim] ws <- err ${JSON.stringify(data.message)} code=${(err as { code?: string })?.code ?? "?"} msg=${raw}`,
            );
            // HA returns ``"Unknown command"`` (or
            // ``"Unknown command: rune/..."`` on newer builds) when the
            // ``rune/*`` WebSocket handlers aren't registered yet —
            // usually because HA wasn't restarted after the
            // integration was installed or updated.
            const hint = /unknown command/i.test(raw)
              ? `${raw} — reload the RUNE integration (Developer Tools → YAML → Reload) or restart Home Assistant.`
              : raw;
            reply({ error: hint });
          });
      } else if (
        data.kind === "service" &&
        typeof data.domain === "string" &&
        typeof data.service === "string"
      ) {
        this._hass
          .callService(data.domain, data.service, data.service_data ?? {})
          .then(() => reply({ result: true }))
          .catch((err) => reply({ error: String((err as Error)?.message ?? err) }));
      } else {
        reply({ error: `unknown bridge kind: ${data.kind}` });
      }
    };

    window.addEventListener("message", onMsg);
    this._listeners.push(onMsg);
  }

  disconnectedCallback(): void {
    for (const fn of this._listeners) window.removeEventListener("message", fn);
    this._listeners = [];
  }
}

try {
  customElements.define("rune-panel", RunePanel);
} catch (err) {
  console.error("[rune] failed to register <rune-panel>:", err);
}
