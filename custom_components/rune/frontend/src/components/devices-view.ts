import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import { api } from "../api/bridge.js";
import { store, subscribe } from "../state/store.js";
import { sharedStyles } from "../styles/shared.js";

import "./device-card.js";

@customElement("rune-devices-view")
export class RuneDevicesView extends LitElement {
  static styles = [
    sharedStyles,
    css`
      .toolbar {
        display: flex;
        gap: 8px;
        align-items: center;
        margin-bottom: 16px;
      }
      .toolbar h2 {
        margin: 0;
        font-weight: 400;
      }
      .grow {
        flex: 1;
      }
    `,
  ];

  @state() private _tick = 0;
  @state() private _loading = false;
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
    this._loading = true;
    try {
      const { devices } = await api.list();
      store.setDevices(devices ?? []);
    } catch (err) {
      store.pushToast(`Load devices: ${(err as Error).message}`, "err");
    } finally {
      this._loading = false;
    }
  }

  private _add(): void {
    store.openDeviceDialog(null);
  }

  render() {
    void this._tick;
    const devices = store.devices;
    return html`
      <div class="toolbar">
        <h2>Devices</h2>
        <span class="grow"></span>
        <button @click=${this._add}>+ Add device</button>
        <button class="secondary" @click=${this.refresh} ?disabled=${this._loading}>
          ${this._loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      ${
        devices.length === 0
          ? html`<div class="empty">
              <div>No devices yet.</div>
              <div style="margin-top:8px;font-size:12px;">
                Click + Add device to create one, or use the config flow.
              </div>
            </div>`
          : html`${devices.map((d) => html`<rune-device-card .device=${d}></rune-device-card>`)}`
      }
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-devices-view": RuneDevicesView;
  }
}
