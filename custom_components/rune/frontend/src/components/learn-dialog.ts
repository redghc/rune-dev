import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import "@/components/ui/index.js";

import { api, refreshDevices } from "@/api/bridge.js";
import { attachDialogFocus } from "@/components/ui/dialog-focus.js";
import { attachStoreController } from "@/state/store-controller.js";
import { reportError, store } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

import type { LearnStatus } from "@/state/store.js";
import type { LearnResult } from "@/types.js";

const STATUS_RENDER: Record<LearnStatus["kind"], (s: LearnStatus) => unknown> = {
  idle: () => msg(str`Idle — click Start learn`),
  capturing: () => msg(str`Capturing… press the button on your remote NOW`),
  no_signal: () => msg(str`No signal captured`),
  failed: (s) => (s.kind === "failed" ? msg(str`Failed: ${s.message}`) : msg(str`Failed`)),
  captured: (s) =>
    s.kind === "captured"
      ? msg(str`Captured: ${s.protocol} @ ${s.carrierHz} Hz`)
      : msg(str`Captured`),
};

@customElement("rune-learn-dialog")
@localized()
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

  constructor() {
    super();
    attachStoreController(this);
    attachDialogFocus(this, () => {
      if (store.learnDialog.open) store.closeLearnDialog();
    });
  }

  @state() private _busy = false;
  @state() private _saving = false;

  private _cancel = (): void => {
    store.closeLearnDialog();
  };

  private async _start(): Promise<void> {
    const { deviceId, commandKey } = store.learnDialog;
    if (!deviceId || !commandKey) return;
    store.updateLearn({ status: { kind: "capturing" } });
    this._busy = true;
    try {
      const result = await api.learnCommand({
        device_id: deviceId,
        command_key: commandKey,
        timeout_s: 15,
      });
      if (result?.captured) {
        store.updateLearn({
          status: {
            kind: "captured",
            protocol: result.captured.protocol_label ?? "raw",
            carrierHz: result.carrier_frequency_hz,
          },
          captured: result.captured,
          rawTimings: result.raw_timings,
          carrierHz: result.carrier_frequency_hz,
        });
      } else {
        store.updateLearn({ status: { kind: "no_signal" } });
      }
    } catch (err) {
      store.updateLearn({
        status: { kind: "failed", message: (err as Error).message },
      });
    } finally {
      this._busy = false;
    }
  }

  /** Compose a new ``PulseCommand`` from the captured timings. */
  private _buildCommand(
    commandKey: string,
    captured: LearnResult["captured"],
    rawTimings: number[],
  ): Record<string, unknown> {
    return {
      key: commandKey,
      label: commandKey.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()),
      category: "custom",
      signal_category: { ...captured.signal_category },
      payload: { ...captured.payload, raw_timings: rawTimings },
    };
  }

  private async _save(): Promise<void> {
    const { deviceId, commandKey, captured, rawTimings } = store.learnDialog;
    if (!deviceId || !captured || !rawTimings) return;
    this._saving = true;
    try {
      const { device } = await api.getDevice(deviceId);
      const commands = {
        ...(device.commands as unknown as Record<string, Record<string, unknown>>),
      };
      commands[commandKey] = this._buildCommand(commandKey, captured, rawTimings);
      await api.updateDevice({ device_id: deviceId, commands });
      store.pushToast(msg(str`Learned "${commandKey}"`), "ok");
      store.closeLearnDialog();
      await refreshDevices();
    } catch (err) {
      reportError(err);
    } finally {
      this._saving = false;
    }
  }

  render() {
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
    else if (ld.status.kind === "failed") dotClass = "err";

    return html`
      <rune-dialog ?open=${ld.open} size="medium" .label=${msg(str`Learn command`)}>
        <div class="body">
          <div class="help">
            <i class="ti ti-info-circle"></i>
            ${msg(
              html`Point your remote at the receiver and press the button you want to capture. RUNE
              records the raw timings and writes them into the command slot.`,
            )}
          </div>

          <div class="section-label">${msg(str`Command`)}</div>
          <div class="target">
            <span class="target-value">${deviceName}</span>
            <i class="ti ti-arrow-right arrow"></i>
            <rune-chip variant="primary">${ld.commandKey}</rune-chip>
          </div>

          <div class="section-label">${msg(str`Status`)}</div>
          <div class="status">
            <span class="status-dot ${dotClass}"></span>
            <span>${STATUS_RENDER[ld.status.kind](ld.status)}</span>
          </div>

          <div class="section-label">${msg(str`Captured timings`)}</div>
          <pre class="timings">${timingsText}</pre>
        </div>
        <div slot="footer" style="display:flex;gap:var(--rune-space-2);justify-content:flex-end">
          <rune-button variant="secondary" icon="x" @click=${this._cancel}>
            ${msg(str`Cancel`)}
          </rune-button>
          <rune-button
            variant="ghost"
            icon="antenna"
            ?loading=${this._busy}
            ?disabled=${ld.captured !== null && !this._busy}
            @click=${this._start}
          >
            ${ld.captured ? msg(str`Re-learn`) : msg(str`Start learn`)}
          </rune-button>
          <rune-button
            variant="primary"
            icon="device-floppy"
            ?loading=${this._saving}
            ?disabled=${!canSave}
            @click=${this._save}
          >
            ${msg(str`Save & close`)}
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
