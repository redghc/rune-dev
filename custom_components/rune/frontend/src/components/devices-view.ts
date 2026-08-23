import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import "@/components/ui/index.js";

import { api } from "@/api/bridge.js";
import { store, subscribe } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

import "./device-card.js";

@customElement("rune-devices-view")
export class RuneDevicesView extends LitElement {
  static styles = [
    sharedStyles,
    css`
      .toolbar {
        display: flex;
        gap: var(--rune-space-3);
        align-items: center;
        margin-bottom: var(--rune-space-5);
      }
      .toolbar h2 {
        margin: 0;
        font-size: var(--rune-fs-2xl);
        font-weight: var(--rune-fw-semibold);
        letter-spacing: -0.02em;
        color: var(--rune-text-strong);
      }
      .toolbar .grow {
        flex: 1;
      }
      .subtitle {
        margin: -12px 0 var(--rune-space-4);
        color: var(--rune-text-muted);
        font-size: var(--rune-fs-sm);
      }
      .stack {
        display: flex;
        flex-direction: column;
        gap: var(--rune-space-3);
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
      <div class="toolbar" role="toolbar" aria-label="Devices toolbar">
        <h2>Devices</h2>
        <span class="grow"></span>
        <rune-tooltip content="Reload from backend">
          <rune-button
            variant="secondary"
            icon="refresh"
            ?loading=${this._loading}
            @click=${this.refresh}
          >
            Refresh
          </rune-button>
        </rune-tooltip>
        <rune-button variant="primary" icon="plus" @click=${this._add}> Add device </rune-button>
      </div>
      <div class="subtitle">
        IR / RF devices RUNE controls in Home Assistant. Click
        <strong>+ Add device</strong> to create one, or use the config flow.
      </div>
      ${
        this._loading && devices.length === 0
          ? html`
              <div
                style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:var(--rune-space-3)"
                aria-busy="true"
                aria-live="polite"
              >
                <rune-skeleton variant="rect" height="120px"></rune-skeleton>
                <rune-skeleton variant="rect" height="120px"></rune-skeleton>
                <rune-skeleton variant="rect" height="120px"></rune-skeleton>
              </div>
            `
          : null
      }
      ${
        devices.length === 0
          ? html`
              <rune-empty-state
                icon="devices"
                heading="No devices yet"
                message="Create your first IR / RF device — pick a category, name it, and choose the emitter entity."
              >
                <rune-button slot="action" variant="primary" icon="plus" @click=${this._add}>
                  Add device
                </rune-button>
              </rune-empty-state>
            `
          : html`
              <div class="stack">
                ${devices.map((d) => html`<rune-device-card .device=${d}></rune-device-card>`)}
              </div>
            `
      }
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-devices-view": RuneDevicesView;
  }
}
