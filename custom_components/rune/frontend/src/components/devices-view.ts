import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import "@/components/ui/index.js";

import { api } from "@/api/bridge.js";
import { attachStoreController } from "@/state/store-controller.js";
import { store } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";
import { toolbarStyles } from "@/styles/views.js";

import "./device-card.js";

@customElement("rune-devices-view")
@localized()
export class RuneDevicesView extends LitElement {
  static styles = [
    sharedStyles,
    toolbarStyles,
    css`
      .toolbar h2 {
        margin: 0;
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
      .skeletons {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: var(--rune-space-3);
      }
    `,
  ];

  constructor() {
    super();
    attachStoreController(this);
  }

  @state() private _loading = false;

  connectedCallback(): void {
    super.connectedCallback();
    void this._refresh();
  }

  private async _refresh(): Promise<void> {
    this._loading = true;
    try {
      const { devices } = await api.list();
      store.setDevices(devices ?? []);
    } catch (err) {
      store.pushToast(msg(str`Load devices: ${(err as Error).message}`), "err");
    } finally {
      this._loading = false;
    }
  }

  private _add(): void {
    store.openDeviceDialog(null);
  }

  render() {
    const devices = store.devices;
    return html`
      <div class="toolbar" role="toolbar" aria-label="Devices toolbar">
        <h2>${msg(str`Devices`)}</h2>
        <span class="grow"></span>
        <rune-tooltip content="Reload from backend">
          <rune-button
            variant="secondary"
            icon="refresh"
            ?loading=${this._loading}
            @click=${this._refresh}
          >
            ${msg(str`Refresh`)}
          </rune-button>
        </rune-tooltip>
        <rune-button variant="primary" icon="plus" @click=${this._add}
          >${msg(str` Add device `)}</rune-button
        >
      </div>
      <div class="subtitle">
        ${msg(
          html`IR / RF devices RUNE controls in Home Assistant. Click
            <strong>+ Add device</strong> to create one, or use the config flow.`,
        )}
      </div>
      ${
        this._loading && devices.length === 0
          ? html`
              <div class="skeletons" aria-busy="true" aria-live="polite">
                ${[0, 1, 2].map(
                  () => html`<rune-skeleton variant="rect" height="120px"></rune-skeleton>`,
                )}
              </div>
            `
          : null
      }
      ${
        devices.length === 0
          ? html`
              <rune-empty-state
                icon="devices"
                heading=${msg(str`No devices yet`)}
                message=${msg(
                  str`Create your first IR / RF device — pick a category, name it, and choose the emitter entity.`,
                )}
              >
                <rune-button slot="action" variant="primary" icon="plus" @click=${this._add}>
                  ${msg(str`Add device`)}
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
