import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import type { TemplateResult } from "lit";

import "@/components/ui/index.js";

import { api, refreshDevices } from "@/api/bridge.js";
import { attachDialogFocus } from "@/components/ui/dialog-focus.js";
import { attachStoreController } from "@/state/store-controller.js";
import { reportError, store } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

import type { RuneStepDef } from "@/components/ui/stepper.js";
import type { LearnDialogState, LearnStep } from "@/state/store.js";

@customElement("rune-learn-dialog")
@localized()
export class RuneLearnDialog extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: contents;
      }
      .step-body {
        display: flex;
        flex-direction: column;
        gap: var(--rune-space-3);
      }
      .help {
        background: var(--rune-primary-soft);
        border-left: 3px solid var(--rune-primary);
        padding: var(--rune-space-3) var(--rune-space-4);
        border-radius: var(--rune-radius-sm);
        font-size: var(--rune-fs-sm);
        color: var(--rune-text);
        line-height: var(--rune-lh-normal);
        display: flex;
        gap: var(--rune-space-2);
      }
      .help i {
        color: var(--rune-primary);
        flex-shrink: 0;
        line-height: 1.6;
      }
      .target {
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
        padding: var(--rune-space-3) var(--rune-space-4);
        background: var(--rune-surface-alt);
        border-radius: var(--rune-radius-sm);
        border: 1px solid var(--rune-border);
      }
      .target-label {
        font-size: 10px;
        color: var(--rune-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        font-weight: var(--rune-fw-semibold);
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
        gap: var(--rune-space-3);
        padding: var(--rune-space-3) var(--rune-space-4);
        background: var(--rune-surface-alt);
        border-radius: var(--rune-radius-sm);
        border: 1px solid var(--rune-border);
        font-family: var(--rune-font-mono);
        font-size: var(--rune-fs-sm);
        color: var(--rune-text);
      }
      .status-dot {
        width: 10px;
        height: 10px;
        border-radius: var(--rune-radius-full);
        background: var(--rune-text-subtle);
        flex-shrink: 0;
        transition: background-color var(--rune-dur) var(--rune-ease);
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
          transform: scale(1);
        }
        50% {
          opacity: 0.55;
          transform: scale(0.85);
        }
      }
      .timings {
        background: var(--rune-bg-elevated);
        padding: var(--rune-space-3) var(--rune-space-4);
        border-radius: var(--rune-radius-sm);
        font-family: var(--rune-font-mono);
        font-size: var(--rune-fs-xs);
        color: var(--rune-text);
        border: 1px solid var(--rune-border);
        margin: 0;
        white-space: pre-wrap;
        word-break: break-all;
        max-height: 140px;
        overflow-y: auto;
      }
      .section-label {
        font-size: 10px;
        color: var(--rune-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: var(--rune-fw-semibold);
      }
      .err {
        color: var(--rune-danger-text);
        background: var(--rune-danger-soft);
        padding: var(--rune-space-2) var(--rune-space-3);
        border-radius: var(--rune-radius-sm);
        font-size: var(--rune-fs-xs);
      }
      .summary {
        display: grid;
        grid-template-columns: max-content 1fr;
        gap: var(--rune-space-2) var(--rune-space-4);
        padding: var(--rune-space-3) var(--rune-space-4);
        background: var(--rune-surface-alt);
        border-radius: var(--rune-radius-sm);
        border: 1px solid var(--rune-border);
        font-size: var(--rune-fs-sm);
      }
      .summary dt {
        margin: 0;
        color: var(--rune-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        font-size: 10px;
        font-weight: var(--rune-fw-semibold);
        align-self: center;
      }
      .summary dd {
        margin: 0;
        color: var(--rune-text-strong);
        font-family: var(--rune-font-mono);
        font-size: var(--rune-fs-sm);
        word-break: break-word;
      }
      .grow {
        flex: 1;
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
  @state() private _pickError = "";
  @state() private _commandKeyDraft = "";
  @state() private _commandLabelDraft = "";

  private get _stepDefs(): RuneStepDef[] {
    return [
      { key: "pick", label: () => msg(str`Command`), icon: "tag" },
      { key: "capture", label: () => msg(str`Capture`), icon: "antenna" },
      { key: "review", label: () => msg(str`Review & save`), icon: "device-floppy" },
    ];
  }

  private _statusRender(ld: LearnDialogState): unknown {
    const s = ld.status;
    switch (s.kind) {
      case "idle":
        return msg(str`Idle — click Start learn`);
      case "capturing":
        return msg(str`Capturing… press the button on your remote NOW`);
      case "no_signal":
        return msg(str`No signal captured — try again`);
      case "failed":
        return msg(str`Failed: ${s.message}`);
      case "captured":
        return msg(str`Captured: ${s.protocol} @ ${s.carrierHz} Hz`);
    }
  }

  private _onClose = (): void => {
    store.closeLearnDialog();
  };

  private _onPickInput = (ev: CustomEvent<{ value: string }>, field: "key" | "label"): void => {
    if (field === "key") this._commandKeyDraft = ev.detail.value;
    else this._commandLabelDraft = ev.detail.value;
  };

  private _confirmPick = (): void => {
    const key = this._commandKeyDraft.trim();
    if (!/^[a-z0-9_]+$/i.test(key)) {
      this._pickError = msg(str`Use lowercase letters, digits, and underscores only.`);
      return;
    }
    this._pickError = "";
    store.updateLearn({
      commandKey: key,
      commandLabel: this._commandLabelDraft.trim() || key,
      step: "capture",
      status: { kind: "idle" },
      captured: null,
      rawTimings: null,
      carrierHz: null,
    });
  };

  private async _start(): Promise<void> {
    const { deviceId, commandKey } = store.learnDialog;
    if (!deviceId || !commandKey) return;
    store.updateLearn({ status: { kind: "capturing" }, step: "capture" });
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
          step: "review",
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

  private _recapture = (): void => {
    store.resetLearnCapture();
    store.setLearnStep("capture");
  };

  private _backToPick = (): void => {
    store.setLearnStep("pick");
  };

  /** Compose a new ``PulseCommand`` from the captured timings. */
  private _buildCommand(
    commandKey: string,
    commandLabel: string,
    captured: NonNullable<LearnDialogState["captured"]>,
    rawTimings: number[],
  ): Record<string, unknown> {
    return {
      key: commandKey,
      label: commandLabel || commandKey.replace(/_/g, " "),
      category: "custom",
      signal_category: { ...captured.signal_category },
      payload: { ...captured.payload, raw_timings: rawTimings },
    };
  }

  private async _save(): Promise<void> {
    const { deviceId, commandKey, commandLabel, captured, rawTimings } = store.learnDialog;
    if (!deviceId || !captured || !rawTimings) return;
    this._saving = true;
    try {
      const { device } = await api.getDevice(deviceId);
      const commands = {
        ...(device.commands as unknown as Record<string, Record<string, unknown>>),
      };
      commands[commandKey] = this._buildCommand(commandKey, commandLabel, captured, rawTimings);
      await api.updateDevice({ device_id: deviceId, commands });
      store.pushToast(msg(str`Learned "${commandLabel || commandKey}"`), "ok");
      store.closeLearnDialog();
      await refreshDevices();
    } catch (err) {
      reportError(err);
    } finally {
      this._saving = false;
    }
  }

  private _renderPick(deviceName: string): TemplateResult {
    const ld = store.learnDialog;
    return html`
      <div class="step-body">
        <div class="help">
          <i class="ti ti-info-circle"></i>
          <span>
            ${msg(
              html`Pick a unique identifier and a friendly label for the command you want RUNE to
              learn. You will press the remote button on the next step.`,
            )}
          </span>
        </div>
        <div class="section-label">${msg(str`Device`)}</div>
        <div class="target">
          <span class="target-label">${msg(str`Device`)}</span>
          <span class="target-value">${deviceName}</span>
        </div>
        <rune-input
          label=${msg(str`Command key`)}
          icon="tag"
          .helper=${msg(str`Lowercase identifier, e.g. off, speed_2, power_on`)}
          .placeholder=${msg(str`off`)}
          .value=${this._commandKeyDraft || ld.commandKey}
          .error=${this._pickError}
          required
          maxlength="32"
          @rune-input=${(ev: CustomEvent<{ value: string }>) => this._onPickInput(ev, "key")}
        ></rune-input>
        <rune-input
          label=${msg(str`Label`)}
          icon="label"
          .helper=${msg(str`What users see on the device card`)}
          .placeholder=${msg(str`Power off`)}
          .value=${this._commandLabelDraft || ld.commandLabel}
          maxlength="32"
          @rune-input=${(ev: CustomEvent<{ value: string }>) => this._onPickInput(ev, "label")}
        ></rune-input>
      </div>
    `;
  }

  private _renderCapture(deviceName: string): TemplateResult {
    const ld = store.learnDialog;
    let dotClass = "";
    if (this._busy) dotClass = "live";
    else if (ld.status.kind === "captured") dotClass = "ok";
    else if (ld.status.kind === "failed" || ld.status.kind === "no_signal") dotClass = "err";
    return html`
      <div class="step-body">
        <div class="help">
          <i class="ti ti-info-circle"></i>
          <span>
            ${msg(
              html`Point your remote at the receiver and press the button you want to capture. RUNE
              listens for up to 15 seconds.`,
            )}
          </span>
        </div>
        <div class="section-label">${msg(str`Capturing for`)}</div>
        <div class="target">
          <span class="target-label">${msg(str`Command`)}</span>
          <span class="target-value">${ld.commandLabel || ld.commandKey}</span>
          <i class="ti ti-arrow-right arrow"></i>
          <span class="target-value">${deviceName}</span>
        </div>
        <div class="section-label">${msg(str`Status`)}</div>
        <div class="status">
          <span class="status-dot ${dotClass}"></span>
          <span>${this._statusRender(ld)}</span>
        </div>
      </div>
    `;
  }

  private _renderReview(): TemplateResult {
    const ld = store.learnDialog;
    const timings = ld.rawTimings;
    const timingsText = timings
      ? JSON.stringify(timings.slice(0, 30)) + (timings.length > 30 ? "…" : "")
      : "—";
    const protocol = ld.status.kind === "captured" ? ld.status.protocol : "—";
    const carrier = ld.status.kind === "captured" ? `${ld.status.carrierHz} Hz` : "—";
    const pulses = timings?.length ?? 0;
    return html`
      <div class="step-body">
        <div class="help">
          <i class="ti ti-check"></i>
          <span>
            ${msg(
              html`RUNE captured the signal. Review the details below and save — the timings land in
              the command slot for this device.`,
            )}
          </span>
        </div>
        <dl class="summary">
          <dt>${msg(str`Device`)}</dt>
          <dd>${store.devices.find((d) => d.id === ld.deviceId)?.name ?? "—"}</dd>
          <dt>${msg(str`Command`)}</dt>
          <dd>${ld.commandLabel || ld.commandKey}</dd>
          <dt>${msg(str`Protocol`)}</dt>
          <dd>${protocol}</dd>
          <dt>${msg(str`Carrier`)}</dt>
          <dd>${carrier}</dd>
          <dt>${msg(str`Pulses`)}</dt>
          <dd>${pulses}</dd>
        </dl>
        <div class="section-label">${msg(str`Raw timings`)}</div>
        <pre class="timings">${timingsText}</pre>
      </div>
    `;
  }

  private _renderStep(deviceName: string): TemplateResult {
    const step: LearnStep = store.learnDialog.step;
    switch (step) {
      case "pick":
        return this._renderPick(deviceName);
      case "capture":
        return this._renderCapture(deviceName);
      case "review":
        return this._renderReview();
    }
  }

  private _renderFooter(): TemplateResult {
    const ld = store.learnDialog;
    const step = ld.step;
    if (step === "pick") {
      return html`
        <rune-button variant="secondary" icon="x" @click=${this._onClose}>
          ${msg(str`Cancel`)}
        </rune-button>
        <rune-button
          variant="primary"
          icon="arrow-right"
          ?disabled=${!this._commandKeyDraft.trim() && !ld.commandKey}
          @click=${this._confirmPick}
        >
          ${msg(str`Continue`)}
        </rune-button>
      `;
    }
    if (step === "capture") {
      return html`
        <rune-button variant="ghost" icon="arrow-left" @click=${this._backToPick}>
          ${msg(str`Back`)}
        </rune-button>
        <span class="grow"></span>
        <rune-button variant="secondary" icon="x" @click=${this._onClose}>
          ${msg(str`Cancel`)}
        </rune-button>
        <rune-button variant="primary" icon="antenna" ?loading=${this._busy} @click=${this._start}>
          ${ld.status.kind === "captured" ? msg(str`Re-learn`) : msg(str`Start learn`)}
        </rune-button>
      `;
    }
    // review
    const canSave = ld.captured !== null && !this._saving;
    return html`
      <rune-button variant="ghost" icon="arrow-left" @click=${this._recapture}>
        ${msg(str`Re-capture`)}
      </rune-button>
      <span class="grow"></span>
      <rune-button variant="secondary" icon="x" @click=${this._onClose}>
        ${msg(str`Cancel`)}
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
    `;
  }

  protected willUpdate(): void {
    const ld = store.learnDialog;
    if (!ld.open) {
      // Reset local drafts every time the dialog hides so reopening
      // starts from a clean slate (and the new command key input
      // doesn't carry leftover text from a previous session).
      if (this._commandKeyDraft || this._commandLabelDraft || this._pickError) {
        this._commandKeyDraft = "";
        this._commandLabelDraft = "";
        this._pickError = "";
      }
      return;
    }
    if (ld.step === "pick") {
      if (ld.commandKey && !this._commandKeyDraft) {
        this._commandKeyDraft = ld.commandKey;
      }
      if (ld.commandLabel && !this._commandLabelDraft) {
        this._commandLabelDraft = ld.commandLabel;
      }
    }
  }

  render() {
    const ld = store.learnDialog;
    const deviceName = store.devices.find((d) => d.id === ld.deviceId)?.name ?? "—";
    const subtitleText = msg(
      str`Teach RUNE a new IR or RF command by capturing the raw signal from your remote.`,
    );
    return html`
      <rune-dialog ?open=${ld.open} size="large" .label=${msg(str`Learn command`)}>
        <div
          slot="subtitle"
          style="display:block;font-family:var(--rune-font);font-size:var(--rune-fs-sm);color:var(--rune-text-muted);line-height:var(--rune-lh-normal);margin-bottom:var(--rune-space-3)"
        >
          ${subtitleText}
        </div>
        <rune-stepper slot="stepper" .steps=${this._stepDefs} current=${ld.step}></rune-stepper>
        ${this._renderStep(deviceName)}
        <div slot="footer">${this._renderFooter()}</div>
      </rune-dialog>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-learn-dialog": RuneLearnDialog;
  }
}
