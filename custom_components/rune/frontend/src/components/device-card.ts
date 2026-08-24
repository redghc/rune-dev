import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import "@/components/ui/index.js";
import "@/components/command-edit-dialog.js";

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
      .cmd-wrap {
        position: relative;
        display: block;
      }
      .cmd-wrap .cmd {
        width: 100%;
      }
      .cmd-placeholder-wrap {
        display: contents;
      }
      .cmd {
        position: relative;
        background: var(--rune-surface-alt);
        border: 1px solid var(--rune-border);
        border-radius: var(--rune-radius-sm);
        padding: calc(var(--rune-space-3) + 8px) var(--rune-space-2) var(--rune-space-3);
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
      .cmd-actions {
        display: flex;
        gap: 4px;
        justify-content: center;
        margin-top: 4px;
        flex-wrap: wrap;
      }
      .cmd-actions rune-button {
        flex: 1;
        min-width: 0;
      }
      .cmd-actions rune-button::part(base) {
        font-size: var(--rune-fs-xs);
        padding: 4px 8px;
        background: transparent;
        border: 1px solid var(--rune-border);
        color: var(--rune-text-muted);
        border-radius: var(--rune-radius-sm);
      }
      .cmd-actions rune-button::part(base):hover {
        background: var(--rune-primary-soft);
        border-color: var(--rune-primary);
        color: var(--rune-primary-text);
      }
      .cmd-actions rune-button.danger-btn::part(base) {
        color: var(--rune-danger);
      }
      .cmd-actions rune-button.danger-btn:hover::part(base) {
        background: var(--rune-danger-soft, rgba(220, 38, 38, 0.12));
        border-color: var(--rune-danger);
        color: var(--rune-danger);
      }
      .cmd-hint {
        margin-top: var(--rune-space-3);
        padding: var(--rune-space-2) var(--rune-space-3);
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-muted);
        background: var(--rune-surface-alt);
        border: 1px dashed var(--rune-border);
        border-radius: var(--rune-radius-sm);
        line-height: var(--rune-lh-normal);
        display: flex;
        gap: var(--rune-space-2);
        align-items: flex-start;
      }
      .cmd-hint i {
        font-size: 14px;
        color: var(--rune-primary);
        flex-shrink: 0;
        margin-top: 1px;
      }
    `,
  ];

  constructor() {
    super();
    attachStoreController(this);
  }

  @property({ attribute: false }) device!: DeviceSummary;

  @state() private _confirmingDelete = false;
  @state() private _confirmingCmdDelete: PulseCommand | null = null;
  @state() private _editingCmd: PulseCommand | null = null;

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

  /** Kick off the learn flow. The dialog handles command-key entry +
   *  capture + save in a single step-by-step flow. */
  private _learn(): void {
    store.openLearnDialog(this.device.id);
  }

  private _editCmd(cmd: PulseCommand): void {
    this._editingCmd = cmd;
  }

  private _relearnCmd(cmd: PulseCommand): void {
    // Reuse the existing Learn dialog — it's already wired for
    // capture + persist via the same `command/update` flow. The
    // dialog overwrites the existing command by key.
    store.openLearnDialog(this.device.id, cmd.key ?? "", cmd.label ?? "");
  }

  private _askDeleteCmd(cmd: PulseCommand): void {
    this._confirmingCmdDelete = cmd;
  }

  private _cancelDeleteCmd(): void {
    this._confirmingCmdDelete = null;
  }

  private async _confirmDeleteCmd(cmd: PulseCommand): Promise<void> {
    this._confirmingCmdDelete = null;
    try {
      await api.deleteCommand(this.device.id, cmd.key);
      store.pushToast(msg(str`Deleted "${cmd.label ?? cmd.key}"`), "ok");
      await refreshDevices();
    } catch (err) {
      reportError(err);
    }
  }

  private async _onCommandSaved(): Promise<void> {
    this._editingCmd = null;
    store.pushToast(msg(str`Command updated`), "ok");
    await refreshDevices();
  }

  private async _onCommandDeleted(): Promise<void> {
    this._editingCmd = null;
    await refreshDevices();
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
              <div class="cmd-wrap">
                <button
                  class="cmd"
                  title=${`Send "${c.label ?? c.key}" to ${d.name}`}
                  @click=${(e: Event) => this._send(c, e.currentTarget as HTMLButtonElement)}
                >
                  <i class="ti ti-bolt"></i>
                  <span>${c.label ?? c.key}</span>
                </button>
                <div class="cmd-actions" @click=${(e: Event) => e.stopPropagation()}>
                  <rune-button
                    icon="pencil"
                    variant="ghost"
                    size="small"
                    aria-label=${msg(str`Edit "${c.label ?? c.key}"`)}
                    @click=${(e: Event) => {
                      e.stopPropagation();
                      this._editCmd(c);
                    }}
                  >
                    ${msg(str`Edit`)}
                  </rune-button>
                  <rune-button
                    icon="refresh"
                    variant="ghost"
                    size="small"
                    aria-label=${msg(str`Re-learn "${c.label ?? c.key}"`)}
                    @click=${(e: Event) => {
                      e.stopPropagation();
                      this._relearnCmd(c);
                    }}
                  >
                    ${msg(str`Re-learn`)}
                  </rune-button>
                  <rune-button
                    icon="trash"
                    variant="ghost"
                    size="small"
                    class="danger-btn"
                    aria-label=${msg(str`Delete "${c.label ?? c.key}"`)}
                    @click=${(e: Event) => {
                      e.stopPropagation();
                      this._askDeleteCmd(c);
                    }}
                  >
                    ${msg(str`Delete`)}
                  </rune-button>
                </div>
              </div>
            `,
          )}
          <button class="cmd placeholder" @click=${this._learn}>
            <i class="ti ti-plus"></i>
            <span>${msg(str`Learn command`)}</span>
          </button>
        </div>
        ${
          (d.commands ?? []).length > 0
            ? html`
                <div class="cmd-hint">
                  <i class="ti ti-info-circle"></i>
                  ${msg(
                    str`Each command is also exposed to Home Assistant as a button entity — visible under Settings → Devices & Services → ${d.name} and on the Buttons dashboard. Use the Edit / Re-learn / Delete buttons under each tile to manage them.`,
                  )}
                </div>
              `
            : null
        }
      </div>

      <rune-command-edit-dialog
        .deviceId=${d.id}
        .command=${this._editingCmd}
        ?open=${this._editingCmd !== null}
        @close=${() => (this._editingCmd = null)}
        @saved=${this._onCommandSaved}
        @deleted=${this._onCommandDeleted}
      ></rune-command-edit-dialog>

      ${
        this._confirmingCmdDelete
          ? html`<rune-dialog
              ?open=${true}
              size="small"
              .label=${msg(str`Delete command`)}
              @sl-after-hide=${this._cancelDeleteCmd}
            >
              <div
                slot="subtitle"
                style="font-family:var(--rune-font);font-size:var(--rune-fs-sm);color:var(--rune-text-muted);line-height:var(--rune-lh-normal);margin-bottom:var(--rune-space-3)"
              >
                ${msg(str`This action is permanent and cannot be undone.`)}
              </div>
              <p
                style="margin:0;color:var(--rune-text);font-size:var(--rune-fs-sm);line-height:var(--rune-lh-normal)"
              >
                ${msg(str`Delete command "${this._confirmingCmdDelete.label ?? this._confirmingCmdDelete.key}" from ${d.name}?`)}
              </p>
              <div slot="footer">
                <rune-button variant="secondary" @click=${this._cancelDeleteCmd}>
                  ${msg(str`Cancel`)}
                </rune-button>
                <rune-button
                  variant="danger"
                  icon="trash"
                  @click=${() => this._confirmDeleteCmd(this._confirmingCmdDelete!)}
                >
                  ${msg(str`Delete`)}
                </rune-button>
              </div>
            </rune-dialog>`
          : null
      }
      ${
        this._confirmingDelete
          ? html`<rune-dialog
              ?open=${true}
              size="small"
              .label=${msg(str`Delete device`)}
              @sl-after-hide=${() => (this._confirmingDelete = false)}
            >
              <div
                slot="subtitle"
                style="font-family:var(--rune-font);font-size:var(--rune-fs-sm);color:var(--rune-text-muted);line-height:var(--rune-lh-normal);margin-bottom:var(--rune-space-3)"
              >
                ${msg(str`This action is permanent and cannot be undone.`)}
              </div>
              <p
                style="margin:0;color:var(--rune-text);font-size:var(--rune-fs-sm);line-height:var(--rune-lh-normal)"
              >
                ${msg(str`Delete device "${d.name}"?`)}
              </p>
              <div slot="footer">
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
