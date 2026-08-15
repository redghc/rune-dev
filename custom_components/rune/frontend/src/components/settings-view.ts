import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import { api } from "@/api/bridge.js";
import { store, subscribe } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

@customElement("rune-settings-view")
export class RuneSettingsView extends LitElement {
  static styles = [
    sharedStyles,
    css`
      h2 {
        margin: 0 0 16px;
        font-weight: 400;
      }
      h3 {
        margin-top: 24px;
      }
      .status-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;
      }
      .stat-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 16px;
      }
      .stat-card .label {
        font-size: 12px;
        color: var(--muted);
        margin-bottom: 6px;
      }
      .stat-card .value {
        font-size: 24px;
        font-weight: 500;
      }
      .status-dot {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 6px;
        background: var(--muted);
      }
      .status-dot.ok {
        background: var(--ok);
      }
      .meta {
        color: var(--muted);
        font-size: 12px;
        margin-top: 6px;
      }
    `,
  ];

  @state() private _tick = 0;
  private _unsub: (() => void) | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    this._unsub = subscribe(() => this._tick++);
    void this.refresh();
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsub?.();
  }

  private async refresh(): Promise<void> {
    try {
      const [{ transmitters }, { receivers }, { devices }] = await Promise.all([
        api.transmitters(),
        api.receivers(),
        api.list(),
      ]);
      store.setTransmitters(transmitters ?? []);
      store.setReceivers(receivers ?? []);
      store.setDevices(devices ?? []);
    } catch (err) {
      store.pushToast(`Load settings: ${(err as Error).message}`, "err");
    }
  }

  render() {
    void this._tick;
    const signalTotal = store.remotes.reduce((acc, r) => acc + r.signals.length, 0);
    return html`
      <h2>Settings</h2>
      <div class="status-grid">
        <div class="stat-card">
          <div class="label">Integration</div>
          <div class="value" style="font-size:18px;">RUNE</div>
          <div class="meta">v${store.version}</div>
        </div>
        <div class="stat-card">
          <div class="label">Devices</div>
          <div class="value">${store.devices.length}</div>
        </div>
        <div class="stat-card">
          <div class="label">Sniffer signals</div>
          <div class="value">${signalTotal}</div>
        </div>
        <div class="stat-card">
          <div class="label">Action bindings</div>
          <div class="value">${store.actions.length}</div>
        </div>
      </div>
      <h3>Available transmitters</h3>
      <div class="status-grid">
        ${
          store.transmitters.length === 0
            ? html`<div class="empty">No IR/RF emitters found.</div>`
            : store.transmitters.map(
                (t) => html`
                  <div class="stat-card">
                    <div class="label">${t.entity_id}</div>
                    <div class="value" style="font-size:14px;">
                      <span class="status-dot ok"></span>${t.state}
                    </div>
                  </div>
                `,
              )
        }
      </div>
      <h3>Available receivers</h3>
      <div class="status-grid">
        ${
          store.receivers.length === 0
            ? html`<div class="empty">No IR/RF receivers found.</div>`
            : store.receivers.map(
                (r) => html`
                  <div class="stat-card">
                    <div class="label">${r.entity_id}</div>
                    <div class="value" style="font-size:14px;">
                      <span class="status-dot ok"></span>${r.state}
                    </div>
                  </div>
                `,
              )
        }
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-settings-view": RuneSettingsView;
  }
}
