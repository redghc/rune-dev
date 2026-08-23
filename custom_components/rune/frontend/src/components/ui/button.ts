import { css, html, LitElement, nothing } from "lit";
import { customElement, property } from "lit/decorators.js";

import "@shoelace-style/shoelace/dist/components/button/button.js";
import "@shoelace-style/shoelace/dist/components/spinner/spinner.js";

import { sharedStyles } from "@/styles/shared.js";

import { tablerClass } from "./icon.js";

export type RuneButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "success";
export type RuneButtonSize = "small" | "medium" | "large";

const SL_VARIANT: Record<RuneButtonVariant, string> = {
  primary: "primary",
  secondary: "default",
  ghost: "text",
  danger: "danger",
  success: "success",
};

@customElement("rune-button")
export class RuneButton extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: inline-flex;
      }
      sl-button::part(base) {
        font-family: var(--rune-font);
        font-weight: var(--rune-fw-medium);
        letter-spacing: 0.01em;
        border-radius: var(--rune-radius-sm);
        transition:
          background-color var(--rune-dur-fast) var(--rune-ease),
          box-shadow var(--rune-dur-fast) var(--rune-ease),
          transform var(--rune-dur-fast) var(--rune-ease);
      }
      sl-button::part(base):hover {
        transform: translateY(-1px);
      }
      sl-button::part(base):active {
        transform: translateY(0);
      }
      .icon {
        font-size: 1.1em;
        margin-right: var(--rune-space-1);
        vertical-align: -0.125em;
      }
      .icon-only {
        margin-right: 0;
      }
    `,
  ];

  @property({ type: String }) variant: RuneButtonVariant = "primary";
  @property({ type: String }) size: RuneButtonSize = "medium";
  @property({ type: String }) icon = "";
  @property({ type: String }) iconEnd = "";
  @property({ type: Boolean, reflect: true }) disabled = false;
  @property({ type: Boolean }) loading = false;
  @property({ type: Boolean }) pill = false;
  @property({ type: String }) type: "button" | "submit" | "reset" = "button";

  protected render() {
    const iconHtml = this.icon ? html`<i class="ti ${tablerClass(this.icon)} icon"></i>` : nothing;
    const iconEndHtml = this.iconEnd
      ? html`<i class="ti ${tablerClass(this.iconEnd)} icon" slot="suffix"></i>`
      : nothing;
    return html`
      <sl-button
        variant=${SL_VARIANT[this.variant]}
        size=${this.size}
        ?disabled=${this.disabled || this.loading}
        type=${this.type}
        ?pill=${this.pill}
      >
        ${this.loading ? html`<sl-spinner slot="prefix"></sl-spinner>` : iconHtml}
        <slot></slot>
        ${iconEndHtml}
      </sl-button>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-button": RuneButton;
  }
}
