import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import { getTheme, onThemeChange, setTheme } from "@/state/theme.js";
import { sharedStyles } from "@/styles/shared.js";

import type { RuneTheme } from "@/state/theme.js";

interface Option {
  value: RuneTheme;
  icon: string;
}

const OPTIONS: Option[] = [
  { value: "auto", icon: "sun-moon" },
  { value: "light", icon: "sun" },
  { value: "dark", icon: "moon" },
];

// Title attribute is a native HTML attribute (string only) so we keep
// an English fallback. Localizers will see the visible labels above
// via msg(); the title is a minor mouse-hover hint.
const TITLE_LABELS: Record<RuneTheme, string> = {
  auto: "Auto",
  light: "Light",
  dark: "Dark",
};

function optionLabel(v: RuneTheme) {
  switch (v) {
    case "auto":
      return msg(str`Auto`);
    case "light":
      return msg(str`Light`);
    case "dark":
      return msg(str`Dark`);
  }
}

@customElement("rune-theme-toggle")
@localized()
export class RuneThemeToggle extends LitElement {
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
        padding: 4px 8px;
        border-radius: var(--rune-radius-sm);
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 4px;
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
      .compact .opt span {
        display: none;
      }
    `,
  ];

  @property({ type: Boolean }) compact = false;

  @state() private _value: RuneTheme = getTheme();
  private _unsub: (() => void) | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    this._unsub = onThemeChange((t) => {
      this._value = t;
    });
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsub?.();
  }

  private _pick(t: RuneTheme): void {
    setTheme(t);
  }

  protected render() {
    return html`
      <div class="seg ${this.compact ? "compact" : ""}" role="radiogroup" aria-label="Color scheme">
        ${OPTIONS.map(
          (o) => html`
            <button
              class="opt ${this._value === o.value ? "active" : ""}"
              role="radio"
              aria-checked=${this._value === o.value ? "true" : "false"}
              title=${TITLE_LABELS[o.value]}
              @click=${() => this._pick(o.value)}
            >
              <i class="ti ti-${o.icon}" aria-hidden="true"></i>
              <span>${optionLabel(o.value)}</span>
            </button>
          `,
        )}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-theme-toggle": RuneThemeToggle;
  }
}
