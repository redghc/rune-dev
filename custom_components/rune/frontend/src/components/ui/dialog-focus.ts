// ReactiveController that handles the dialog focus dance:
//
//   • On ``sl-show`` (which fires when the host dialog opens), capture
//     the element that currently has focus so we can restore it when
//     the dialog closes.
//   • On ``sl-after-hide``, restore focus to the captured element and
//     invoke an optional ``onAfterHide`` callback so the host can sync
//     its own open state.
//
// The controller filters out events from nested Shoelace popups
// (e.g. ``<sl-select>`` dropdowns): only the host's own
// ``<rune-dialog>`` opening / closing fires the callbacks, so opening
// or closing a select inside the dialog doesn't steal focus or run the
// host's onAfterHide.
//
// Usage from a component constructor:
//
//   constructor() {
//     super();
//     attachDialogFocus(this, () => {
//       if (store.deviceDialog.open) store.closeDeviceDialog();
//     });
//   }

import type { ReactiveController, ReactiveControllerHost } from "lit";

interface DialogFocusHost extends ReactiveControllerHost, HTMLElement {
  renderRoot: HTMLElement | DocumentFragment;
}

const POPUP_TAGS = new Set(["sl-select", "sl-dropdown", "sl-popup"]);

export class DialogFocusController implements ReactiveController {
  private _returnFocusTo: HTMLElement | null = null;

  constructor(
    private readonly host: DialogFocusHost,
    private readonly onAfterHide?: () => void,
  ) {
    host.addController(this);
  }

  hostConnected(): void {
    this.host.addEventListener("sl-show", this._onShow);
    this.host.addEventListener("sl-after-hide", this._onAfterHide);
  }

  hostDisconnected(): void {
    this.host.removeEventListener("sl-show", this._onShow);
    this.host.removeEventListener("sl-after-hide", this._onAfterHide);
  }

  /** True when the event traversed the host's own ``<rune-dialog>``
   *  without going through a nested Shoelace popup. */
  private _isOwnEvent = (ev: Event): boolean => {
    const root = this.host.renderRoot;
    let sawDialog = false;
    for (const node of ev.composedPath()) {
      if (!(node instanceof Element)) continue;
      const tag = node.tagName.toLowerCase();
      if (POPUP_TAGS.has(tag)) return false;
      if (tag === "rune-dialog" && root.contains(node)) sawDialog = true;
    }
    return sawDialog;
  };

  private _onShow = (ev: Event): void => {
    if (!this._isOwnEvent(ev)) return;
    this._returnFocusTo = (this.host.getRootNode() as Document | ShadowRoot)
      .activeElement as HTMLElement | null;
    queueMicrotask(() => {
      const target = this.host.renderRoot.querySelector<HTMLElement>(
        "input, select, sl-input, sl-select, textarea, button",
      );
      target?.focus();
    });
  };

  private _onAfterHide = (ev: Event): void => {
    if (!this._isOwnEvent(ev)) return;
    this._returnFocusTo?.focus();
    this._returnFocusTo = null;
    this.onAfterHide?.();
  };
}

/** Attach a ``DialogFocusController`` to ``host`` without storing the
 *  reference. */
export function attachDialogFocus(host: DialogFocusHost, onAfterHide?: () => void): void {
  void new DialogFocusController(host, onAfterHide);
}
