import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import "@/components/ui/index.js";

import { api, refreshDevices } from "@/api/bridge.js";
import { attachStoreController } from "@/state/store-controller.js";
import { reportError, store } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

import type { DeviceCategory, DeviceSummary, PulseCommand } from "@/types.js";

const CATEGORY_ICON: Record<DeviceCategory, string> = {
  fan: "wind",
  climate: "temperature",
  light: "bulb",
  cover: "blind",
  media_player: "device-tv",
  switch: "plug",
  remote: "device-remote",
};

const FLASH_MS = 380;

@customElement("rune-device-card")
@localized()
export class RuneDeviceCard extends LitElement {
  static styles = [
    sharedStyles,
    css`
      .card {
        background: var(--rune-surface);
        border-radius: var(--rune-radius-md);
        padding: var(--rune-space-5);
        border: 1px solid var(--rune-border);
        box-shadow: var(--rune-shadow-1);
        transition:
          box-shadow var(--rune-dur) var(--rune-ease),
          transform var(--rune-dur) var(--rune-ease);
      }
      .card:hover {
        box-shadow: var(--rune-shadow-2);
      }
      .head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: var(--rune-space-4);
        gap: var(--rune-space-3);
      }
      .head-left {
        display: flex;
        gap: var(--rune-space-3);
        align-items: flex-start;
        flex: 1;
        min-width: 0;
      }
      .icon-circle {
        width: 44px;
        height: 44px;
        border-radius: var(--rune-radius-md);
        background: var(--rune-primary-soft);
        color: var(--rune-primary);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        line-height: 1;
        flex-shrink: 0;
      }
      .title-block {
        flex: 1;
        min-width: 0;
      }
      .title-block h3 {
        margin: 0 0 4px;
        font-size: var(--rune-fs-lg);
        font-weight: var(--rune-fw-semibold);
        color: var(--rune-text-strong);
        letter-spacing: -0.01em;
      }
      .meta {
        display: flex;
        flex-wrap: wrap;
        gap: var(--rune-space-2);
        align-items: center;
        color: var(--rune-text-muted);
        font-size: var(--rune-fs-xs);
      }
      .meta i {
        font-size: 13px;
        line-height: 1;
      }
      .meta-item {
        display: inline-flex;
        align-items: center;
        gap: 4px;
      }
      .actions {
        display: flex;
        gap: var(--rune-space-1);
        flex-shrink: 0;
      }
      .commands {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: var(--rune-space-2);
      }
      .cmd {
        position: relative;
        background: var(--rune-surface-alt);
        border: 1px solid var(--rune-border);
        border-radius: var(--rune-radius-sm);
        padding: var(--rune-space-3) var(--rune-space-2);
        cursor: pointer;
        font: inherit;
        color: var(--rune-text);
        font-size: var(--rune-fs-sm);
        font-weight: var(--rune-fw-medium);
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        transition:
          background-color var(--rune-dur-fast) var(--rune-ease),
          border-color var(--rune-dur-fast) var(--rune-ease),
          transform var(--rune-dur-fast) var(--rune-ease);
      }
      .cmd i {
        font-size: 16px;
        color: var(--rune-text-subtle);
        transition: color var(--rune-dur-fast) var(--rune-ease);
      }
      .cmd:hover {
        background: var(--rune-primary);
        border-color: var(--rune-primary);
        color: var(--rune-on-primary);
        transform: translateY(-1px);
      }
      .cmd:hover i {
        color: var(--rune-on-primary);
      }
      .cmd:active {
        transform: translateY(0);
      }
      .cmd.flash {
        background: var(--rune-success) !important;
        border-color: var(--rune-success) !important;
        color: white !important;
      }
      .cmd.flash i {
        color: white !important;
      }
      .cmd.placeholder {
        border-style: dashed;
        color: var(--rune-text-muted);
        background: transparent;
      }
      .cmd.placeholder:hover {
        background: var(--rune-primary-soft);
        border-style: solid;
        border-color: var(--rune-primary);
        color: var(--rune-primary-text);
      }
      .cmd.placeholder:hover i {
        color: var(--rune-primary);
      }
    `,
  ];

  constructor() {
    super();
    attachStoreController(this);
  }

  @property({ attribute: false }) device!: DeviceSummary;

  @state() private _confirmingDelete = false;

  private _onEdit(): void {
    store.openDeviceDialog(this.device);
  }

