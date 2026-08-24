import { css, html, LitElement, nothing } from "lit";
import { customElement, property, query, state } from "lit/decorators.js";

import type { PropertyValues } from "lit";

import "@shoelace-style/shoelace/dist/components/select/select.js";
import "@shoelace-style/shoelace/dist/components/option/option.js";
import "@shoelace-style/shoelace/dist/components/spinner/spinner.js";

import { sharedStyles } from "@/styles/shared.js";

import { tablerClass } from "./icon.js";

export interface RuneSelectOption {
  value: string;
  label: string | (() => unknown);
  /** Sub-line rendered under the label in both the dropdown and the
   *  closed combobox (e.g. ``Living Room › RM4 pro``). */
  description?: string | (() => unknown);
  /** Right-aligned tag rendered at the end of the dropdown row only
   *  (e.g. ``Radio Frequency``). Use a getter so it stays reactive
   *  to locale. */
  meta?: string | (() => unknown);
  icon?: string;
  /** Third line rendered in the dropdown row only (e.g. entity_id). */
  id?: string | (() => unknown);
  disabled?: boolean;
}

export type AsyncLoader = () => Promise<RuneSelectOption[]>;

export type RuneSelectSize = "small" | "medium";

/** Subset of ``<sl-select>``'s imperative surface that we poke. */
interface SlSelectHandle extends HTMLElement {
  show: () => Promise<void>;
  hide: () => Promise<void>;
  open: boolean;
}

