import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import "@/components/ui/index.js";

import { store, subscribe } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

@customElement("rune-toast-stack")
export class RuneToastStack extends LitElement {
  static styles = [
    sharedStyles,
    css`
      .stack {
        position: fixed;
        bottom: var(--rune-space-6);
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        flex-direction: column-reverse;
        gap: var(--rune-space-2);
        z-index: var(--rune-z-toast, 1200);
        pointer-events: none;
      }
      .toast {
        display: flex;
        align-items: center;
        gap: var(--rune-space-2);
        padding: var(--rune-space-3) var(--rune-space-4);
        background: var(--rune-surface);
        border: 1px solid var(--rune-border);
        border-radius: var(--rune-radius-md);
        box-shadow: var(--rune-shadow-3);
        font-size: var(--rune-fs-sm);
        font-weight: var(--rune-fw-medium);
        color: var(--rune-text);
        min-width: 240px;
        max-width: 480px;
        pointer-events: auto;
        animation: rune-toast-in 0.18s var(--rune-ease);
      }
      .toast.ok {
        border-color: var(--rune-success);
        background: var(--rune-surface);
        color: var(--rune-text-strong);
      }
      .toast.err {
        border-color: var(--rune-danger);
        background: var(--rune-surface);
        color: var(--rune-text-strong);
      }
      .toast .badge {
        width: 22px;
        height: 22px;
        border-radius: var(--rune-radius-full);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        font-size: 13px;
      }
      .toast.ok .badge {
        background: var(--rune-success-soft);
        color: var(--rune-success);
      }
      .toast.err .badge {
        background: var(--rune-danger-soft);
        color: var(--rune-danger);
      }
      .toast .badge i {
        line-height: 1;
      }
      @keyframes rune-toast-in {
        from {
          opacity: 0;
          transform: translateY(12px) scale(0.96);
        }
        to {
          opacity: 1;
          transform: translateY(0) scale(1);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .toast {
          animation: none;
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
      <div class="stack" aria-live="polite" aria-atomic="true">
        ${store.toasts.map((t) => {
          const icon = t.kind === "err" ? "alert-circle" : "check";
          return html`
            <div class="toast ${t.kind ?? ""}" role="status">
              <span class="badge"><i class="ti ti-${icon}"></i></span>
              <span>${t.text}</span>
            </div>
          `;
        })}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-toast-stack": RuneToastStack;
  }
}
