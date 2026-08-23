import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement } from "lit/decorators.js";

import "@/components/ui/index.js";

import { api } from "@/api/bridge.js";
import { attachStoreController } from "@/state/store-controller.js";
import { reportError, store } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";
import { entityCardStyles, toolbarStyles } from "@/styles/views.js";

import type { TxEntity } from "@/types.js";
import type { TemplateResult } from "lit";

const OFF_STATES = new Set(["off", "unavailable", "closed", "idle", "standby"]);
const UNKNOWN_STATES = new Set(["unknown", "none", "none-pending"]);

@customElement("rune-settings-view")
@localized()
export class RuneSettingsView extends LitElement {
  static styles = [
    sharedStyles,
    toolbarStyles,
    entityCardStyles,
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
      .stat-meta {
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-muted);
        margin-top: 2px;
      }
    `,
  ];

  constructor() {
    super();
    attachStoreController(this);
  }

  connectedCallback(): void {
    super.connectedCallback();
    void this._refresh();
  }

  private async _refresh(): Promise<void> {
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
      reportError(err, msg(str`Load settings`));
    }
  }

  private _renderEntity(e: TxEntity): TemplateResult {
    const off = OFF_STATES.has(e.state);
    const unknown = !off && UNKNOWN_STATES.has(e.state);
    const dotCls = off ? "off" : unknown ? "unknown" : "";
    return html`
      <div class="entity">
        <div style="display:flex;flex-direction:column;gap:2px">
          <span style="font-weight:var(--rune-fw-medium)">${e.name || e.entity_id}</span>
          ${
            e.name && e.name !== e.entity_id
              ? html`<span class="entity-id" style="font-size:11px;color:var(--rune-text-muted)"
                  >${e.entity_id}</span
                >`
              : null
          }
        </div>
        <span class="entity-state">
          <span class="dot ${dotCls}"></span>
          ${e.state}
        </span>
      </div>
    `;
  }

  private _renderEntitySection(
    title: unknown,
    icon: string,
    entities: TxEntity[],
    empty: { heading: unknown; message: unknown },
  ): TemplateResult {
    return html`
      <div class="section-title">
        <i class="ti ti-${icon}"></i>
        ${title}
        <rune-chip variant="neutral">${entities.length}</rune-chip>
      </div>
      ${
        entities.length === 0
          ? html`<rune-empty-state
              icon=${icon}
              heading=${empty.heading}
              message=${empty.message}
            ></rune-empty-state>`
          : html`<div class="entities">${entities.map((e) => this._renderEntity(e))}</div>`
      }
    `;
  }

  render() {
    const signalTotal = store.remotes.reduce((acc, r) => acc + r.signals.length, 0);
    return html`
      <div class="head">
        <h2>${msg(str`Settings`)}</h2>
        <div class="sub">${msg(str`Integration health and discovered entities.`)}</div>
      </div>

      <div class="stats">
        <div class="stat">
          <div class="stat-icon"><i class="ti ti-device-remote"></i></div>
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

      ${this._renderEntitySection(
        msg(str`Available transmitters`),
        "antenna-bars-5",
        store.transmitters,
        {
          heading: msg(str`No IR/RF emitters found`),
          message: msg(
            str`Add a Broadlink / ESPHome / MQTT emitter entity to Home Assistant first.`,
          ),
        },
      )}
      ${this._renderEntitySection(msg(str`Available receivers`), "antenna", store.receivers, {
        heading: msg(str`No IR/RF receivers found`),
        message: msg(
          str`Add a Broadlink / ESPHome RF receiver to enable sniffer + learn workflows.`,
        ),
      })}
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-settings-view": RuneSettingsView;
  }
}
