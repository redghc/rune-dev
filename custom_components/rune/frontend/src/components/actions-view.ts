import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import { api } from "../api/bridge.js";
import { store, subscribe } from "../state/store.js";
import { sharedStyles } from "../styles/shared.js";

@customElement("rune-actions-view")
export class RuneActionsView extends LitElement {
  static styles = [
    sharedStyles,
    css`
      .toolbar {
        display: flex;
        gap: 8px;
        align-items: center;
        margin-bottom: 16px;
      }
      .toolbar h2 {
        margin: 0;
        font-weight: 400;
      }
      .grow {
        flex: 1;
      }
      .action-card {
        background: var(--card);
        border-radius: 6px;
        padding: 10px;
        margin-bottom: 6px;
        border: 1px solid var(--border);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .action-card .info strong {
        font-weight: 500;
      }
      .action-card .meta {
        color: var(--muted);
        font-size: 11px;
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

  render() {
    void this._tick;
    const actions = store.actions;
    return html`
      <div class="toolbar">
        <h2>Actions</h2>
        <span class="grow"></span>
        <button class="secondary" @click=${this.refresh} ?disabled=${this._loading}>
          ${this._loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      <div class="help">
        Action bindings connect a captured signal to a side-effect: fire a pulse on a device, call a
        service, activate a scene, run a script, or fire an event. Bindings are managed
        programmatically (the API is stable; a UI editor lands in v0.4).
      </div>
      ${
        actions.length === 0
          ? html`<div class="empty">No action bindings yet.</div>`
          : actions.map(
              (a) => html`
                <div class="action-card">
                  <div class="info">
                    <strong>${a.name ?? a.id}</strong>
                    <div class="meta">
                      ${a.target.kind} · signal ${a.signal_id.slice(0, 8)}… · min_hits:
                      ${a.min_hits}
                    </div>
                  </div>
                </div>
              `,
            )
      }
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-actions-view": RuneActionsView;
  }
}
