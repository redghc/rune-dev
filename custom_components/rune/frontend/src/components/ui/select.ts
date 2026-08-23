import { css, html, LitElement, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import type { PropertyValues } from "lit";

import "@shoelace-style/shoelace/dist/components/select/select.js";
import "@shoelace-style/shoelace/dist/components/option/option.js";
import "@shoelace-style/shoelace/dist/components/spinner/spinner.js";

import { sharedStyles } from "@/styles/shared.js";

import { tablerClass } from "./icon.js";

export interface RuneSelectOption {
  value: string;
  label: string | (() => unknown);
  description?: string | (() => unknown);
  icon?: string;
  disabled?: boolean;
}

export type AsyncLoader = () => Promise<RuneSelectOption[]>;

export type RuneSelectSize = "small" | "medium";

@customElement("rune-select")
export class RuneSelect extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
        margin-bottom: var(--rune-space-2);
      }
      sl-select::part(combobox) {
        border-radius: var(--rune-radius-sm);
        font-family: var(--rune-font);
        transition:
          box-shadow var(--rune-dur-fast) var(--rune-ease),
          border-color var(--rune-dur-fast) var(--rune-ease);
      }
      sl-select::part(combobox):hover:not([disabled]) {
        border-color: var(--rune-border-strong);
      }
      sl-select::part(combobox):focus-within {
        border-color: var(--rune-primary);
        box-shadow: var(--rune-focus-ring);
      }
      sl-select::part(control):hover:not([disabled]) {
        border-color: var(--rune-border-strong);
      }
      sl-select::part(control):focus-within {
        border-color: var(--rune-primary);
        box-shadow: var(--rune-focus-ring);
      }
      sl-select::part(form-control-label) {
        font-size: 10px;
        font-weight: var(--rune-fw-semibold);
        color: var(--rune-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 2px;
      }
      sl-select::part(help-text) {
        font-size: 11px;
        color: var(--rune-text-muted);
        margin-top: 2px;
      }
      sl-select::part(listbox) {
        background: var(--rune-surface);
        border: 1px solid var(--rune-border);
        border-radius: var(--rune-radius-md);
        box-shadow: var(--rune-shadow-3);
        padding: var(--rune-space-1);
      }
      sl-option::part(base) {
        border-radius: var(--rune-radius-sm);
        font-family: var(--rune-font);
        color: var(--rune-text) !important;
        padding: var(--rune-space-2) var(--rune-space-3);
        background-color: transparent !important;
        transition:
          background var(--rune-dur-fast) var(--rune-ease),
          color var(--rune-dur-fast) var(--rune-ease);
      }
      sl-option:hover::part(base),
      sl-option:focus-visible::part(base) {
        background-color: var(--rune-surface-alt) !important;
        color: var(--rune-text-strong) !important;
      }
      sl-option[aria-selected="true"]::part(base) {
        background-color: var(--rune-primary-soft) !important;
        color: var(--rune-primary-text) !important;
      }
      sl-option[aria-selected="true"]:hover::part(base) {
        background-color: var(--rune-primary-soft) !important;
        color: var(--rune-primary-text) !important;
      }
      sl-option::part(checked-icon) {
        color: var(--rune-primary);
      }
      .row {
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
        width: 100%;
      }
      .row i {
        color: var(--rune-text-subtle);
        font-size: 1.1em;
        flex-shrink: 0;
        transition: color var(--rune-dur-fast) var(--rune-ease);
      }
      .opt-label {
        display: flex;
        flex-direction: column;
        gap: 1px;
        min-width: 0;
      }
      .opt-title {
        color: var(--rune-text);
        font-size: var(--rune-fs-sm);
        font-weight: var(--rune-fw-medium);
        line-height: 1.3;
        transition: color var(--rune-dur-fast) var(--rune-ease);
      }
      .opt-desc {
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-muted);
        line-height: 1.2;
        transition: color var(--rune-dur-fast) var(--rune-ease);
      }
      sl-option:hover .opt-title,
      sl-option:focus-visible .opt-title {
        color: var(--rune-text-strong);
      }
      sl-option:hover .opt-desc,
      sl-option:focus-visible .opt-desc {
        color: var(--rune-primary-text);
      }
      sl-option:hover .row i,
      sl-option:focus-visible .row i {
        color: var(--rune-primary);
      }
      sl-option[aria-selected="true"] .opt-title {
        color: var(--rune-primary-text);
        font-weight: var(--rune-fw-semibold);
      }
      sl-option[aria-selected="true"] .opt-desc {
        color: var(--rune-primary-hover);
        opacity: 0.95;
      }
      sl-option[aria-selected="true"] .row i {
        color: var(--rune-primary);
      }
      .spinner {
        color: var(--rune-text-subtle);
      }
    `,
  ];

  @property() label: string | unknown = "";
  @property() placeholder: string | unknown = "Select…";
  @property({ type: String }) value = "";
  @property({ type: String }) name = "";
  @property() helper: string | unknown = "";
  @property({ type: String }) error = "";
  @property({ type: String }) icon = "";
  @property({ type: String }) size: RuneSelectSize = "medium";
  @property({ type: Boolean }) disabled = false;
  @property({ type: Boolean }) required = false;
  @property({ type: Boolean }) clearable = false;
  @property({ type: Boolean }) searchable = false;
  @property({ type: Boolean }) multiple = false;
  @property({ attribute: false }) options: RuneSelectOption[] = [];
  @property({ attribute: false }) loadOptions: AsyncLoader | null = null;
  @property() emptyText: string | unknown = "No options";

  @state() private _loading = false;
  @state() private _asyncLoaded = false;

  protected async firstUpdated(_changed: PropertyValues): Promise<void> {
    void _changed;
    if (this.loadOptions && !this._asyncLoaded) {
      await this._refresh();
    }
  }

  protected async updated(changed: PropertyValues): Promise<void> {
    if (changed.has("loadOptions") && this.loadOptions && !this._asyncLoaded) {
      await this._refresh();
    }
  }

  private async _refresh(): Promise<void> {
    if (!this.loadOptions) return;
    this._loading = true;
    try {
      this.options = await this.loadOptions();
      this._asyncLoaded = true;
      await this.updateComplete;
    } catch (err) {
      this.error = (err as Error).message;
    } finally {
      this._loading = false;
    }
  }

  private _onChange = (ev: Event): void => {
    const target = ev.target as HTMLSelectElement & { value: string | string[] };
    this.value = target.value as string;
    this.dispatchEvent(
      new CustomEvent("rune-change", {
        detail: { value: this.value, name: this.name },
        bubbles: true,
        composed: true,
      }),
    );
  };

  private _renderOption(o: RuneSelectOption) {
    const labelNode = typeof o.label === "function" ? o.label() : o.label;
    const descNode = o.description
      ? typeof o.description === "function"
        ? o.description()
        : o.description
      : null;
    return html`
      <sl-option value=${o.value} ?disabled=${o.disabled ?? false}>
        <div class="row">
          ${o.icon ? html`<i class="ti ${tablerClass(o.icon)}"></i>` : nothing}
          <div class="opt-label">
            <span class="opt-title">${labelNode}</span>
            ${descNode ? html`<span class="opt-desc">${descNode}</span>` : nothing}
          </div>
        </div>
      </sl-option>
    `;
  }

  protected render() {
    const labelStr = typeof this.label === "string" ? this.label : "";
    const placeholderStr = typeof this.placeholder === "string" ? this.placeholder : "";
    const helperStr =
      typeof this.helper === "string" && this.helper ? this.helper : this.error || "";
    const emptyStr = typeof this.emptyText === "string" ? this.emptyText : "";
    return html`
      <sl-select
        size=${this.size}
        ?disabled=${this.disabled}
        ?required=${this.required}
        ?clearable=${this.clearable}
        ?multiple=${this.multiple}
        ?hoist=${true}
        label=${labelStr || nothing}
        placeholder=${placeholderStr || nothing}
        value=${this.value || nothing}
        name=${this.name || nothing}
        help-text=${helperStr || nothing}
        ?loading=${this._loading}
        empty=${emptyStr}
        @sl-change=${this._onChange}
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
            ? html`<i
                slot="prefix"
                class="ti ${tablerClass(this.icon)}"
                style="color:var(--rune-text-subtle);font-size:1.05em"
              ></i>`
            : nothing
        }
        ${this.options.map((o) => this._renderOption(o))}
        ${
          this._loading && this.options.length === 0
            ? html`<sl-spinner class="spinner"></sl-spinner>`
            : nothing
        }
      </sl-select>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-select": RuneSelect;
  }
}
