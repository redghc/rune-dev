import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import "@/components/ui/index.js";

import { api } from "@/api/bridge.js";
import { store, subscribe } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

@customElement("rune-settings-view")
@localized()
export class RuneSettingsView extends LitElement {
  static styles = [
    sharedStyles,
    css`
      .head {
        margin-bottom: var(--rune-space-5);
      }
      .head h2 {
        margin: 0 0 var(--rune-space-1);
        font-size: var(--rune-fs-2xl);
        font-weight: var(--rune-fw-semibold);
        letter-spacing: -0.02em;
        color: var(--rune-text-strong);
      }
      .head .sub {
        color: var(--rune-text-muted);
        font-size: var(--rune-fs-sm);
      }
      .section-title {
        margin: var(--rune-space-6) 0 var(--rune-space-3);
        font-size: var(--rune-fs-md);
        font-weight: var(--rune-fw-semibold);
        color: var(--rune-text-strong);
        letter-spacing: -0.01em;
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
      }
      .section-title i {
        color: var(--rune-primary);
        font-size: 18px;
      }
      .stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: var(--rune-space-3);
      }
      .stat {
        background: var(--rune-surface);
        border-radius: var(--rune-radius-md);
        padding: var(--rune-space-4);
        border: 1px solid var(--rune-border);
        box-shadow: var(--rune-shadow-1);
        display: flex;
        align-items: flex-start;
        gap: var(--rune-space-3);
      }
      .stat-icon {
        width: 36px;
        height: 36px;
        border-radius: var(--rune-radius-sm);
        background: var(--rune-primary-soft);
        color: var(--rune-primary);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
        flex-shrink: 0;
      }
      .stat-icon.success {
        background: var(--rune-success-soft);
        color: var(--rune-success);
      }
      .stat-icon.warning {
        background: var(--rune-warning-soft);
        color: var(--rune-warning);
      }
      .stat-icon.neutral {
        background: var(--rune-surface-alt);
        color: var(--rune-text-muted);
      }
      .stat-body {
        flex: 1;
        min-width: 0;
      }
      .stat-label {
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        font-weight: var(--rune-fw-medium);
        margin-bottom: 2px;
      }
      .stat-value {
        font-size: var(--rune-fs-xl);
        font-weight: var(--rune-fw-semibold);
        color: var(--rune-text-strong);
        letter-spacing: -0.01em;
      }
      .stat-value.small {
        font-size: var(--rune-fs-md);
        font-family: var(--rune-font-mono);
      }
      .stat-meta {
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-muted);
        margin-top: 2px;
      }
      .entities {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: var(--rune-space-2);
      }
      .entity {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--rune-space-3) var(--rune-space-4);
        background: var(--rune-surface);
        border: 1px solid var(--rune-border);
        border-radius: var(--rune-radius-sm);
        font-family: var(--rune-font-mono);
        font-size: var(--rune-fs-xs);
      }
      .entity-id {
        color: var(--rune-text-strong);
        font-weight: var(--rune-fw-medium);
      }
      .entity-state {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        color: var(--rune-text-muted);
      }
      .dot {
        width: 8px;
        height: 8px;
        border-radius: var(--rune-radius-full);
        background: var(--rune-success);
        box-shadow: 0 0 0 3px var(--rune-success-soft);
      }
      .dot.off {
        background: var(--rune-text-subtle);
        box-shadow: 0 0 0 3px var(--rune-surface-alt);
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
      store.pushToast(msg(str`Load settings: ${(err as Error).message}`), "err");
    }
  }

  render() {
    void this._tick;
    const signalTotal = store.remotes.reduce((acc, r) => acc + r.signals.length, 0);
    return html`
      <div class="head">
        <h2>${msg(str`Settings`)}</h2>
        <div class="sub">${msg(str`Integration health and discovered entities.`)}</div>
      </div>

      <div class="stats">
        <div class="stat">
          <div class="stat-icon"><i class="ti ti-remote"></i></div>
          <div class="stat-body">
            <div class="stat-label">${msg(str`Integration`)}</div>
            <div class="stat-value">${msg(str`RUNE`)}</div>
            <div class="stat-meta">v${store.version}</div>
          </div>
        </div>
        <div class="stat">
          <div class="stat-icon neutral"><i class="ti ti-devices"></i></div>
          <div class="stat-body">
            <div class="stat-label">${msg(str`Devices`)}</div>
            <div class="stat-value">${store.devices.length}</div>
          </div>
        </div>
        <div class="stat">
          <div class="stat-icon warning"><i class="ti ti-antenna"></i></div>
          <div class="stat-body">
            <div class="stat-label">${msg(str`Sniffer signals`)}</div>
            <div class="stat-value">${signalTotal}</div>
          </div>
        </div>
        <div class="stat">
          <div class="stat-icon success"><i class="ti ti-wand"></i></div>
          <div class="stat-body">
            <div class="stat-label">${msg(str`Action bindings`)}</div>
            <div class="stat-value">${store.actions.length}</div>
          </div>
        </div>
      </div>

      <div class="section-title">
        <i class="ti ti-antenna-bars-5"></i>
        ${msg(str`Available transmitters`)}
        <rune-chip variant="neutral">${store.transmitters.length}</rune-chip>
      </div>
      ${
        store.transmitters.length === 0
          ? html`<rune-empty-state
              icon="antenna-bars-5"
              heading=${msg(str`No IR/RF emitters found`)}
              message=${msg(str`Add a Broadlink / ESPHome / MQTT emitter entity to Home Assistant first.`)}
            ></rune-empty-state>`
          : html`
              <div class="entities">
                ${store.transmitters.map(
                  (t) => html`
                    <div class="entity">
                      <span class="entity-id">${t.entity_id}</span>
                      <span class="entity-state">
                        <span
                          class="dot ${t.state === "off" || t.state === "unavailable" ? "off" : ""}"
                        ></span>
                        ${t.state}
                      </span>
                    </div>
                  `,
                )}
              </div>
            `
      }

      <div class="section-title">
        <i class="ti ti-antenna"></i>
        ${msg(str`Available receivers`)}
        <rune-chip variant="neutral">${store.receivers.length}</rune-chip>
      </div>
      ${
        store.receivers.length === 0
          ? html`<rune-empty-state
              icon="antenna"
              heading=${msg(str`No IR/RF receivers found`)}
              message=${msg(str`Add a Broadlink / ESPHome RF receiver to enable sniffer + learn workflows.`)}
            ></rune-empty-state>`
          : html`
              <div class="entities">
                ${store.receivers.map(
                  (r) => html`
                    <div class="entity">
                      <span class="entity-id">${r.entity_id}</span>
                      <span class="entity-state">
                        <span
                          class="dot ${r.state === "off" || r.state === "unavailable" ? "off" : ""}"
                        ></span>
                        ${r.state}
                      </span>
                    </div>
                  `,
                )}
              </div>
            `
      }
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-settings-view": RuneSettingsView;
  }
}
