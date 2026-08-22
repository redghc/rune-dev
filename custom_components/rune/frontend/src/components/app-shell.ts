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
  label: string;
  icon: string;
}

const NAV: NavItem[] = [
  { id: "devices", label: "Devices", icon: "devices" },
  { id: "sniffer", label: "Sniffer", icon: "antenna" },
  { id: "actions", label: "Actions", icon: "wand" },
  { id: "settings", label: "Settings", icon: "settings" },
];

@customElement("rune-app")
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
      }
      .brand h1 {
        margin: 0;
        font-size: var(--rune-fs-lg);
        font-weight: var(--rune-fw-semibold);
        letter-spacing: -0.02em;
        color: var(--rune-text-strong);
      }
      .pill {
        display: inline-block;
        padding: 2px 8px;
        border-radius: var(--rune-radius-full);
        background: var(--rune-surface-alt);
        color: var(--rune-text-muted);
        font-size: var(--rune-fs-xs);
        font-weight: var(--rune-fw-medium);
        margin-left: auto;
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
      .footer {
        margin-top: auto;
        padding: var(--rune-space-3);
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-subtle);
        border-top: 1px solid var(--rune-border);
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
      }
      .footer .dot {
        width: 8px;
        height: 8px;
        border-radius: var(--rune-radius-full);
        background: var(--rune-success);
        box-shadow: 0 0 0 3px var(--rune-success-soft);
      }
      main {
        padding: var(--rune-space-6);
        overflow-y: auto;
        height: 100%;
        max-height: 100vh;
        background: var(--rune-bg);
      }
    `,
  ];

  @state() private _tick = 0;
  private _unsub: (() => void) | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    this._unsub = subscribe(() => this._tick++);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsub?.();
  }

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
      <nav>
        <div class="brand">
          <span class="brand-mark"><i class="ti ti-remote"></i></span>
          <h1>RUNE<span class="pill">v${store.version}</span></h1>
        </div>
        ${NAV.map(
          (n) => html`
            <button
              class="nav-item ${store.section === n.id ? "active" : ""}"
              data-section=${n.id}
              aria-current=${store.section === n.id ? "page" : "false"}
              @click=${() => this._select(n.id)}
            >
              <i class="ti ti-${n.icon}"></i>
              <span>${n.label}</span>
            </button>
          `,
        )}
        <div class="footer">
          <span class="dot"></span>
          <span>Connected</span>
        </div>
      </nav>
      <main>${this._renderSection()}</main>
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