  private async _confirmDelete(): Promise<void> {
    this._confirmingDelete = false;
    try {
      await api.deleteDevice(this.device.id);
      store.pushToast(msg(str`Deleted`), "ok");
      await refreshDevices();
    } catch (err) {
      reportError(err);
    }
  }

  private async _send(cmd: PulseCommand, btn: HTMLButtonElement): Promise<void> {
    try {
      await api.sendCommand(this.device.id, cmd.key);
      btn.classList.add("flash");
      setTimeout(() => btn.classList.remove("flash"), FLASH_MS);
      store.pushToast(msg(str`Sent ${cmd.label ?? cmd.key}`), "ok");
    } catch (err) {
      reportError(err);
    }
  }

  /** Kick off the learn flow. Uses ``window.prompt`` for now — a
   *  custom dialog with live validation is a v0.4 follow-up. */
  private _learn(): void {
    const key = window.prompt(
      msg(
        str`Learn which command on "${this.device.name}"?\n\nEnter a command key (e.g. "off", "speed_2", "power_on"):`,
      ),
      "off",
    );
    if (!key) return;
    store.openLearnDialog(this.device.id, key.trim());
  }

  render() {
    const d = this.device;
    const tx = (d.transmitter_entity_ids ?? []).join(", ") || "—";
    const rx = (d.receiver_entity_ids ?? []).join(", ");
    const icon = CATEGORY_ICON[d.category] ?? "remote";
    return html`
      <div class="card">
        <div class="head">
          <div class="head-left">
            <div class="icon-circle"><i class="ti ti-${icon}"></i></div>
            <div class="title-block">
              <h3>${d.name}</h3>
              <div class="meta">
                <rune-chip variant="primary" icon=${icon}>${d.category}</rune-chip>
                <span class="meta-item">
                  <i class="ti ti-bolt"></i
                  >${msg(str`${d.command_count} ${d.command_count === 1 ? msg(str`command`) : msg(str`commands`)}`)}
                </span>
                <span class="meta-item" title="Transmitters">
                  <i class="ti ti-antenna-bars-5"></i>${tx}
                </span>
                ${
                  rx
                    ? html`<span class="meta-item" title="Receivers">
                        <i class="ti ti-antenna"></i>${rx}
                      </span>`
                    : null
                }
                ${
                  d.manufacturer
                    ? html`<span class="meta-item">
                        <i class="ti ti-building"></i>${d.manufacturer}
                      </span>`
                    : null
                }
              </div>
            </div>
          </div>
          <div class="actions">
            <rune-tooltip content="Edit device">
              <rune-button
                variant="ghost"
                icon="edit"
                @click=${this._onEdit}
                aria-label="Edit device"
              ></rune-button>
            </rune-tooltip>
            <rune-tooltip content="Delete device">
              <rune-button
                variant="ghost"
                icon="trash"
                @click=${() => (this._confirmingDelete = true)}
                aria-label="Delete device"
              ></rune-button>
            </rune-tooltip>
          </div>
        </div>
        <div class="commands">
          ${(d.commands ?? []).map(
            (c) => html`
              <button
                class="cmd"
                title=${`Send "${c.label ?? c.key}" to ${d.name}`}
                @click=${(e: Event) => this._send(c, e.currentTarget as HTMLButtonElement)}
              >
                <i class="ti ti-bolt"></i>
                <span>${c.label ?? c.key}</span>
              </button>
            `,
          )}
          <button class="cmd placeholder" @click=${this._learn}>
            <i class="ti ti-plus"></i>
            <span>${msg(str`Learn command`)}</span>
          </button>
        </div>
      </div>

      ${
        this._confirmingDelete
          ? html`<rune-dialog
              ?open=${true}
              size="small"
              .label=${msg(str`Delete device`)}
              @sl-after-hide=${() => (this._confirmingDelete = false)}
            >
              <p>${msg(str`Delete device "${d.name}"? This cannot be undone.`)}</p>
              <div
                slot="footer"
                style="display:flex;gap:var(--rune-space-2);justify-content:flex-end"
              >
                <rune-button
                  variant="secondary"
                  icon="x"
                  @click=${() => (this._confirmingDelete = false)}
                >
                  ${msg(str`Cancel`)}
                </rune-button>
                <rune-button variant="danger" icon="trash" @click=${this._confirmDelete}>
                  ${msg(str`Delete`)}
                </rune-button>
              </div>
            </rune-dialog>`
          : null
      }
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-device-card": RuneDeviceCard;
  }
}
