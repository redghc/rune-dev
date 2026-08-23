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

  @property() label: string | unknown = "";
  @property({ type: Boolean, reflect: true }) open = false;
  @property({ type: String }) size: RuneDialogSize = "medium";
  @property({ type: Boolean }) noHeader = false;
  @property({ type: Boolean }) closable = true;

  private _overlayClickSwallowed = false;

  private _findOpenSelect(root: ParentNode): HTMLElement | null {
    const direct = root.querySelector("sl-select[open], sl-dropdown[open]");
    if (direct) {
      return direct as HTMLElement;
    }
    for (const el of Array.from(root.querySelectorAll("*"))) {
      const sr = (el as HTMLElement).shadowRoot;
      if (sr) {
        const found = this._findOpenSelect(sr);
        if (found) {
          return found;
        }
      }
    }
    return null;
  }

  private _onDocMouseDown = (_ev: MouseEvent): void => {
    this._overlayClickSwallowed = false;
    if (!this.open) {
      return;
    }
    // Capture phase: runs before Shoelace's own document mousedown/mouseup
    // handlers hide the open ``<sl-select>`` / ``<sl-dropdown>``.
    // If a select/dropdown was open when mousedown fired, this interaction
    // belongs to the select (either picking an option or dismissing it).
    // When the option/popup hides on mouseup, the trailing click event
    // can land on the underlying dialog overlay backdrop. We must swallow
    // that overlay close request.
    const openSelect = this._findOpenSelect(this);
    if (openSelect) {
      this._overlayClickSwallowed = true;
    }
  };

  private _onRequestClose = (ev: CustomEvent): void => {
    const source = (ev.detail as { source?: string } | undefined)?.source;
    if (source === "overlay" && this._overlayClickSwallowed) {
      this._overlayClickSwallowed = false;
      ev.preventDefault();
    }
  };

  connectedCallback(): void {
    super.connectedCallback();
    document.addEventListener("mousedown", this._onDocMouseDown, true);
  }

  disconnectedCallback(): void {
    document.removeEventListener("mousedown", this._onDocMouseDown, true);
    super.disconnectedCallback();
  }

  protected render() {
    return html`
      <sl-dialog
        label=${typeof this.label === "string" ? this.label : ""}
        ?open=${this.open}
        size=${this.size}
        ?no-header=${this.noHeader}
        ?closable=${this.closable}
        @sl-request-close=${this._onRequestClose}
      >
        ${
          this.label && typeof this.label !== "string"
            ? html`<span slot="label">${this.label}</span>`
            : null
        }
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
