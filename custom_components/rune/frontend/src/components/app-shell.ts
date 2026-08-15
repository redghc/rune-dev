import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

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

@customElement("rune-app")
export class RuneApp extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: grid;
        grid-template-columns: 220px 1fr;
        min-height: 100vh;
        background: var(--bg);
      }
      nav {
        background: var(--bg-2);
        border-right: 1px solid var(--border);
        padding: 16px 0;
      }
      .brand {
        padding: 0 20px 16px;
        border-bottom: 1px solid var(--border);
        margin-bottom: 12px;
      }
      .brand h1 {
        margin: 0;
        font-size: 18px;
        font-weight: 500;
      }
      .pill {
        display: inline-block;
        padding: 1px 6px;
        border-radius: 8px;
        background: var(--bg);
        color: var(--muted);
        font-size: 10px;
        border: 1px solid var(--border);
        margin-left: 4px;
      }
      .nav-item {
        display: block;
        padding: 10px 20px;
        color: var(--muted);
        text-decoration: none;
        cursor: pointer;
        border: 0;
        background: transparent;
        width: 100%;
        text-align: left;
        font: inherit;
        font-size: 13px;
      }
      .nav-item:hover {
        background: var(--bg);
        color: var(--text);
      }
      .nav-item.active {
        background: var(--bg);
        color: var(--primary);
        border-left: 3px solid var(--primary);
      }
      main {
        padding: 24px;
        overflow-y: auto;
        max-height: 100vh;
      }
    `,
  ];

  // Re-render on store change. We snapshot the whole store into a
  // single ``_tick`` counter so Lit knows to re-evaluate.
  @state() private _tick = 0;
  private _unsub: (() => void) | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    this._unsub = subscribe(() => {
      this._tick++;
    });
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
    // _tick is referenced so Lit tracks the dependency.
    void this._tick;
    return html`
      <nav>
        <div class="brand">
          <h1>RUNE <span class="pill">v${store.version}</span></h1>
        </div>
        ${(["devices", "sniffer", "actions", "settings"] as Section[]).map(
          (s) => html`
            <button
              class="nav-item ${store.section === s ? "active" : ""}"
              data-section=${s}
              @click=${() => this._select(s)}
            >
              ${s[0]!.toUpperCase()}${s.slice(1)}
            </button>
          `,
        )}
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
