import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import "@/components/ui/index.js";

import { api } from "@/api/bridge.js";
import { store, subscribe } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

@customElement("rune-learn-dialog")
export class RuneLearnDialog extends LitElement {
  static styles = [
    sharedStyles,
    css`
      .body {
        display: flex;
        flex-direction: column;
        gap: var(--rune-space-3);
        min-width: 480px;
      }
      .help {
        background: var(--rune-primary-soft);
        border-left: 3px solid var(--rune-primary);
        padding: var(--rune-space-3) var(--rune-space-4);
        border-radius: var(--rune-radius-sm);
        font-size: var(--rune-fs-sm);
        color: var(--rune-text);
        line-height: var(--rune-lh-relaxed);
      }
      .help i {
        color: var(--rune-primary);
        margin-right: var(--rune-space-1);
        vertical-align: -2px;
      }
      .target {
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
        padding: var(--rune-space-3);
        background: var(--rune-surface-alt);
        border-radius: var(--rune-radius-sm);
        border: 1px solid var(--rune-border);
      }
      .target-label {
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        font-weight: var(--rune-fw-medium);
      }
      .target-value {
        font-family: var(--rune-font-mono);
        font-size: var(--rune-fs-sm);
        color: var(--rune-text-strong);
        font-weight: var(--rune-fw-medium);
      }
      .arrow {
        color: var(--rune-text-subtle);
        font-size: 14px;
      }
      .status {
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
        padding: var(--rune-space-3);
        background: var(--rune-surface-alt);
        border-radius: var(--rune-radius-sm);
        font-family: var(--rune-font-mono);
        font-size: var(--rune-fs-sm);
        color: var(--rune-text);
      }
      .status-dot {
        width: 8px;
        height: 8px;
        border-radius: var(--rune-radius-full);
        background: var(--rune-text-subtle);
        flex-shrink: 0;
      }
      .status-dot.live {
        background: var(--rune-warning);
        animation: rune-pulse 1.2s infinite;
      }
      .status-dot.ok {
        background: var(--rune-success);
      }
      .status-dot.err {
        background: var(--rune-danger);
      }
      @keyframes rune-pulse {
        0%,
        100% {
          opacity: 1;
          box-shadow: 0 0 0 0 var(--rune-warning);
        }
        50% {
          opacity: 0.5;
          box-shadow: 0 0 0 6px transparent;
        }
      }
      .timings {
        background: var(--rune-bg-elevated);
        padding: var(--rune-space-3);
        border-radius: var(--rune-radius-sm);
        font-family: var(--rune-font-mono);
        font-size: var(--rune-fs-xs);
        color: var(--rune-text);
        overflow-x: auto;
        max-height: 120px;
        border: 1px solid var(--rune-border);
        margin: 0;
      }
      .section-label {
        font-size: 10px;
        color: var(--rune-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: var(--rune-fw-semibold);
        margin-bottom: 2px;
      }
    `,
  ];

  @state() private _tick = 0;
  @state() private _busy = false;
  @state() private _saving = false;
  private _unsub: (() => void) | null = null;
  private _returnFocusTo: HTMLElement | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    this._unsub = subscribe(() => this._tick++);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsub?.();
  }

  private _cancel = (): void => {
    store.closeLearnDialog();
  };

  private _onShow = (): void => {
    this._returnFocusTo = (this.getRootNode() as Document | ShadowRoot)
      .activeElement as HTMLElement | null;
  };

  private _onAfterHide = (): void => {
    this._returnFocusTo?.focus();
    this._returnFocusTo = null;
    // Sync the store if the user closed the dialog via the X button.
    if (store.learnDialog.open) store.closeLearnDialog();
  };

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
      const commands = {
        ...device.commands,
      } as unknown as Record<string, Record<string, unknown>>;
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
    const canSave = ld.captured !== null && !this._saving;

    let dotClass = "";
    if (this._busy) dotClass = "live";
    else if (ld.captured) dotClass = "ok";
    else if (ld.status.startsWith("Failed")) dotClass = "err";

    return html`
      <rune-dialog
        ?open=${ld.open}
        size="medium"
        label="Learn command"
        @sl-show=${this._onShow}
        @sl-after-hide=${this._onAfterHide}
      >
        <div class="body">
          <div class="help">
            <i class="ti ti-info-circle"></i>
            Point your remote at the receiver and press the button you want to capture. RUNE records
            the raw timings and writes them into the command slot.
          </div>

          <div class="section-label">Command</div>
          <div class="target">
            <span class="target-value">${deviceName}</span>
            <i class="ti ti-arrow-right arrow"></i>
            <rune-chip variant="primary">${ld.commandKey}</rune-chip>
          </div>

          <div class="section-label">Status</div>
          <div class="status">
            <span class="status-dot ${dotClass}"></span>
            <span>${ld.status}</span>
          </div>

          <div class="section-label">Captured timings</div>
          <pre class="timings">${timingsText}</pre>
        </div>
        <div slot="footer" style="display:flex;gap:var(--rune-space-2);justify-content:flex-end">
          <rune-button variant="secondary" icon="x" @click=${this._cancel}> Cancel </rune-button>
          <rune-button
            variant="ghost"
            icon="antenna"
            ?loading=${this._busy}
            ?disabled=${ld.captured !== null && !this._busy}
            @click=${this._start}
          >
            ${ld.captured ? "Re-learn" : "Start learn"}
          </rune-button>
          <rune-button
            variant="primary"
            icon="device-floppy"
            ?loading=${this._saving}
            ?disabled=${!canSave}
            @click=${this._save}
          >
            Save &amp; close
          </rune-button>
        </div>
      </rune-dialog>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-learn-dialog": RuneLearnDialog;
  }
}