@customElement("rune-select")
export class RuneSelect extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
      }
      .wrapper {
        position: relative;
        display: block;
      }
      .lbl {
        font-size: 10px;
        font-weight: var(--rune-fw-semibold);
        color: var(--rune-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 2px;
      }
      .lbl .req {
        color: var(--rune-danger);
        margin-left: 2px;
      }
      .combo {
        position: relative;
        min-height: 42px;
      }
      /* The underlying sl-select contributes the dropdown popup. We
         strip every visual part and disable pointer events on the host
         so our custom display catches clicks instead; the listbox +
         options re-enable pointer-events on themselves so the popup
         stays interactive. No z-index on the host so the popup's own
         stacking context escapes to the document level. */
      sl-select.underlying {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
      }
      sl-select.underlying::part(combobox) {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        min-height: 0 !important;
        height: 100%;
        cursor: pointer;
        color: transparent !important;
      }
      sl-select.underlying::part(display-input),
      sl-select.underlying::part(display-label),
      sl-select.underlying::part(prefix),
      sl-select.underlying::part(suffix),
      sl-select.underlying::part(expand-icon),
      sl-select.underlying::part(clear-button),
      sl-select.underlying::part(checked-icon),
      sl-select.underlying::part(form-control-label),
      sl-select.underlying::part(help-text) {
        display: none !important;
      }
      /* ---- Custom rich display (closed state) ----
         On top of the sl-select so it gets the visual treatment (icon,
         name, sub-line, chevron). Catches clicks to open the popup via
         the imperative slSelect.show() call. The clear button has its
         own pointer-events re-enabled so it stays clickable. */
      .display {
        position: absolute;
        inset: 0;
        z-index: 1;
        display: flex;
        align-items: center;
        gap: var(--rune-space-3);
        min-height: 42px;
        padding: 6px 12px;
        border: 1px solid var(--rune-border);
        border-radius: var(--rune-radius-sm);
        background: var(--rune-surface);
        color: var(--rune-text);
        font-family: var(--rune-font);
        cursor: pointer;
        transition:
          border-color var(--rune-dur-fast) var(--rune-ease),
          box-shadow var(--rune-dur-fast) var(--rune-ease);
      }
      .display:hover:not(.disabled) {
        border-color: var(--rune-border-strong);
      }
      .wrapper.open .display,
      .wrapper:focus-within .display {
        border-color: var(--rune-primary);
        box-shadow: var(--rune-focus-ring);
      }
      .display.disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .display .d-icon {
        color: var(--rune-text-subtle);
        font-size: 1.2em;
        flex-shrink: 0;
      }
      .display .d-info {
        flex: 1 1 auto;
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
      }
      .display .d-title {
        color: var(--rune-text);
        font-size: var(--rune-fs-sm);
        font-weight: var(--rune-fw-medium);
        line-height: 1.25;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .display .d-desc {
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-muted);
        line-height: 1.2;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .display.placeholder .d-ph {
        color: var(--rune-text-subtle);
        font-size: var(--rune-fs-sm);
      }
      .display .d-chev {
        color: var(--rune-text-subtle);
        font-size: 1em;
        flex-shrink: 0;
        transition: transform var(--rune-dur-fast) var(--rune-ease);
      }
      .wrapper.open .display .d-chev {
        transform: rotate(180deg);
      }
      .display .d-clear {
        flex-shrink: 0;
        background: transparent;
        border: none;
        cursor: pointer;
        color: var(--rune-text-subtle);
        padding: 4px;
        border-radius: var(--rune-radius-sm);
        display: flex;
        align-items: center;
        pointer-events: auto;
      }
      .display .d-clear:hover {
        color: var(--rune-text);
        background: var(--rune-surface-alt);
      }
      /* ---- Dropdown styling ---- */
      sl-select.underlying::part(listbox) {
        background: var(--rune-surface);
        border: 1px solid var(--rune-border);
        border-radius: var(--rune-radius-md);
        box-shadow: var(--rune-shadow-3);
        padding: var(--rune-space-1);
        z-index: 9999;
        pointer-events: auto;
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
      .opt-row {
        display: flex;
        align-items: center;
        gap: var(--rune-space-3);
        width: 100%;
      }
      .opt-row .o-icon {
        color: var(--rune-text-subtle);
        font-size: 1.15em;
        flex-shrink: 0;
        transition: color var(--rune-dur-fast) var(--rune-ease);
      }
      .opt-row .o-label {
        flex: 1 1 auto;
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
      }
      .opt-row .o-title {
        color: var(--rune-text);
        font-size: var(--rune-fs-sm);
        font-weight: var(--rune-fw-medium);
        line-height: 1.25;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .opt-row .o-desc {
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-muted);
        line-height: 1.2;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .opt-row .o-id {
        font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
        font-size: 11px;
        color: var(--rune-text-subtle);
        line-height: 1.2;
        opacity: 0.85;
        word-break: break-all;
      }
      .opt-row .o-meta {
        flex-shrink: 0;
        padding: 2px 10px;
        font-size: var(--rune-fs-xs);
        font-weight: var(--rune-fw-medium);
        line-height: 1.4;
        color: var(--rune-text-muted);
        background: var(--rune-surface-alt);
        border: 1px solid var(--rune-border);
        border-radius: var(--rune-radius-full);
        white-space: nowrap;
        transition:
          color var(--rune-dur-fast) var(--rune-ease),
          border-color var(--rune-dur-fast) var(--rune-ease),
          background-color var(--rune-dur-fast) var(--rune-ease);
      }
      sl-option:hover .o-icon,
      sl-option:focus-visible .o-icon {
        color: var(--rune-primary);
      }
      sl-option:hover .o-title,
      sl-option:focus-visible .o-title {
        color: var(--rune-text-strong);
      }
      sl-option:hover .o-desc,
      sl-option:focus-visible .o-desc {
        color: var(--rune-primary-text);
      }
      sl-option[aria-selected="true"] .o-title {
        color: var(--rune-primary-text);
        font-weight: var(--rune-fw-semibold);
      }
      sl-option[aria-selected="true"] .o-desc {
        color: var(--rune-primary-hover);
        opacity: 0.95;
      }
      sl-option[aria-selected="true"] .o-meta {
        color: var(--rune-primary-text);
        border-color: var(--rune-primary);
        background: transparent;
      }
      .help {
        font-size: 11px;
        color: var(--rune-text-muted);
        margin-top: 2px;
      }
      .help.err {
        color: var(--rune-danger-text);
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
  @state() private _open = false;

  @query("sl-select.underlying") private _slSelect!: SlSelectHandle;

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

  private _onDisplayClick = (ev: MouseEvent): void => {
    if (this.disabled) return;
    if ((ev.target as HTMLElement).closest(".d-clear")) return;
    if (!this._slSelect) return;
    if (this._slSelect.open) {
      void this._slSelect.hide();
    } else {
      void this._slSelect.show();
    }
  };

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

  private _onShow = (): void => {
    this._open = true;
  };

  private _onAfterHide = (): void => {
    this._open = false;
  };

  private _onClear = (ev: Event): void => {
    ev.stopPropagation();
    this.value = "";
    this.dispatchEvent(
      new CustomEvent("rune-change", {
        detail: { value: "", name: this.name },
        bubbles: true,
        composed: true,
      }),
    );
  };

  private _resolveText(v: string | (() => unknown) | undefined): unknown {
    if (v === undefined) return null;
    return typeof v === "function" ? v() : v;
  }

  private _renderOption(o: RuneSelectOption) {
    const labelNode = this._resolveText(o.label);
    const descNode = o.description ? this._resolveText(o.description) : null;
    const metaNode = o.meta ? this._resolveText(o.meta) : null;
    const idNode = o.id ? this._resolveText(o.id) : null;
    return html`
      <sl-option value=${o.value} ?disabled=${o.disabled ?? false}>
        <div class="opt-row">
          ${o.icon ? html`<i class="ti ${tablerClass(o.icon)} o-icon"></i>` : nothing}
          <div class="o-label">
            <span class="o-title">${labelNode}</span>
            ${descNode ? html`<span class="o-desc">${descNode}</span>` : nothing}
            ${idNode ? html`<span class="o-id">${idNode}</span>` : nothing}
          </div>
          ${metaNode ? html`<span class="o-meta">${metaNode}</span>` : nothing}
        </div>
      </sl-option>
    `;
  }

  private _renderDisplay() {
    const selected = this.options.find((o) => o.value === this.value);
    const isDisabled = this.disabled;
    if (!selected) {
      const ph = typeof this.placeholder === "string" ? this.placeholder : "";
      return html`
        <div
          class=${`display placeholder${isDisabled ? " disabled" : ""}`}
          role="button"
          tabindex=${isDisabled ? -1 : 0}
          @click=${this._onDisplayClick}
        >
          <span class="d-ph">${ph || "Select…"}</span>
          <i class="ti ti-chevron-down d-chev"></i>
        </div>
      `;
    }
    const labelNode = this._resolveText(selected.label);
    const descNode = selected.description ? this._resolveText(selected.description) : null;
    return html`
      <div
        class=${`display has-value${isDisabled ? " disabled" : ""}`}
        role="button"
        tabindex=${isDisabled ? -1 : 0}
        @click=${this._onDisplayClick}
      >
        ${selected.icon ? html`<i class="ti ${tablerClass(selected.icon)} d-icon"></i>` : nothing}
        <div class="d-info">
          <div class="d-title">${labelNode}</div>
          ${descNode ? html`<div class="d-desc">${descNode}</div>` : nothing}
        </div>
        ${
          this.clearable && !isDisabled && this.value
            ? html`
                <button class="d-clear" type="button" aria-label="Clear" @click=${this._onClear}>
                  <i class="ti ti-x"></i>
                </button>
              `
            : nothing
        }
        <i class="ti ti-chevron-down d-chev"></i>
      </div>
    `;
  }

  protected render() {
    const hasLabel = this.label !== undefined && this.label !== null && this.label !== "";
    const hasHelper = this.helper !== undefined && this.helper !== null && this.helper !== "";
    const helperStr =
      typeof this.helper === "string" && this.helper ? this.helper : this.error || "";
    const emptyStr = typeof this.emptyText === "string" ? this.emptyText : "";
    const wrapperClasses = `wrapper${this._open ? " open" : ""}${this.disabled ? " disabled" : ""}`;
    return html`
      <div class=${wrapperClasses}>
        ${hasLabel ? html`<div class="lbl">${this.label}</div>` : nothing}
        <div class="combo">
          <sl-select
            class="underlying"
            size=${this.size}
            ?disabled=${this.disabled}
            ?required=${this.required}
            ?multiple=${this.multiple}
            ?hoist=${true}
            value=${this.value || nothing}
            name=${this.name || nothing}
            empty=${emptyStr}
            ?loading=${this._loading}
            @sl-change=${this._onChange}
            @sl-show=${this._onShow}
            @sl-after-hide=${this._onAfterHide}
          >
            ${this.options.map((o) => this._renderOption(o))}
            ${
              this._loading && this.options.length === 0
                ? html`<sl-spinner class="spinner"></sl-spinner>`
                : nothing
            }
          </sl-select>
          ${this._renderDisplay()}
        </div>
        ${
          hasHelper
            ? html`<div class=${`help${this.error ? " err" : ""}`}>
                ${helperStr || this.helper}
              </div>`
            : nothing
        }
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-select": RuneSelect;
  }
}
