// Horizontal step indicator used inside step-by-step dialogs.
//
// Usage:
//
//   <rune-stepper
//     .steps=${[{ key: "pick", label: () => msg(str`Pick`) },
//               { key: "capture", label: () => msg(str`Capture`) },
//               { key: "review", label: () => msg(str`Review`) }]}
//     current="capture"
//   ></rune-stepper>
//
// ``current`` matches the ``key`` of the active step. Earlier steps
// render as completed (filled primary circle), later steps as pending
// (outlined muted circle). The active step pulses with the primary
// color so the eye lands on it immediately when the dialog opens.

import { css, html, LitElement } from "lit";
import { customElement, property } from "lit/decorators.js";

import { sharedStyles } from "@/styles/shared.js";

export interface RuneStepDef {
  key: string;
  label: () => unknown;
  /** Optional tabler icon name. */
  icon?: string;
}

@customElement("rune-stepper")
export class RuneStepper extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
      }
      .row {
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
      }
      .step {
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
        flex-shrink: 0;
      }
      .dot {
        width: 28px;
        height: 28px;
        border-radius: var(--rune-radius-full);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-family: var(--rune-font);
        font-size: var(--rune-fs-xs);
        font-weight: var(--rune-fw-semibold);
        flex-shrink: 0;
        transition:
          background-color var(--rune-dur) var(--rune-ease),
          color var(--rune-dur) var(--rune-ease),
          border-color var(--rune-dur) var(--rune-ease),
          box-shadow var(--rune-dur) var(--rune-ease);
      }
      .dot.pending {
        background: var(--rune-surface-alt);
        color: var(--rune-text-muted);
        border: 1px solid var(--rune-border);
      }
      .dot.active {
        background: var(--rune-primary);
        color: var(--rune-on-primary);
        border: 1px solid var(--rune-primary);
        box-shadow: 0 0 0 4px var(--rune-primary-soft);
      }
      .dot.done {
        background: var(--rune-success);
        color: var(--rune-on-primary);
        border: 1px solid var(--rune-success);
      }
      .dot i {
        font-size: 14px;
        line-height: 1;
      }
      .label {
        font-family: var(--rune-font);
        font-size: var(--rune-fs-xs);
        font-weight: var(--rune-fw-medium);
        color: var(--rune-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        white-space: nowrap;
      }
      .step.active .label,
      .step.done .label {
        color: var(--rune-text-strong);
      }
      .bar {
        flex: 1;
        height: 2px;
        background: var(--rune-border);
        border-radius: var(--rune-radius-full);
        min-width: 16px;
        overflow: hidden;
        position: relative;
      }
      .bar.done::after {
        content: "";
        position: absolute;
        inset: 0;
        background: var(--rune-success);
      }
    `,
  ];

  @property({ attribute: false }) steps: RuneStepDef[] = [];
  @property({ type: String }) current = "";

  protected render() {
    const idx = this.steps.findIndex((s) => s.key === this.current);
    return html`
      <div class="row" role="list" aria-label="Progress">
        ${this.steps.map((s, i) => {
          const state = i < idx ? "done" : i === idx ? "active" : "pending";
          const showBar = i < this.steps.length - 1;
          const barState = i < idx ? "done" : "";
          return html`
            <div
              class="step ${state}"
              role="listitem"
              aria-current=${state === "active" ? "step" : "false"}
            >
              <div class="dot ${state}">
                ${
                  state === "done"
                    ? html`<i class="ti ti-check"></i>`
                    : s.icon
                      ? html`<i class="ti ti-${s.icon}"></i>`
                      : html`${i + 1}`
                }
              </div>
              <span class="label">${s.label()}</span>
            </div>
            ${showBar ? html`<div class="bar ${barState}"></div>` : null}
          `;
        })}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-stepper": RuneStepper;
  }
}
