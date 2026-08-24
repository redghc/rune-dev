import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import "@/components/ui/index.js";

import { api } from "@/api/bridge.js";
import { reportError } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

import type { PulseCommand } from "@/types.js";

/**
 * Edit a single learned command in place.
 *
 * Used by the device-card context menu for two distinct flows:
 *
 * - **Rename / re-categorise** — the user wants to change ``label`` or
 *   ``category`` without re-capturing. The raw-timings textarea is
 *   pre-filled with the current value and is opt-in: leave it alone
 *   to keep the existing payload, edit it inline to tweak a couple
 *   of microseconds.
 * - **Re-learn from this dialog** — same as the existing Learn flow
 *   but the form is pre-populated. A future enhancement can launch
 *   the capture orchestrator from here; for now, opening the
 *   existing Learn dialog pre-filled with the same key achieves
 *   the same outcome and reuses the same capture UX.
 *
 * ``Save`` patches via ``rune/command/update``. ``Delete`` (footer
 * secondary action) calls ``rune/command/delete`` and confirms first.
 */
@customElement("rune-command-edit-dialog")
@localized()
export class RuneCommandEditDialog extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: contents;
      }
      .field {
        display: flex;
        flex-direction: column;
        gap: 4px;
        margin-bottom: var(--rune-space-3);
      }
      .field label {
        font-family: var(--rune-font);
        font-size: var(--rune-fs-xs);
        font-weight: var(--rune-fw-medium);
        color: var(--rune-text-muted);
        letter-spacing: 0.02em;
        text-transform: uppercase;
      }
      .field .hint {
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-muted);
        line-height: var(--rune-lh-normal);
      }
      sl-textarea {
        --sl-input-border-radius-medium: var(--rune-radius-sm);
      }
      sl-textarea::part(textarea) {
        font-family: var(--rune-font-mono);
        font-size: var(--rune-fs-xs);
        line-height: var(--rune-lh-tight);
        min-height: 96px;
      }
    `,
  ];

  @property({ attribute: false }) command: PulseCommand | null = null;
  @property({ type: Boolean }) open = false;
  @property({ type: String }) deviceId = "";

  @state() private _label = "";
  @state() private _category = "";
  @state() private _rawTimings = "";
  @state() private _carrierHz: number | null = null;
  @state() private _repeatCount: number | null = null;
  @state() private _sendCount: number | null = null;
  @state() private _saving = false;
  @state() private _confirmingDelete = false;
  @state() private _errorMsg = "";

  willUpdate(changed: Map<string, unknown>) {
    if (changed.has("command")) {
      // Sync the dialog's internal ``open`` flag with the parent.
      // Without this Lit's reactivity doesn't re-trigger the inner
      // ``<sl-dialog>`` when the parent re-toggles ``?open`` from
      // false back to true — the element instance is reused, the
      // ``open`` property stays at its last value, and the modal
      // never reappears.
      this.open = this.command !== null;
      if (this.command) {
        // Pre-populate the form from the current PulseCommand. We
        // intentionally copy the timings as a JSON array so the user
        // can paste-edit one value without losing the others.
        this._label = this.command.label ?? this.command.key ?? "";
        this._category = this.command.category ?? "custom";
        this._rawTimings = JSON.stringify(this.command.payload?.raw_timings ?? []);
        const signal = (this.command.signal_category ?? {}) as Record<string, unknown>;
        this._carrierHz =
          typeof signal.carrier_frequency_hz === "number" ? signal.carrier_frequency_hz : null;
        const payload = (this.command.payload ?? {}) as Record<string, unknown>;
        this._repeatCount = typeof payload.repeat_count === "number" ? payload.repeat_count : null;
        this._sendCount = typeof payload.send_count === "number" ? payload.send_count : null;
        this._confirmingDelete = false;
        this._errorMsg = "";
      }
    }
  }

  private _close = (): void => {
    this.open = false;
    this._confirmingDelete = false;
    this._errorMsg = "";
    this.dispatchEvent(new CustomEvent("close", { bubbles: true, composed: true }));
  };

  private async _save(): Promise<void> {
    if (!this.command || !this.deviceId) return;
    this._saving = true;
    this._errorMsg = "";
    try {
      // Build the patch — only include fields that the user actually
      // changed. The backend treats each field independently so an
      // unedited label survives untouched, the unchanged payload
      // sticks around, etc. Empty label is rejected client-side.
      const patch: Record<string, unknown> = {};
      const cmd = this.command;
      const newLabel = this._label.trim();
      if (!newLabel) {
        this._errorMsg = msg(str`Label is required.`);
        return;
      }
      if (newLabel !== cmd.label) patch.label = newLabel;
      if (this._category && this._category !== cmd.category) patch.category = this._category;

      // Raw-timings edit: parse + coerce to a list of int. Empty
      // input or invalid JSON means the user cleared the field; bail
      // with a friendly error rather than wiping the payload.
      const trimmedTimings = this._rawTimings.trim();
      if (trimmedTimings) {
        let parsed: unknown;
        try {
          parsed = JSON.parse(trimmedTimings);
        } catch (err) {
          this._errorMsg = msg(
            str`Raw timings must be a JSON array of integers: ${(err as Error).message}`,
          );
          return;
        }
        if (!Array.isArray(parsed) || !parsed.every((n) => typeof n === "number")) {
          this._errorMsg = msg(str`Raw timings must be a JSON array of integers.`);
          return;
        }
        if (JSON.stringify(parsed) !== JSON.stringify(cmd.payload?.raw_timings ?? [])) {
          patch.raw_timings = parsed;
        }
      }

      if (this._carrierHz != null) patch.carrier_frequency_hz = this._carrierHz;
      if (this._repeatCount != null) patch.repeat_count = this._repeatCount;
      if (this._sendCount != null) patch.send_count = this._sendCount;

      if (Object.keys(patch).length === 0) {
        this._close();
        return;
      }

      await api.updateCommand(this.deviceId, cmd.key, patch);
      this.dispatchEvent(new CustomEvent("saved", { bubbles: true, composed: true }));
      this._close();
    } catch (err) {
      reportError(err);
    } finally {
      this._saving = false;
    }
  }

  private async _delete(): Promise<void> {
    if (!this.command || !this.deviceId) return;
    try {
      await api.deleteCommand(this.deviceId, this.command.key);
      this.dispatchEvent(new CustomEvent("deleted", { bubbles: true, composed: true }));
      this._close();
    } catch (err) {
      reportError(err);
    }
  }

  private _onDialogHide = (ev: CustomEvent): void => {
    if ((ev.detail as { source?: string } | undefined)?.source !== "overlay") return;
    this._close();
  };

  protected render() {
    const cmd = this.command;
    return html`
      <sl-dialog
        ?open=${this.open}
        label=${cmd ? msg(str`Edit "${cmd.label ?? cmd.key}"`) : ""}
        @sl-after-hide=${this._onDialogHide}
      >
        ${
          cmd
            ? html`
                <div class="field">
                  <label>${msg(str`Label`)}</label>
                  <sl-input
                    value=${this._label}
                    @sl-input=${(e: Event) => (this._label = (e.target as HTMLInputElement).value)}
                  ></sl-input>
                </div>
                <div class="field">
                  <label>${msg(str`Category`)}</label>
                  <sl-input
                    value=${this._category}
                    @sl-input=${(e: Event) =>
                      (this._category = (e.target as HTMLInputElement).value)}
                  ></sl-input>
                  <div class="hint">
                    ${msg(
                      str`Semantic role (power, speed_preset, volume, …). Used by entity platforms to expose the right controls.`,
                    )}
                  </div>
                </div>
                <div class="field">
                  <label>${msg(str`Raw timings (µs, alternating signs)`)}</label>
                  <sl-textarea
                    .value=${this._rawTimings}
                    rows="6"
                    @sl-input=${(e: Event) =>
                      (this._rawTimings = (e.target as HTMLTextAreaElement).value)}
                  ></sl-textarea>
                  <div class="hint">
                    ${msg(
                      str`JSON array. Marks positive, spaces negative. Edit a value to tweak a mis-captured microsecond.`,
                    )}
                  </div>
                </div>
                ${
                  this._errorMsg
                    ? html`<div
                        style="color:var(--rune-danger);font-size:var(--rune-fs-sm);margin-bottom:var(--rune-space-2)"
                      >
                        ${this._errorMsg}
                      </div>`
                    : null
                }
                <div
                  slot="footer"
                  style="display:flex;gap:var(--rune-space-2);justify-content:space-between;align-items:center;width:100%"
                >
                  ${
                    this._confirmingDelete
                      ? html`
                          <span
                            style="color:var(--rune-danger);font-size:var(--rune-fs-sm);margin-right:auto"
                          >
                            ${msg(str`Delete this command? This cannot be undone.`)}
                          </span>
                          <rune-button
                            variant="ghost"
                            @click=${() => (this._confirmingDelete = false)}
                          >
                            ${msg(str`Cancel`)}
                          </rune-button>
                          <rune-button variant="danger" icon="trash" @click=${this._delete}>
                            ${msg(str`Confirm delete`)}
                          </rune-button>
                        `
                      : html`
                          <rune-button
                            variant="danger"
                            icon="trash"
                            @click=${() => (this._confirmingDelete = true)}
                          >
                            ${msg(str`Delete`)}
                          </rune-button>
                          <div style="display:flex;gap:var(--rune-space-2);margin-left:auto">
                            <rune-button variant="secondary" @click=${this._close}>
                              ${msg(str`Cancel`)}
                            </rune-button>
                            <rune-button
                              variant="primary"
                              icon="check"
                              ?loading=${this._saving}
                              @click=${this._save}
                            >
                              ${msg(str`Save`)}
                            </rune-button>
                          </div>
                        `
                  }
                </div>
              `
            : null
        }
      </sl-dialog>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-command-edit-dialog": RuneCommandEditDialog;
  }
}
