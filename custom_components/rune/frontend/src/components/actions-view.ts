import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import "@/components/ui/index.js";

import { api } from "@/api/bridge.js";
import { store, subscribe } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

import type { ActionBinding } from "@/types.js";

@customElement("rune-actions-view")
export class RuneActionsView extends LitElement {
  static styles = [
    sharedStyles,
    css`
      .toolbar {
        display: flex;
        gap: var(--rune-space-3);
        align-items: center;
        margin-bottom: var(--rune-space-5);
      }
      .toolbar h2 {
        margin: 0;
        font-size: var(--rune-fs-2xl);
        font-weight: var(--rune-fw-semibold);
        letter-spacing: -0.02em;
        color: var(--rune-text-strong);
      }
      .grow {
        flex: 1;
      }
      .actions {
        display: flex;
        flex-direction: column;
        gap: var(--rune-space-2);
      }
      .action {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--rune-space-4);
        background: var(--rune-surface);
        border-radius: var(--rune-radius-md);
        border: 1px solid var(--rune-border);
        box-shadow: var(--rune-shadow-1);
        gap: var(--rune-space-3);
      }
      .action-info {
        flex: 1;
        min-width: 0;
      }
      .action-info .name {
        font-size: var(--rune-fs-md);
        font-weight: var(--rune-fw-semibold);
        color: var(--rune-text-strong);
        margin-bottom: 4px;
      }
      .action-info .meta {
        display: flex;
        flex-wrap: wrap;
        gap: var(--rune-space-2);
        align-items: center;
        color: var(--rune-text-muted);
        font-size: var(--rune-fs-xs);
        font-family: var(--rune-font-mono);
      }
      .action-info .meta i {
        font-size: 11px;
        line-height: 1;
      }
      .action-icon {
        width: 40px;
        height: 40px;
        border-radius: var(--rune-radius-sm);
        background: var(--rune-primary-soft);
        color: var(--rune-primary);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        flex-shrink: 0;
      }
    `,
  ];

  @state() private _tick = 0;
  @state() private _loading = false;
  private _unsub: (() => void) | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    this._unsub = subscribe(() => this._tick++);
    void this.refresh();
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsub?.();
  }

  private async refresh(): Promise<void> {
    this._loading = true;
    try {
      const { actions } = await api.listActions();
      store.setActions(actions ?? []);
    } catch (err) {
      store.pushToast(`Load actions: ${(err as Error).message}`, "err");
    } finally {
      this._loading = false;
    }
  }

  private _renderAction(a: ActionBinding) {
    return html`
      <div class="action">
        <div class="action-icon"><i class="ti ti-wand"></i></div>
        <div class="action-info">
          <div class="name">${a.name ?? a.id}</div>
          <div class="meta">
            <rune-chip variant="primary" icon="target">${a.target.kind}</rune-chip>
            <span>
              <i class="ti ti-fingerprint"></i>
              signal ${a.signal_id.slice(0, 8)}…
            </span>
            <span> <i class="ti ti-bolt"></i> min_hits: ${a.min_hits} </span>
          </div>
        </div>
      </div>
    `;
  }

  render() {
    void this._tick;
    const actions = store.actions;
    return html`
      <div class="toolbar">
        <h2>Actions</h2>
        <rune-chip variant="neutral" icon="wand"
          >${actions.length} binding${actions.length === 1 ? "" : "s"}</rune-chip
        >
        <span class="grow"></span>
        <rune-tooltip content="Reload from backend">
          <rune-button
            variant="secondary"
            icon="refresh"
            ?loading=${this._loading}
            @click=${this.refresh}
          >
            Refresh
          </rune-button>
        </rune-tooltip>
      </div>
      <div class="help">
        <i class="ti ti-info-circle"></i> Action bindings connect a captured signal to a
        side-effect: fire a pulse on a device, call a service, activate a scene, run a script, or
        fire an event. Bindings are managed programmatically (the API is stable; a UI editor lands
        in v0.4).
      </div>
      ${
        actions.length === 0
          ? html`
              <rune-empty-state
                icon="wand"
                heading="No action bindings yet"
                message="Create bindings from the API or wait for the v0.4 editor."
              ></rune-empty-state>
            `
          : html` <div class="actions">${actions.map((a) => this._renderAction(a))}</div> `
      }
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-actions-view": RuneActionsView;
  }
}
