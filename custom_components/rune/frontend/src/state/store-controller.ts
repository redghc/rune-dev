// ReactiveController that wires a LitElement to the global store.
//
// Before this controller every consumer had to repeat:
//
//   @state() private _tick = 0;
//   private _unsub: (() => void) | null = null;
//   connectedCallback()  { super.connectedCallback(); this._unsub = subscribe(() => this._tick++); }
//   disconnectedCallback(){ super.disconnectedCallback(); this._unsub?.(); }
//   render() { void this._tick; /* ... */ }
//
// That pattern leaks the reactive plumbing into nine components and
// forces every render to read ``void this._tick`` so Lit doesn't elide
// it. The controller hooks into the host lifecycle instead: subscribe
// on connect, unsubscribe on disconnect, and trigger an update on
// every store notification — no extra state needed.
//
// Usage from a component constructor:
//
//   constructor() {
//     super();
//     attachStoreController(this);
//   }

import { subscribe } from "./store.js";

import type { ReactiveController, ReactiveControllerHost } from "lit";

export class StoreController implements ReactiveController {
  private _unsub: (() => void) | null = null;

  constructor(private readonly host: ReactiveControllerHost) {
    host.addController(this);
  }

  hostConnected(): void {
    this._unsub = subscribe(() => this.host.requestUpdate());
  }

  hostDisconnected(): void {
    this._unsub?.();
    this._unsub = null;
  }
}

/** Attach a ``StoreController`` to ``host`` without storing the
 *  reference. The controller self-registers via ``addController`` so
 *  the host keeps it alive for its full lifetime. */
export function attachStoreController(host: ReactiveControllerHost): void {
  void new StoreController(host);
}
