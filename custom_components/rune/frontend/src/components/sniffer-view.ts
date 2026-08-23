import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import "@/components/ui/index.js";

import { api } from "@/api/bridge.js";
import { attachStoreController } from "@/state/store-controller.js";
import { reportError, store } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";
import { toolbarStyles } from "@/styles/views.js";

import type { Remote, RemoteSignal } from "@/types.js";

@customElement("rune-sniffer-view")
@localized()
export class RuneSnifferView extends LitElement {
  static styles = [
    sharedStyles,
    toolbarStyles,
    css`
      .remotes {
        display: flex;
        flex-direction: column;
        gap: var(--rune-space-4);
      }
      .remote-card {
        background: var(--rune-surface);
        border-radius: var(--rune-radius-md);
        padding: var(--rune-space-5);
        border: 1px solid var(--rune-border);
        box-shadow: var(--rune-shadow-1);
      }
      .remote-card.dismissed {
        opacity: 0.55;
      }
      .remote-head {
        display: flex;
        align-items: center;
        gap: var(--rune-space-3);
        margin-bottom: var(--rune-space-3);
      }
      .remote-icon {
        width: 36px;
        height: 36px;
        border-radius: var(--rune-radius-sm);
        background: var(--rune-primary-soft);
        color: var(--rune-primary);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
      }
      .remote-title {
        flex: 1;
        min-width: 0;
      }
      .remote-title h4 {
        margin: 0;
        font-size: var(--rune-fs-lg);
        font-weight: var(--rune-fw-semibold);
        color: var(--rune-text-strong);
        letter-spacing: -0.01em;
      }
      .remote-meta {
        display: flex;
        gap: var(--rune-space-2);
        align-items: center;
        margin-top: 4px;
        font-size: var(--rune-fs-xs);
        color: var(--rune-text-muted);
      }
      .signals {
        display: flex;
        flex-direction: column;
        gap: var(--rune-space-2);
      }
      .signal {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--rune-space-3);
        background: var(--rune-surface-alt);
        border-radius: var(--rune-radius-sm);
        border: 1px solid var(--rune-border);
        gap: var(--rune-space-3);
      }
      .signal-info {
        flex: 1;
        min-width: 0;
      }
      .signal-info .name {
        font-family: var(--rune-font-mono);
        font-size: var(--rune-fs-sm);
        color: var(--rune-text-strong);
        font-weight: var(--rune-fw-medium);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .signal-info .meta {
        color: var(--rune-text-muted);
        font-size: var(--rune-fs-xs);
        margin-top: 2px;
        display: flex;
        gap: var(--rune-space-2);
        flex-wrap: wrap;
      }
      .signal-info .meta i {
        font-size: 11px;
        line-height: 1;
      }
      .signal-info .meta-item {
        display: inline-flex;
        align-items: center;
        gap: 4px;
      }
      .hit-count {
        font-family: var(--rune-font-mono);
        font-weight: var(--rune-fw-semibold);
        color: var(--rune-primary);
        padding: var(--rune-space-1) var(--rune-space-2);
        background: var(--rune-primary-soft);
        border-radius: var(--rune-radius-sm);
        font-size: var(--rune-fs-xs);
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
      const { remotes } = await api.listSniffer();
      store.setRemotes(remotes ?? []);
    } catch (err) {
      reportError(err, msg(str`Load sniffer`));
    } finally {
      this._loading = false;
    }
  }

  private async _dismiss(r: Remote): Promise<void> {
    try {
      await api.dismissRemote(r.id);
      await this._refresh();
    } catch (err) {
      reportError(err);
    }
  }

  private _renderSignal(s: RemoteSignal) {
    return html`
      <div class="signal">
        <div class="signal-info">
          <div class="name">${s.alias ?? s.fingerprint ?? s.id}</div>
          <div class="meta">
            <span class="meta-item"> <i class="ti ti-clock"></i>${s.last_seen} </span>
            ${
              s.decoded_fingerprint
                ? html`<span class="meta-item">
                    <i class="ti ti-fingerprint"></i>${s.decoded_fingerprint}
                  </span>`
                : null
            }
          </div>
        </div>
        <rune-chip variant="primary" icon="bolt"
          >${msg(str`${s.hit_count} hit${s.hit_count === 1 ? "" : "s"}`)}</rune-chip
        >
      </div>
    `;
  }

  render() {
    const visible = store.remotes.filter((r) => !r.dismissed);
    const totalSignals = visible.reduce((acc, r) => acc + r.signals.length, 0);
    return html`
      <div class="toolbar">
        <h2>${msg(str`Sniffer`)}</h2>
        <rune-chip variant="neutral" icon="antenna"
          >${msg(str`${visible.length} ${visible.length === 1 ? msg(str`remote`) : msg(str`remotes`)} · ${totalSignals} ${totalSignals === 1 ? msg(str`signal`) : msg(str`signals`)}`)}</rune-chip
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
          html`Live signals captured from every receiver you've configured. The sniffer listens on
            each receiver entity automatically once you add a device. Assign a signal to a device
            command via the <strong>Actions</strong> tab, or dismiss the whole remote here.`,
        )}
      </div>
      ${
        visible.length === 0
          ? html`
              <rune-empty-state
                icon="antenna"
                heading=${msg(str`No captured signals yet`)}
                message=${msg(
                  str`Add a receiver (IR or RF) and RUNE will start listening. Captured signals appear here in real time.`,
                )}
              ></rune-empty-state>
            `
          : html`
              <div class="remotes">
                ${visible.map(
                  (r) => html`
                    <div class="remote-card ${r.dismissed ? "dismissed" : ""}">
                      <div class="remote-head">
                        <div class="remote-icon"><i class="ti ti-antenna"></i></div>
                        <div class="remote-title">
                          <h4>${r.label ?? r.protocol_label ?? r.id}</h4>
                          <div class="remote-meta">
                            ${
                              r.protocol_label
                                ? html`<rune-chip variant="primary">${r.protocol_label}</rune-chip>`
                                : html`<rune-chip variant="neutral"
                                    >${msg(str`unknown`)}</rune-chip
                                  >`
                            }
                            <span
                              >${msg(str`${r.signal_count} ${r.signal_count === 1 ? msg(str`signal`) : msg(str`signals`)}`)}</span
                            >
                          </div>
                        </div>
                        <rune-tooltip
                          content=${
                            r.dismissed
                              ? msg(str`Re-activate this remote`)
                              : msg(str`Hide this remote from the sniffer list`)
                          }
                        >
                          <rune-button
                            variant=${r.dismissed ? "ghost" : "secondary"}
                            icon=${r.dismissed ? "rotate" : "x"}
                            @click=${() => this._dismiss(r)}
                          >
                            ${r.dismissed ? msg(str`Re-activate`) : msg(str`Dismiss`)}
                          </rune-button>
                        </rune-tooltip>
                      </div>
                      ${
                        r.signals.length > 0
                          ? html`
                              <div class="signals">
                                ${r.signals.map((s) => this._renderSignal(s))}
                              </div>
                            `
                          : null
                      }
                    </div>
                  `,
                )}
              </div>
            `
      }
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-sniffer-view": RuneSnifferView;
  }
}
