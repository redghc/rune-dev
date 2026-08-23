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

const OPTION_LABEL: Record<RuneTheme, () => ReturnType<typeof msg>> = {
  auto: () => msg(str`Auto`),
  light: () => msg(str`Light`),
  dark: () => msg(str`Dark`),
};

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
        gap: 2px;
        padding: 3px;
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
        padding: 6px 10px;
        border-radius: var(--rune-radius-sm);
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        min-height: 28px;
        transition:
          background-color var(--rune-dur-fast) var(--rune-ease),
          color var(--rune-dur-fast) var(--rune-ease);
      }
      .opt:hover {
        background: var(--rune-surface);
        color: var(--rune-text);
      }
      .opt:focus-visible {
        outline: none;
        box-shadow: var(--rune-focus-ring);
      }
      .opt.active {
        background: var(--rune-primary);
        color: var(--rune-on-primary);
        font-weight: var(--rune-fw-semibold);
        box-shadow: var(--rune-shadow-1);
      }
      .opt.active:hover {
        background: var(--rune-primary-hover);
        color: var(--rune-on-primary);
      }
      .opt i {
        font-size: 16px;
        line-height: 1;
      }
      .compact .opt {
        padding: 6px 8px;
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
              <span>${OPTION_LABEL[o.value]()}</span>
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
