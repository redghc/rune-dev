import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import "@/components/ui/index.js";

import { store, subscribe } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

import type { Section } from "@/state/store.js";

import "./toast-stack.js";
import "./devices-view.js";
import "./sniffer-view.js";
import "./actions-view.js";
import "./settings-view.js";
import "./device-dialog.js";
import "./learn-dialog.js";

interface NavItem {
  id: Section;
  icon: string;
  shortcut: [string, string];
}

const NAV: NavItem[] = [
  { id: "devices", icon: "devices", shortcut: ["g", "d"] },
  { id: "sniffer", icon: "antenna", shortcut: ["g", "s"] },
  { id: "actions", icon: "wand", shortcut: ["g", "a"] },
  { id: "settings", icon: "settings", shortcut: ["g", "x"] },
];

function sectionLabel(id: Section) {
  switch (id) {
    case "devices":
      return msg(str`Devices`);
    case "sniffer":
      return msg(str`Sniffer`);
    case "actions":
      return msg(str`Actions`);
    case "settings":
      return msg(str`Settings`);
  }
}

const SHORTCUT_MAP: Record<string, Section> = {
  d: "devices",
  s: "sniffer",
  a: "actions",
  x: "settings",
};

@customElement("rune-app")
@localized()
export class RuneApp extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: grid;
        grid-template-columns: 240px 1fr;
        grid-template-rows: 100vh;
        height: 100%;
        min-height: 100vh;
        background: var(--rune-bg);
        color: var(--rune-text);
      }
      .skip-link {
        position: fixed;
        top: var(--rune-space-2);
        left: var(--rune-space-2);
        padding: var(--rune-space-2) var(--rune-space-3);
        background: var(--rune-primary);
        color: var(--rune-on-primary);
        border-radius: var(--rune-radius-sm);
        font-size: var(--rune-fs-sm);
        font-weight: var(--rune-fw-semibold);
        text-decoration: none;
        z-index: 9999;
        transform: translateY(-200%);
        transition: transform var(--rune-dur-fast) var(--rune-ease);
        box-shadow: var(--rune-shadow-3);
      }
      .skip-link:focus {
        transform: translateY(0);
      }
      nav {
        background: var(--rune-bg-elevated);
        border-right: 1px solid var(--rune-border);
        padding: var(--rune-space-5) var(--rune-space-2);
        height: 100%;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: var(--rune-space-1);
      }
      .brand {
        padding: 0 var(--rune-space-3) var(--rune-space-4);
        border-bottom: 1px solid var(--rune-border);
        margin-bottom: var(--rune-space-3);
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
        flex-shrink: 0;
      }
      .brand-mark {
        width: 32px;
        height: 32px;
        border-radius: var(--rune-radius-sm);
        background: linear-gradient(
          135deg,
          var(--rune-primary) 0%,
          var(--rune-primary-active) 100%
        );
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: var(--rune-on-primary);
        font-size: 18px;
        box-shadow: var(--rune-shadow-1);
        flex-shrink: 0;
      }
      .brand h1 {
        margin: 0;
        font-size: var(--rune-fs-lg);
        font-weight: var(--rune-fw-semibold);
        letter-spacing: -0.02em;
        color: var(--rune-text-strong);
        white-space: nowrap;
        flex: 1;
        min-width: 0;
      }
      .pill {
        display: inline-block;
        padding: 2px 8px;
        border-radius: var(--rune-radius-full);
        background: var(--rune-surface-alt);
        color: var(--rune-text-muted);
        font-size: var(--rune-fs-xs);
        font-weight: var(--rune-fw-medium);
        flex-shrink: 0;
      }
      .nav-item {
        display: flex;
        align-items: center;
        gap: var(--rune-space-3);
        padding: var(--rune-space-3);
        color: var(--rune-text-muted);
        text-decoration: none;
        cursor: pointer;
        border: 0;
        background: transparent;
        border-radius: var(--rune-radius-sm);
        width: 100%;
        text-align: left;
        font: inherit;
        font-size: var(--rune-fs-sm);
        font-weight: var(--rune-fw-medium);
        transition:
          background-color var(--rune-dur-fast) var(--rune-ease),
          color var(--rune-dur-fast) var(--rune-ease);
        flex-shrink: 0;
      }
      .nav-item:hover {
        background: var(--rune-surface-alt);
        color: var(--rune-text);
      }
      .nav-item.active {
        background: var(--rune-primary-soft);
        color: var(--rune-primary-text);
        font-weight: var(--rune-fw-semibold);
      }
      .nav-item i {
        font-size: 18px;
        line-height: 1;
        width: 18px;
        flex-shrink: 0;
      }
      .nav-item .label {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .kbd {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        flex-shrink: 0;
      }
      .kbd kbd {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 18px;
        height: 18px;
        padding: 0 4px;
        border-radius: var(--rune-radius-xs);
        background: var(--rune-surface);
        border: 1px solid var(--rune-border);
        border-bottom-width: 2px;
        color: var(--rune-text-muted);
        font-family: var(--rune-font-mono);
        font-size: 10px;
        font-weight: var(--rune-fw-semibold);
        line-height: 1;
      }
      .nav-item.active .kbd kbd {
        background: var(--rune-surface);
        border-color: var(--rune-primary);
        color: var(--rune-primary);
      }
      .footer {
        margin-top: auto;
        padding: var(--rune-space-3);
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-subtle);
        border-top: 1px solid var(--rune-border);
        display: flex;
        flex-direction: column;
        gap: var(--rune-space-2);
        flex-shrink: 0;
      }
      .status-row {
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
      }
      .status-row .dot {
        width: 8px;
        height: 8px;
        border-radius: var(--rune-radius-full);
        background: var(--rune-success);
        box-shadow: 0 0 0 3px var(--rune-success-soft);
        flex-shrink: 0;
      }
      main {
        padding: var(--rune-space-6);
        overflow-y: auto;
        height: 100%;
        max-height: 100vh;
        background: var(--rune-bg);
        animation: rune-section-in 0.18s var(--rune-ease);
      }
      @keyframes rune-section-in {
        from {
          opacity: 0;
          transform: translateY(4px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        main {
          animation: none;
        }
      }

      /* ---- Compact viewport (≤ 760px) ---- */
      @media (max-width: 760px) {
        :host {
          grid-template-columns: 1fr;
          grid-template-rows: auto 1fr;
          height: auto;
          min-height: 100vh;
        }
        nav {
          height: auto;
          border-right: none;
          border-bottom: 1px solid var(--rune-border);
          padding: var(--rune-space-3);
          flex-direction: row;
          overflow-x: auto;
          overflow-y: hidden;
          gap: var(--rune-space-1);
        }
        .brand {
          border-bottom: none;
          padding: 0;
          margin-bottom: 0;
          margin-right: var(--rune-space-3);
          flex-shrink: 0;
        }
        .brand h1 {
          font-size: var(--rune-fs-md);
        }
        .nav-item {
          flex: 0 0 auto;
          width: auto;
          padding: var(--rune-space-2) var(--rune-space-3);
          font-size: var(--rune-fs-xs);
        }
        .nav-item .label {
          max-width: 80px;
        }
        .kbd {
          display: none;
        }
        .footer {
          display: none;
        }
        main {
          padding: var(--rune-space-4);
          max-height: none;
        }
      }
    `,
  ];

  @state() private _tick = 0;
  private _unsub: (() => void) | null = null;
  private _shortcutPrefix: string | null = null;
  private _shortcutTimer: ReturnType<typeof setTimeout> | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    this._unsub = subscribe(() => this._tick++);
    document.addEventListener("keydown", this._onKeydown);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsub?.();
    document.removeEventListener("keydown", this._onKeydown);
    if (this._shortcutTimer) clearTimeout(this._shortcutTimer);
  }

  private _onKeydown = (ev: KeyboardEvent): void => {
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    const target = ev.target as HTMLElement | null;
    const inField =
      target?.tagName === "INPUT" ||
      target?.tagName === "TEXTAREA" ||
      target?.tagName === "SELECT" ||
      target?.isContentEditable;
    if (inField) return;
    if (ev.key === "g") {
      this._shortcutPrefix = "g";
      if (this._shortcutTimer) clearTimeout(this._shortcutTimer);
      this._shortcutTimer = setTimeout(() => {
        this._shortcutPrefix = null;
      }, 1200);
      return;
    }
    if (this._shortcutPrefix === "g") {
      const section = SHORTCUT_MAP[ev.key.toLowerCase()];
      if (section) {
        ev.preventDefault();
        store.setSection(section);
      }
      this._shortcutPrefix = null;
      if (this._shortcutTimer) clearTimeout(this._shortcutTimer);
    }
  };

  private _select(s: Section): void {
    store.setSection(s);
  }

  private _renderSection() {
    switch (store.section) {
      case "sniffer":
        return html`<rune-sniffer-view></rune-sniffer-view>`;
      case "actions":
        return html`<rune-actions-view></rune-actions-view>`;
      case "settings":
        return html`<rune-settings-view></rune-settings-view>`;
      case "devices":
      default:
        return html`<rune-devices-view></rune-devices-view>`;
    }
  }

  render() {
    void this._tick;
    return html`
      <a class="skip-link" href="#main-content">${msg(str`Skip to content`)}</a>
      <nav aria-label="Primary">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true">
            <i class="ti ti-remote"></i>
          </span>
          <h1>${msg(str`RUNE`)}<span class="pill">v${store.version}</span></h1>
        </div>
        ${NAV.map(
          (n) => html`
            <button
              class="nav-item ${store.section === n.id ? "active" : ""}"
              data-section=${n.id}
              aria-current=${store.section === n.id ? "page" : "false"}
              @click=${() => this._select(n.id)}
            >
              <i class="ti ti-${n.icon}" aria-hidden="true"></i>
              <span class="label">${sectionLabel(n.id)}</span>
              <span class="kbd" aria-hidden="true">
                <kbd>${n.shortcut[0]}</kbd><kbd>${n.shortcut[1]}</kbd>
              </span>
            </button>
          `,
        )}
        <div class="footer">
          <rune-theme-toggle compact></rune-theme-toggle>
          <div class="status-row" role="status" aria-live="polite">
            <span class="dot"></span>
            <span>${msg(str`Connected`)}</span>
          </div>
        </div>
      </nav>
      <main id="main-content" tabindex="-1">${this._renderSection()}</main>
      <rune-toast-stack></rune-toast-stack>
      <rune-device-dialog></rune-device-dialog>
      <rune-learn-dialog></rune-learn-dialog>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-app": RuneApp;
  }
}
