import { css, html, LitElement } from "lit";
import { customElement, property } from "lit/decorators.js";

import "@shoelace-style/shoelace/dist/components/tooltip/tooltip.js";

import { sharedStyles } from "@/styles/shared.js";

@customElement("rune-tooltip")
export class RuneTooltip extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: inline-flex;
      }
      sl-tooltip {
        --max-width: 280px;
      }
      sl-tooltip::part(base) {
        background: var(--rune-text-strong);
        color: var(--rune-text-inverse);
        font-family: var(--rune-font);
        font-size: var(--rune-fs-xs);
        font-weight: var(--rune-fw-medium);
        padding: var(--rune-space-1) var(--rune-space-2);
        border-radius: var(--rune-radius-xs);
        box-shadow: var(--rune-shadow-2);
      }
      sl-tooltip::part(arrow)::before {
        border-top-color: var(--rune-text-strong);
      }
    `,
  ];

  @property({ type: String }) content = "";
  @property({ type: String }) placement:
    | "top"
    | "top-start"
    | "top-end"
    | "right"
    | "right-start"
    | "right-end"
    | "bottom"
    | "bottom-start"
    | "bottom-end"
    | "left"
    | "left-start"
    | "left-end" = "top";
  @property({ type: Boolean }) disabled = false;
  @property({ type: Number }) openDelay = 250;
  @property({ type: Number }) closeDelay = 0;

  protected render() {
    return html`
      <sl-tooltip
        content=${this.content}
        placement=${this.placement}
        ?disabled=${this.disabled}
        .openDelay=${this.openDelay}
        .closeDelay=${this.closeDelay}
        hoist
      >
        <slot></slot>
      </sl-tooltip>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-tooltip": RuneTooltip;
  }
}
