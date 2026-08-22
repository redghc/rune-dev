import { css, html, LitElement } from "lit";
import { customElement, property } from "lit/decorators.js";

import "@shoelace-style/shoelace/dist/components/dialog/dialog.js";

import { sharedStyles } from "@/styles/shared.js";

export type RuneDialogSize = "small" | "medium" | "large";

@customElement("rune-dialog")
export class RuneDialog extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: contents;
      }
      sl-dialog {
        --width: 480px;
      }
      sl-dialog[size="small"] {
        --width: 360px;
      }
      sl-dialog[size="large"] {
        --width: 720px;
      }
      sl-dialog::part(panel) {
        background: var(--rune-surface);
        border: 1px solid var(--rune-border);
        border-radius: var(--rune-radius-lg);
        box-shadow: var(--rune-shadow-4);
        color: var(--rune-text);
      }
      sl-dialog::part(title) {
        font-family: var(--rune-font);
        font-size: var(--rune-fs-lg);
        font-weight: var(--rune-fw-semibold);
        color: var(--rune-text-strong);
        letter-spacing: -0.01em;
      }
      sl-dialog::part(close-button) {
        color: var(--rune-text-muted);
      }
      sl-dialog::part(close-button):hover {
        color: var(--rune-text);
      }
      sl-dialog::part(body) {
        font-family: var(--rune-font);
        font-size: var(--rune-fs-sm);
        color: var(--rune-text);
        padding-top: var(--rune-space-2);
      }
      sl-dialog::part(footer) {
        gap: var(--rune-space-2);
        padding-top: var(--rune-space-4);
      }
      sl-dialog::part(overlay) {
        backdrop-filter: blur(6px) saturate(140%);
        -webkit-backdrop-filter: blur(6px) saturate(140%);
        background: rgb(0 0 0 / 0.35);
      }
    `,
  ];

  @property({ type: String }) label = "";
  @property({ type: Boolean, reflect: true }) open = false;
  @property({ type: String }) size: RuneDialogSize = "medium";
  @property({ type: Boolean }) noHeader = false;
  @property({ type: Boolean }) closable = true;

  protected render() {
    return html`
      <sl-dialog
        label=${this.label || ""}
        ?open=${this.open}
        size=${this.size}
        ?no-header=${this.noHeader}
        ?closable=${this.closable}
      >
        <slot></slot>
        <slot name="footer" slot="footer"></slot>
      </sl-dialog>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-dialog": RuneDialog;
  }
}
