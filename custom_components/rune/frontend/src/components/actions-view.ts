import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import "@/components/ui/index.js";

import { api } from "@/api/bridge.js";
import { attachStoreController } from "@/state/store-controller.js";
import { reportError, store } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";
import { toolbarStyles } from "@/styles/views.js";
import { pluralize } from "@/utils/format.js";

import type { ActionBinding } from "@/types.js";

@customElement("rune-actions-view")
@localized()
export class RuneActionsView extends LitElement {
  static styles = [
    sharedStyles,
    toolbarStyles,
    css`
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

  constructor() {
    super();
    attachStoreController(this);
  }

  @state() private _loading = false;

  connectedCallback(): void {
    super.connectedCallback();
    void this._refresh();
  }

  private async _refresh(): Promise<void> {
    this._loading = true;
    try {
      const { actions } = await api.listActions();
      store.setActions(actions ?? []);
    } catch (err) {
      reportError(err, msg(str`Load actions`));
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
              ${msg(str`signal`)} ${a.signal_id.slice(0, 8)}…
            </span>
            <span>
              <i class="ti ti-bolt"></i>
              ${msg(str`min_hits: ${a.min_hits}`)}
            </span>
          </div>
        </div>
      </div>
    `;
  }

  render() {
    const actions = store.actions;
    return html`
      <div class="toolbar">
        <h2>${msg(str`Actions`)}</h2>
        <rune-chip variant="neutral" icon="wand"
          >${msg(str`${pluralize(actions.length, "binding")}`)}</rune-chip
        >
        <span class="grow"></span>
        <rune-tooltip content="Reload from backend">
          <rune-button
            variant="secondary"
            icon="refresh"
            ?loading=${this._loading}
            @click=${this._refresh}
          >
            ${msg(str`Refresh`)}
          </rune-button>
        </rune-tooltip>
      </div>
      <div class="help">
        <i class="ti ti-info-circle"></i>
        ${msg(
          str`Action bindings connect a captured signal to a side-effect: fire a pulse on a device, call a service, activate a scene, run a script, or fire an event. Bindings are managed programmatically (the API is stable; a UI editor lands in v0.4).`,
        )}
      </div>
      ${
        actions.length === 0
          ? html`
              <rune-empty-state
                icon="wand"
                heading=${msg(str`No action bindings yet`)}
                message=${msg(str`Create bindings from the API or wait for the v0.4 editor.`)}
              ></rune-empty-state>
            `
          : html`<div class="actions">${actions.map((a) => this._renderAction(a))}</div>`
      }
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-actions-view": RuneActionsView;
  }
}
