import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import { store, subscribe } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

@customElement("rune-toast-stack")
export class RuneToastStack extends LitElement {
  static styles = [
    sharedStyles,
    css`
      .stack {
        position: fixed;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        flex-direction: column;
        gap: 8px;
        z-index: 1000;
        pointer-events: none;
      }
      .toast {
        background: var(--card);
        border: 1px solid var(--border);
        padding: 12px 20px;
        border-radius: 8px;
        max-width: 80%;
        animation: rune-fade-in 0.15s ease-out;
      }
      .toast.err {
        border-color: var(--danger);
        color: #ff8a80;
      }
      .toast.ok {
        border-color: var(--ok);
        color: #b9f6ca;
      }
      @keyframes rune-fade-in {
        from {
          opacity: 0;
          transform: translateY(8px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
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

  render() {
    void this._tick;
    return html`
      <div class="stack">
        ${store.toasts.map((t) => html` <div class="toast ${t.kind ?? ""}">${t.text}</div> `)}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-toast-stack": RuneToastStack;
  }
}
