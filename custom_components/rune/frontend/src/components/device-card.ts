import { css, html, LitElement } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import { api } from "@/api/bridge.js";
import { store } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

import type { DeviceSummary, PulseCommand } from "@/types.js";

@customElement("rune-device-card")
export class RuneDeviceCard extends LitElement {
  static styles = [
    sharedStyles,
    css`
      .device {
        background: var(--card);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        border: 1px solid var(--border);
      }
      .device-head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 12px;
        gap: 8px;
      }
      .device h3 {
        margin: 0 0 4px;
        font-size: 16px;
        font-weight: 500;
      }
      .meta {
        color: var(--muted);
        font-size: 12px;
      }
      .actions {
        display: flex;
        gap: 4px;
      }
      .actions button {
        padding: 4px 10px;
        font-size: 12px;
      }
      .commands {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: 6px;
      }
      .cmd {
        background: var(--bg-2);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 8px;
        cursor: pointer;
        font: inherit;
        color: var(--text);
        font-size: 12px;
        text-align: center;
        transition: all 0.1s;
      }
      .cmd:hover {
        background: var(--primary);
        color: white;
        border-color: var(--primary);
      }
      .cmd:active {
        transform: scale(0.97);
      }
      .cmd.flash {
        background: var(--ok) !important;
        color: white !important;
      }
      .cmd.placeholder {
        border-style: dashed;
        color: var(--muted);
      }
    `,
  ];

  @property({ attribute: false }) device!: DeviceSummary;

  @state() private _flash: string | null = null;

  private _onEdit(): void {
    store.openDeviceDialog(this.device);
  }

  private async _onDelete(): Promise<void> {
    if (!confirm(`Delete device "${this.device.name}"?`)) return;
    try {
      await api.deleteDevice(this.device.id);
      store.pushToast("Deleted", "ok");
      const { devices } = await api.list();
      store.setDevices(devices ?? []);
    } catch (err) {
      store.pushToast((err as Error).message, "err");
    }
  }

  private async _send(cmd: PulseCommand, btn: HTMLButtonElement): Promise<void> {
    try {
      await api.sendCommand(this.device.id, cmd.key);
      btn.classList.add("flash");
      setTimeout(() => btn.classList.remove("flash"), 280);
      store.pushToast(`Sent ${cmd.label ?? cmd.key}`, "ok");
    } catch (err) {
      store.pushToast((err as Error).message, "err");
    }
  }

  private _learn(): void {
    const key = prompt(
      `Learn which command on "${this.device.name}"?\n\n` +
        `Enter a command key (e.g. "off", "speed_2", "power_on"):`,
      "off",
    );
    if (!key) return;
    store.openLearnDialog(this.device.id, key.trim());
  }

  render() {
    const d = this.device;
    const tx = (d.transmitter_entity_ids ?? []).join(", ") || "—";
    const meta = `${d.category} • ${d.command_count} command(s) • tx: ${tx}`;
    void this._flash;
    return html`
      <div class="device">
        <div class="device-head">
          <div>
            <h3>${d.name}</h3>
            <div class="meta">${meta}</div>
          </div>
          <div class="actions">
            <button class="secondary" @click=${this._onEdit}>Edit</button>
            <button class="danger" @click=${this._onDelete}>Delete</button>
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
                ${c.label ?? c.key}
              </button>
            `,
          )}
          <button class="cmd placeholder" @click=${this._learn}>+ Learn command</button>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-device-card": RuneDeviceCard;
  }
}
