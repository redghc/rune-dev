// Document-level theme tokens. ``shared.ts`` exports ``rootTokens`` as a
// plain CSS string targeting ``:root`` and ``:root.sl-theme-dark`` —
// we need it to live in light DOM so the tokens cascade into every Lit
// shadow root via custom-property inheritance (no ``:host`` defaults,
// no ``:host-context()`` acrobatics, no per-browser gotchas).
//
// Shoelace ships the same trick via its own ``rune-shoelace-theme`` style
// tag — this one is the ``--rune-*`` counterpart.

import { injectStyle } from "./inject-style.js";
import { rootTokens } from "./shared.js";

const STYLE_ID = "rune-root-tokens";

export function injectRootTokens(): void {
  injectStyle(STYLE_ID, rootTokens);
}
