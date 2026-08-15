import { css, html, LitElement } from "lit";
import { customElement, query, state } from "lit/decorators.js";

import { api } from "../api/bridge.js";
import { store, subscribe } from "../state/store.js";
import { sharedStyles } from "../styles/shared.js";

@customElement("rune-learn-dialog")
export class RuneLearnDialog extends LitElement {
  static styles = [
    sharedStyles,
    css`
      dialog {
        background: var(--card);
        color: var(--text);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 24px;
        min-width: 420px;
        max-width: 90vw;
      }
      dialog::backdrop {
        background: rgba(0, 0, 0, 0.6);
      }
      h2 {
        margin: 0 0 16px;
      }
      .form-row {
        display: flex;
        flex-direction: column;
        gap: 4px;
        margin-bottom: 12px;
      }
      .form-row label {
        font-size: 12px;
        color: var(--muted);
      }
      .dialog-actions {
        display: flex;
        gap: 8px;
        justify-content: flex-end;
        margin-top: 16px;
      }
      pre {
        background: var(--bg-2);
        padding: 8px;
        border-radius: 4px;
        font-size: 11px;
        overflow-x: auto;
      }
      .status {
        font-family: monospace;
      }
    `,
  ];

  @state() private _tick = 0;
  @state() private _busy = false;
  @state() private _saving = false;
  private _unsub: (() => void) | null = null;
  @query("#dlg") private _dlg!: HTMLDialogElement;

  connectedCallback(): void {
    super.connectedCallback();
    this._unsub = subscribe(() => {
      const wasOpen = this._dlg?.open ?? false;
      this._tick++;
      queueMicrotask(() => {
        const dlg = this._dlg;
        if (!dlg) return;
        if (store.learnDialog.open && !wasOpen) dlg.showModal();
        else if (!store.learnDialog.open && wasOpen) dlg.close();
      });
    });
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsub?.();
  }

  private _cancel(): void {
    store.closeLearnDialog();
  }

  private async _start(): Promise<void> {
    const { deviceId, commandKey } = store.learnDialog;
    if (!deviceId || !commandKey) return;
    store.updateLearn({ status: "Capturing… press the button on your remote NOW" });
    this._busy = true;
    try {
      const result = await api.learnCommand({
        device_id: deviceId,
        command_key: commandKey,
        timeout_s: 15,
      });
      if (result?.captured) {
        store.updateLearn({
          status: `Captured: ${result.captured.protocol_label ?? "raw"} @ ${result.carrier_frequency_hz} Hz`,
          captured: result.captured,
          rawTimings: result.raw_timings,
          carrierHz: result.carrier_frequency_hz,
        });
      } else {
        store.updateLearn({ status: "No signal captured" });
      }
    } catch (err) {
      store.updateLearn({ status: `Failed: ${(err as Error).message}` });
    } finally {
      this._busy = false;
    }
  }

  private async _save(): Promise<void> {
    const { deviceId, commandKey, captured, rawTimings } = store.learnDialog;
    if (!deviceId || !captured || !rawTimings) return;
    this._saving = true;
    try {
      const { device } = await api.getDevice(deviceId);
      const commands = { ...device.commands } as unknown as Record<string, Record<string, unknown>>;
      commands[commandKey] = {
        key: commandKey,
        label: commandKey.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()),
        category: "custom",
        signal_category: { ...captured.signal_category },
        payload: { ...captured.payload, raw_timings: rawTimings },
      };
      await api.updateDevice({ device_id: deviceId, commands });
      store.pushToast(`Learned "${commandKey}"`, "ok");
      store.closeLearnDialog();
      const { devices } = await api.list();
      store.setDevices(devices ?? []);
    } catch (err) {
      store.pushToast((err as Error).message, "err");
    } finally {
      this._saving = false;
    }
  }

  render() {
    void this._tick;
    const ld = store.learnDialog;
    const timings = ld.rawTimings;
    const timingsText = timings
      ? JSON.stringify(timings.slice(0, 30)) + (timings.length > 30 ? "…" : "")
      : "—";
    const deviceName = store.devices.find((d) => d.id === ld.deviceId)?.name ?? "—";
    const target = `${deviceName} → ${ld.commandKey}`;
    const canSave = ld.captured !== null && !this._saving;
    return html`
      <dialog id="dlg" @close=${() => store.closeLearnDialog()}>
        <h2>Learn command</h2>
        <div class="help">
          Point your remote at the receiver and press the button you want to capture. RUNE records
          the raw timings and writes them into the command slot.
        </div>
        <div class="form-row">
          <label>Command</label>
          <div><strong>${target}</strong></div>
        </div>
        <div class="form-row">
          <label>Status</label>
          <div class="status">${ld.status}</div>
        </div>
        <div class="form-row">
          <label>Captured timings</label>
          <pre>${timingsText}</pre>
        </div>
        <div class="dialog-actions">
          <button class="secondary" type="button" @click=${this._cancel}>Cancel</button>
          <button type="button" @click=${this._start} ?disabled=${this._busy}>
            ${this._busy ? "Capturing…" : "Start learn"}
          </button>
          <button type="button" @click=${this._save} ?disabled=${!canSave}>
            ${this._saving ? "Saving…" : "Save & close"}
          </button>
        </div>
      </dialog>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-learn-dialog": RuneLearnDialog;
  }
}
