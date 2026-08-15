import { css, html, LitElement } from "lit";
import { customElement, state } from "lit/decorators.js";

import { api } from "@/api/bridge.js";
import { store, subscribe } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

import type { Remote } from "@/types.js";

@customElement("rune-sniffer-view")
export class RuneSnifferView extends LitElement {
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
      .remote-card {
        background: var(--card);
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 12px;
        border: 1px solid var(--border);
      }
      .remote-card.dismissed {
        opacity: 0.5;
      }
      .remote-card h4 {
        margin: 0 0 8px;
        font-size: 14px;
      }
      .signal-card {
        background: var(--card);
        border-radius: 6px;
        padding: 10px;
        margin-bottom: 6px;
        border: 1px solid var(--border);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .signal-card .info {
        font-size: 13px;
      }
      .signal-card .meta {
        color: var(--muted);
        font-size: 11px;
      }
      .badge {
        display: inline-block;
        padding: 1px 8px;
        border-radius: 10px;
        background: var(--bg-2);
        color: var(--muted);
        font-size: 11px;
        border: 1px solid var(--border);
        margin-left: 6px;
      }
      .badge.protocol {
        color: var(--primary);
        border-color: var(--primary);
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
      const { remotes } = await api.listSniffer();
      store.setRemotes(remotes ?? []);
    } catch (err) {
      store.pushToast(`Load sniffer: ${(err as Error).message}`, "err");
    } finally {
      this._loading = false;
    }
  }

  private async _dismiss(r: Remote): Promise<void> {
    try {
      await api.dismissRemote(r.id);
      await this.refresh();
    } catch (err) {
      store.pushToast((err as Error).message, "err");
    }
  }

  render() {
    void this._tick;
    const visible = store.remotes.filter((r) => !r.dismissed);
    return html`
      <div class="toolbar">
        <h2>Sniffer</h2>
        <span class="grow"></span>
        <button class="secondary" @click=${this.refresh} ?disabled=${this._loading}>
          ${this._loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      <div class="help">
        Live signals captured from every receiver you've configured. The sniffer listens on each
        receiver entity automatically once you add a device. Assign a signal to a device command via
        the
        <code>Actions</code> tab, or dismiss the whole remote here.
      </div>
      ${
        visible.length === 0
          ? html`<div class="empty">No captured signals yet.</div>`
          : visible.map(
              (r) => html`
                <div class="remote-card ${r.dismissed ? "dismissed" : ""}">
                  <h4>
                    ${r.label ?? r.protocol_label ?? r.id}
                    <span class="badge protocol">${r.protocol_label ?? "unknown"}</span>
                    <span class="badge">${r.signal_count} signal(s)</span>
                  </h4>
                  ${r.signals.map(
                    (s) => html`
                      <div class="signal-card">
                        <div class="info">${s.alias ?? s.fingerprint ?? s.id}</div>
                        <div class="meta">
                          hits: ${s.hit_count} · last: ${s.last_seen} ·
                          ${s.decoded_fingerprint ?? "—"}
                        </div>
                      </div>
                    `,
                  )}
                  <button class="secondary" @click=${() => this._dismiss(r)}>
                    ${r.dismissed ? "Re-activate" : "Dismiss remote"}
                  </button>
                </div>
              `,
            )
      }
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-sniffer-view": RuneSnifferView;
  }
}
