import { css, html, LitElement, nothing } from "lit";
import { customElement, property } from "lit/decorators.js";

import "@shoelace-style/shoelace/dist/components/input/input.js";
import "@shoelace-style/shoelace/dist/components/icon/icon.js";

import { sharedStyles } from "@/styles/shared.js";

import { tablerClass } from "./icon.js";

export type RuneInputSize = "small" | "medium";

@customElement("rune-input")
export class RuneInput extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
        margin-bottom: var(--rune-space-2);
      }
      sl-input::part(base) {
        border-radius: var(--rune-radius-sm);
        font-family: var(--rune-font);
        transition:
          box-shadow var(--rune-dur-fast) var(--rune-ease),
          border-color var(--rune-dur-fast) var(--rune-ease);
      }
      sl-input::part(base):hover:not([disabled]) {
        border-color: var(--rune-border-strong);
      }
      sl-input::part(base):focus-within {
        box-shadow: var(--rune-focus-ring);
        border-color: var(--rune-primary);
      }
      sl-input::part(form-control-label) {
        font-size: 10px;
        font-weight: var(--rune-fw-semibold);
        color: var(--rune-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 2px;
      }
      sl-input::part(help-text) {
        font-size: 11px;
        color: var(--rune-text-muted);
        margin-top: 2px;
      }
      .leading {
        color: var(--rune-text-subtle);
        font-size: 1.05em;
      }
    `,
  ];

  @property() label: string | unknown = "";
  @property() placeholder: string | unknown = "";
  @property({ type: String }) value = "";
  @property({ type: String }) type:
    "text" | "search" | "email" | "url" | "tel" | "password" | "number" = "text";
  @property({ type: String }) name = "";
  @property() helper: string | unknown = "";
  @property({ type: String }) error = "";
  @property({ type: String }) icon = "";
  @property({ type: String }) size: RuneInputSize = "medium";
  @property({ type: Boolean }) required = false;
  @property({ type: Boolean }) disabled = false;
  @property({ type: Boolean }) clearable = false;
  @property({ type: String }) autocomplete: string | null = null;
  @property({ type: String }) inputmode:
    "text" | "search" | "email" | "url" | "tel" | "numeric" | "decimal" | null = null;
  @property({ type: Number }) maxlength: number | null = null;
  @property({ type: Number }) min: number | null = null;
  @property({ type: Number }) max: number | null = null;
  @property({ type: Number }) step: number | null = null;

  private _onInput = (ev: Event): void => {
    const target = ev.target as HTMLInputElement & { value: string };
    this.value = target.value;
    this.dispatchEvent(
      new CustomEvent("rune-input", {
        detail: { value: this.value, name: this.name },
        bubbles: true,
        composed: true,
      }),
    );
  };

  protected render() {
    const labelStr = typeof this.label === "string" ? this.label : "";
    const placeholderStr = typeof this.placeholder === "string" ? this.placeholder : "";
    const helperStr =
      typeof this.helper === "string" && this.helper ? this.helper : this.error || "";
    return html`
      <sl-input
        size=${this.size}
        ?disabled=${this.disabled}
        ?required=${this.required}
        ?clearable=${this.clearable}
        label=${labelStr || nothing}
        placeholder=${placeholderStr || nothing}
        value=${this.value}
        type=${this.type}
        name=${this.name || nothing}
        help-text=${helperStr || nothing}
        autocomplete=${this.autocomplete ?? nothing}
        inputmode=${this.inputmode ?? nothing}
        maxlength=${this.maxlength ?? nothing}
        min=${this.min ?? nothing}
        max=${this.max ?? nothing}
        step=${this.step ?? nothing}
        @sl-input=${this._onInput}
      >
        ${
          this.label && typeof this.label !== "string"
            ? html`<span slot="label">${this.label}</span>`
            : null
        }
        ${
          this.placeholder && typeof this.placeholder !== "string"
            ? html`<span slot="placeholder">${this.placeholder}</span>`
            : null
        }
        ${
          (this.helper && typeof this.helper !== "string") || this.error
            ? html`<span slot="help-text">${this.helper || this.error}</span>`
            : null
        }
        ${
          this.icon
            ? html`<i slot="prefix" class="ti ${tablerClass(this.icon)} leading"></i>`
            : nothing
        }
        <slot name="suffix" slot="suffix"></slot>
      </sl-input>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-input": RuneInput;
  }
}
