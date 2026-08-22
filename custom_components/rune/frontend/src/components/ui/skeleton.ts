import { css, html, LitElement } from "lit";
import { customElement, property } from "lit/decorators.js";

import { sharedStyles } from "@/styles/shared.js";

export type RuneSkeletonVariant = "text" | "circle" | "rect";

@customElement("rune-skeleton")
export class RuneSkeleton extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
        --sk-bg: linear-gradient(
          90deg,
          var(--rune-surface-alt) 0%,
          var(--rune-border) 50%,
          var(--rune-surface-alt) 100%
        );
      }
      .sk {
        background: var(--sk-bg);
        background-size: 200% 100%;
        animation: rune-shimmer 1.4s ease-in-out infinite;
        border-radius: var(--rune-radius-xs);
        width: 100%;
        display: block;
      }
      .text {
        height: 0.9em;
        border-radius: var(--rune-radius-xs);
      }
      .circle {
        border-radius: var(--rune-radius-full);
      }
      .rect {
        border-radius: var(--rune-radius-sm);
      }
      @keyframes rune-shimmer {
        0% {
          background-position: 200% 0;
        }
        100% {
          background-position: -200% 0;
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .sk {
          animation: none;
        }
      }
    `,
  ];

  @property({ type: String }) variant: RuneSkeletonVariant = "text";
  @property({ type: String }) width = "100%";
  @property({ type: String }) height = "auto";

  protected render() {
    return html`
      <span
        class="sk ${this.variant}"
        style="width:${this.width};height:${this.height}"
        aria-busy="true"
        aria-live="polite"
      ></span>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-skeleton": RuneSkeleton;
  }
}
