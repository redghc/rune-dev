import { css, html, LitElement } from "lit";
import { customElement, property } from "lit/decorators.js";

import { ensureIconCss, tablerClass } from "./icon.js";

export type RuneIconSize = "xs" | "sm" | "md" | "lg" | "xl";

const SIZE_MAP: Record<RuneIconSize, string> = {
  xs: "0.75em",
  sm: "0.9em",
  md: "1.1em",
  lg: "1.4em",
  xl: "1.8em",
};

@customElement("rune-icon")
export class RuneIcon extends LitElement {
  static styles = css`
    :host {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      line-height: 1;
      vertical-align: -0.125em;
    }
    i {
      font-size: inherit;
      color: inherit;
    }
  `;

  @property({ type: String }) name = "";
  @property({ type: String }) size: RuneIconSize = "md";
  @property({ type: String }) color = "";

  connectedCallback(): void {
    super.connectedCallback();
    ensureIconCss();
  }

  protected render() {
    const sizeStyle = `font-size:${SIZE_MAP[this.size]}`;
    const colorStyle = this.color ? `color:${this.color}` : "";
    return html`<i
      class="ti ${tablerClass(this.name).replace("ti ", "")}"
      style="${sizeStyle};${colorStyle}"
      aria-hidden="true"
    ></i>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-icon": RuneIcon;
  }
}
