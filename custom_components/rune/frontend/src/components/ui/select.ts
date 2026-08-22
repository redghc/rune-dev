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
  label: string;
  description?: string;
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
        margin-bottom: var(--rune-space-3);
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
        font-size: var(--rune-fs-xs);
        font-weight: var(--rune-fw-medium);
        color: var(--rune-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: var(--rune-space-1);
      }
      sl-select::part(help-text) {
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-muted);
        margin-top: var(--rune-space-1);
      }
      sl-option::part(base):hover {
        background: var(--rune-primary-soft);
      }
      .row {
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
      }
      .row i {
        color: var(--rune-text-subtle);
        font-size: 1.05em;
      }
      .opt-label {
        display: flex;
        flex-direction: column;
      }
      .opt-desc {
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-muted);
      }
      .spinner {
        color: var(--rune-text-subtle);
      }
    `,
  ];

  @property({ type: String }) label = "";
  @property({ type: String }) placeholder = "Select…";
  @property({ type: String }) value = "";
  @property({ type: String }) name = "";
  @property({ type: String }) helper = "";
  @property({ type: String }) error = "";
  @property({ type: String }) icon = "";
  @property({ type: String }) size: RuneSelectSize = "medium";
  @property({ type: Boolean }) disabled = false;
  @property({ type: Boolean }) required = false;
  @property({ type: Boolean }) clearable = false;
  @property({ type: Boolean }) searchable = false;
  @property({ type: Boolean }) multiple = false;
  @property({ type: Object }) options: RuneSelectOption[] = [];
  @property({ attribute: false }) loadOptions: AsyncLoader | null = null;
  @property({ type: String }) emptyText = "No options";

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
    return html`
      <sl-option value=${o.value} ?disabled=${o.disabled ?? false}>
        <div class="row">
          ${o.icon ? html`<i class="ti ${tablerClass(o.icon).replace("ti ", "")}"></i>` : nothing}
          <div class="opt-label">
            <span>${o.label}</span>
            ${o.description ? html`<span class="opt-desc">${o.description}</span>` : nothing}
          </div>
        </div>
      </sl-option>
    `;
  }

  protected render() {
    return html`
      <sl-select
        size=${this.size}
        ?disabled=${this.disabled}
        ?required=${this.required}
        ?clearable=${this.clearable}
        ?multiple=${this.multiple}
        ?hoisted=${true}
        label=${this.label || nothing}
        placeholder=${this.placeholder || nothing}
        value=${this.value || nothing}
        name=${this.name || nothing}
        help-text=${this.helper || this.error || nothing}
        ?loading=${this._loading}
        empty=${this.emptyText}
        @sl-change=${this._onChange}
      >
        ${
          this.icon
            ? html`<i
                slot="prefix"
                class="ti ${tablerClass(this.icon).replace("ti ", "")}"
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
