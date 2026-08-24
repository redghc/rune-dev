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
        grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
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
        /* Right padding reserves space for the 24px kebab icon at
         * right:4px so the label never collides with the dots. */
        padding: var(--rune-space-3) calc(var(--rune-space-2) + 24px) var(--rune-space-3)
          var(--rune-space-2);
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
      .cmd-kebab {
        position: absolute;
        top: 4px;
        right: 4px;
        width: 24px;
        height: 24px;
        padding: 0;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: var(--rune-surface);
        border: 1px solid var(--rune-border);
        color: var(--rune-text);
        border-radius: var(--rune-radius-sm);
        cursor: pointer;
        opacity: 0.85;
        transition:
          opacity var(--rune-dur-fast) var(--rune-ease),
          background-color var(--rune-dur-fast) var(--rune-ease),
          border-color var(--rune-dur-fast) var(--rune-ease),
          color var(--rune-dur-fast) var(--rune-ease);
      }
      .cmd:hover .cmd-kebab,
      .cmd-kebab:hover,
      .cmd-kebab:focus-within {
        opacity: 1;
      }
      .cmd-kebab:hover {
        background: var(--rune-primary);
        border-color: var(--rune-primary);
        color: var(--rune-on-primary);
      }
      .cmd-kebab:focus-visible {
        outline: 2px solid var(--rune-primary);
        outline-offset: 1px;
      }
      .cmd-kebab i {
        font-size: 14px;
        line-height: 1;
      }
      .menu-popover {
        background: var(--rune-surface);
        border: 1px solid var(--rune-border);
        border-radius: var(--rune-radius-sm);
        box-shadow: var(--rune-shadow-3);
        padding: var(--rune-space-1);
        z-index: 1000;
        min-width: 180px;
        display: flex;
        flex-direction: column;
        /* Clicks on the menu's padding pass through to whatever sits
         * behind (often a sibling cmd button the menu is overlapping).
         * Only the menu items capture clicks; the rest is a visual
         * shell so we can still see the menu above the card. */
        pointer-events: none;
      }
      .menu-item {
        background: transparent;
        border: none;
        text-align: left;
        padding: var(--rune-space-2) var(--rune-space-3);
        font: inherit;
        font-size: var(--rune-fs-sm);
        color: var(--rune-text);
        cursor: pointer;
        border-radius: var(--rune-radius-sm);
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
        width: 100%;
        /* Counter the menu container's pointer-events: none so the
         * rows stay clickable. */
        pointer-events: auto;
      }
      .menu-item:hover {
        background: var(--rune-primary-soft);
        color: var(--rune-primary-text);
      }
      .menu-item.danger {
        color: var(--rune-danger);
      }
      .menu-item.danger:hover {
        background: var(--rune-danger-soft, rgba(220, 38, 38, 0.12));
        color: var(--rune-danger);
      }
      .menu-item i {
        font-size: 16px;
        width: 16px;
        text-align: center;
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
  @state() private _openMenuKey: string | null = null;
  @state() private _menuAnchor: HTMLElement | null = null;
  @state() private _menuPos: { x: number; y: number } | null = null;

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
    // Catch the client-side case where the backend reported the
    // command as having a payload, but the compact ``commands``
    // summary the SPA received has ``has_payload: false`` (e.g. the
    // user learned a command via the API but never actually
    // captured a signal). Sending it would no-op at the hardware
    // — the user sees "Sent" but the device doesn't react.
    const meta = (this.device.commands ?? []).find((c) => c.key === cmd.key);
    if (meta && meta.has_payload === false) {
      store.pushToast(
        msg(str`"${cmd.label ?? cmd.key}" has no captured signal — re-learn it from the ⋮ menu`),
        "err",
      );
      return;
    }
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

  /** Open the per-command menu near the kebab icon the user clicked.
   *  We position the popover with ``position: fixed`` so it floats
   *  above the grid without disturbing layout, and use ``fixed``-
   *  coords so scrolling the device card doesn't drag the menu
   *  with it. */
  private _toggleMenu(cmd: PulseCommand, anchor: HTMLElement): void {
    if (this._openMenuKey === cmd.key) {
      this._closeMenu();
      return;
    }
    const rect = anchor.getBoundingClientRect();
    this._openMenuKey = cmd.key;
    this._menuAnchor = anchor;
    // ``position: fixed`` is viewport-relative, so we feed it raw
    // ``getBoundingClientRect`` coords — adding ``window.scrollX/Y``
    // would push the menu off-screen on any scrolled page.
    this._menuPos = {
      x: rect.left,
      y: rect.bottom,
    };
  }

  private _closeMenu = (): void => {
    this._openMenuKey = null;
    this._menuAnchor = null;
    this._menuPos = null;
  };

  private _onDocClick = (ev: MouseEvent): void => {
    if (!this._openMenuKey) return;
    const path = ev.composedPath();
    if (this._menuAnchor && path.includes(this._menuAnchor)) return;
    if (path.some((n) => (n as HTMLElement).id === "rune-cmd-menu")) return;
    this._closeMenu();
  };

  private _editCmd(cmd: PulseCommand): void {
    this._closeMenu();
    this._editingCmd = cmd;
  }

  private _relearnCmd(cmd: PulseCommand): void {
    this._closeMenu();
    // Reuse the existing Learn dialog — it's already wired for
    // capture + persist via the same `command/update` flow. The
    // dialog overwrites the existing command by key.
    store.openLearnDialog(this.device.id, cmd.key ?? "", cmd.label ?? "");
  }

  private _askDeleteCmd(cmd: PulseCommand): void {
    this._closeMenu();
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

  connectedCallback(): void {
    super.connectedCallback();
    document.addEventListener("click", this._onDocClick);
  }

  disconnectedCallback(): void {
    document.removeEventListener("click", this._onDocClick);
    super.disconnectedCallback();
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
                <button
                  type="button"
                  class="cmd-kebab"
                  title=${msg(str`Options for "${c.label ?? c.key}"`)}
                  aria-label=${msg(str`Options for "${c.label ?? c.key}"`)}
                  @click=${(e: Event) => {
                    e.stopPropagation();
                    this._toggleMenu(c, e.currentTarget as HTMLElement);
                  }}
                >
                  <i class="ti ti-dots-vertical" aria-hidden="true"></i>
                </button>
              </div>
            `,
          )}
          <button class="cmd placeholder" @click=${this._learn}>
            <i class="ti ti-plus"></i>
            <span>${msg(str`Learn command`)}</span>
          </button>
        </div>
      </div>

      ${
        this._openMenuKey && this._menuPos
          ? html`
              <div
                id="rune-cmd-menu"
                class="menu-popover"
                style=${`position:fixed;left:${this._menuPos.x}px;top:${this._menuPos.y}px;`}
              >
                <button
                  class="menu-item"
                  @click=${() => {
                    const cmd = (d.commands ?? []).find((c) => c.key === this._openMenuKey);
                    if (cmd) this._editCmd(cmd);
                  }}
                >
                  <i class="ti ti-pencil"></i>
                  ${msg(str`Edit`)}
                </button>
                <button
                  class="menu-item"
                  @click=${() => {
                    const cmd = (d.commands ?? []).find((c) => c.key === this._openMenuKey);
                    if (cmd) this._relearnCmd(cmd);
                  }}
                >
                  <i class="ti ti-refresh"></i>
                  ${msg(str`Re-learn`)}
                </button>
                <button
                  class="menu-item danger"
                  @click=${() => {
                    const cmd = (d.commands ?? []).find((c) => c.key === this._openMenuKey);
                    if (cmd) this._askDeleteCmd(cmd);
                  }}
                >
                  <i class="ti ti-trash"></i>
                  ${msg(str`Delete`)}
                </button>
              </div>
            `
          : null
      }

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
