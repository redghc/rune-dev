import { css, html, LitElement } from "lit";
import { customElement, property } from "lit/decorators.js";

import { sharedStyles } from "@/styles/shared.js";

import { tablerClass } from "./icon.js";

@customElement("rune-empty-state")
export class RuneEmptyState extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
      }
      .box {
        text-align: center;
        padding: var(--rune-space-8) var(--rune-space-4);
        background: var(--rune-surface);
        border: 2px dashed var(--rune-border);
        border-radius: var(--rune-radius-lg);
        color: var(--rune-text-muted);
      }
      .icon-wrap {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 72px;
        height: 72px;
        margin: 0 auto var(--rune-space-3);
        border-radius: var(--rune-radius-full);
        background: var(--rune-primary-soft);
        color: var(--rune-primary);
        font-size: 36px;
        line-height: 1;
      }
      h3 {
        margin: 0 0 var(--rune-space-1);
        font-size: var(--rune-fs-lg);
        font-weight: var(--rune-fw-semibold);
        color: var(--rune-text);
        font-family: var(--rune-font);
        letter-spacing: -0.01em;
      }
      p {
        margin: 0 0 var(--rune-space-4);
        font-size: var(--rune-fs-sm);
        line-height: var(--rune-lh-relaxed);
        color: var(--rune-text-muted);
        max-width: 36ch;
        margin-left: auto;
        margin-right: auto;
      }
      .actions {
        display: flex;
        justify-content: center;
        gap: var(--rune-space-2);
      }
    `,
  ];

  @property({ type: String }) icon = "inbox";
  @property() heading: string | unknown = "";
  @property() message: string | unknown = "";
  @property({ type: Boolean }) compact = false;

  protected render() {
    return html`
      <div class="box" role="status">
        <div class="icon-wrap">
          <i class="ti ${tablerClass(this.icon)}"></i>
        </div>
        <h3>${this.heading}</h3>
        ${this.message ? html`<p>${this.message}</p>` : null}
        <div class="actions">
          <slot name="action"></slot>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-empty-state": RuneEmptyState;
  }
}
