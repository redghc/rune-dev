import { css, html, LitElement } from "lit";
import { customElement, property } from "lit/decorators.js";

import "@shoelace-style/shoelace/dist/components/tag/tag.js";

import { sharedStyles } from "@/styles/shared.js";

import { tablerClass } from "./icon.js";

export type RuneChipVariant = "neutral" | "primary" | "success" | "warning" | "danger";

@customElement("rune-chip")
export class RuneChip extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: inline-flex;
      }
      sl-tag::part(base) {
        font-family: var(--rune-font);
        font-size: var(--rune-fs-xs);
        font-weight: var(--rune-fw-medium);
        border-radius: var(--rune-radius-full);
        letter-spacing: 0.02em;
        transition: background-color var(--rune-dur-fast) var(--rune-ease);
      }
      .icon {
        font-size: 1em;
        margin-right: var(--rune-space-1);
      }
    `,
  ];

  @property({ type: String }) variant: RuneChipVariant = "neutral";
  @property({ type: String }) icon = "";
  @property({ type: Boolean }) outlined = false;
  @property({ type: Boolean }) pulse = false;
  @property({ type: Boolean }) closable = false;

  private _slVariant(): "neutral" | "primary" | "success" | "warning" | "danger" {
    return this.variant === "neutral" ? "neutral" : this.variant;
  }

  private _onRemove = (ev: Event): void => {
    ev.stopPropagation();
    this.dispatchEvent(new CustomEvent("rune-chip-remove", { bubbles: true, composed: true }));
  };

  protected render() {
    return html`
      <sl-tag
        variant=${this._slVariant()}
        size="small"
        ?pill=${true}
        ?outlined=${this.outlined}
        ?closable=${this.closable}
        @sl-remove=${this._onRemove}
      >
        ${
          this.icon
            ? html`<i
                class="ti ${tablerClass(this.icon).replace("ti ", "")} icon"
                style=${this.pulse ? "animation:rune-pulse 1.6s infinite" : ""}
              ></i>`
            : null
        }
        <slot></slot>
      </sl-tag>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-chip": RuneChip;
  }
}
