import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import {
  getLocalePref,
  onLocalePrefChange,
  setLocalePref,
  SUPPORTED_LOCALES,
} from "@/state/locale-pref.js";
import { sharedStyles } from "@/styles/shared.js";

import type { LocalePref } from "@/state/locale-pref.js";

interface Option {
  value: LocalePref;
  /** Short label rendered inside the button (e.g. "EN"). */
  short: string;
  /** Tooltip / aria-label. Localized via msg() so it tracks the
   *  current locale (the UI for picking the UI language should always
   *  be readable in the language being picked). */
  aria: unknown;
  icon: string;
}

const OPTIONS: Option[] = [
  {
    value: "auto",
    short: "AUTO",
    aria: msg(str`Follow Home Assistant locale`),
    icon: "language",
  },
  { value: "en", short: "EN", aria: msg(str`English`), icon: "letter-english" },
  { value: "es", short: "ES", aria: msg(str`Español`), icon: "letter-spanish" },
];

@customElement("rune-locale-toggle")
@localized()
export class RuneLocaleToggle extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: inline-block;
      }
      .seg {
        display: inline-flex;
        gap: 0;
        padding: 2px;
        background: var(--rune-surface-alt);
        border: 1px solid var(--rune-border);
        border-radius: var(--rune-radius-md);
      }
      .opt {
        appearance: none;
        background: transparent;
        border: 0;
        color: var(--rune-text-muted);
        font: inherit;
        font-size: var(--rune-fs-xs);
        font-weight: var(--rune-fw-medium);
        padding: 4px 6px;
        border-radius: var(--rune-radius-sm);
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        letter-spacing: 0.04em;
        transition:
          background-color var(--rune-dur-fast) var(--rune-ease),
          color var(--rune-dur-fast) var(--rune-ease);
      }
      .opt:hover {
        color: var(--rune-text);
      }
      .opt.active {
        background: var(--rune-surface);
        color: var(--rune-text-strong);
        box-shadow: var(--rune-shadow-1);
      }
      .opt i {
        font-size: 13px;
        line-height: 1;
      }
      .compact .opt {
        padding: 4px;
      }
    `,
  ];

  @property({ type: Boolean }) compact = false;

  @state() private _value: LocalePref = getLocalePref();
  private _unsub: (() => void) | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    this._unsub = onLocalePrefChange((p) => {
      this._value = p;
    });
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsub?.();
  }

  protected render() {
    return html`
      <div class="seg ${this.compact ? "compact" : ""}" role="radiogroup" aria-label="Language">
        ${OPTIONS.map(
          (o) => html`
            <button
              class="opt ${this._value === o.value ? "active" : ""}"
              role="radio"
              aria-checked=${this._value === o.value ? "true" : "false"}
              aria-label=${typeof o.aria === "string" ? o.aria : ""}
              title=${typeof o.aria === "string" ? o.aria : ""}
              @click=${() => setLocalePref(o.value)}
            >
              <i class="ti ti-${o.icon}" aria-hidden="true"></i>
              <span>${o.short}</span>
            </button>
          `,
        )}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-locale-toggle": RuneLocaleToggle;
  }
}

/** Re-export so the i18n bootstrap can validate user-typed locales
 *  against the same allow-list. */
export { SUPPORTED_LOCALES };
