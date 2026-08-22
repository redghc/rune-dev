import { autoUpdate, computePosition, flip, offset, shift } from "@floating-ui/dom";

import type { Placement } from "@floating-ui/dom";

// Thin wrapper around @floating-ui/dom for popovers that aren't covered
// by Shoelace (e.g. custom context menus, lazy-loaded command palettes,
// etc). Returns a cleanup fn that stops auto-positioning.
//
// Usage:
//   const cleanup = attachFloating(refEl, popEl, { placement: "bottom-end" });
//   ...later
//   cleanup();
//
// All handlers are passive: this module never mutates Shoelace state.

export interface FloatingOptions {
  placement?: Placement;
  offset?: number;
  flip?: boolean;
  shiftPadding?: number;
}

export function attachFloating(
  reference: HTMLElement,
  floating: HTMLElement,
  opts: FloatingOptions = {},
): () => void {
  const middleware = [
    offset(opts.offset ?? 6),
    ...((opts.flip ?? true) ? [flip()] : []),
    shift({ padding: opts.shiftPadding ?? 8 }),
  ];

  floating.style.position = "absolute";
  floating.style.top = "0";
  floating.style.left = "0";

  const update = async () => {
    const { x, y } = await computePosition(reference, floating, {
      placement: opts.placement ?? "bottom",
      middleware,
    });
    Object.assign(floating.style, {
      transform: `translate(${Math.round(x)}px, ${Math.round(y)}px)`,
    });
  };

  return autoUpdate(reference, floating, update);
}
