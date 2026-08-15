import { css, html, LitElement } from "lit";
import { customElement, query, state } from "lit/decorators.js";

import { api } from "@/api/bridge.js";
import { store, subscribe } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

import type { DeviceCategory, TxEntity } from "@/types.js";

const CATEGORIES: DeviceCategory[] = [
  "fan",
  "climate",
  "light",
  "cover",
  "media_player",
  "switch",
  "remote",
];

@customElement("rune-device-dialog")
export class RuneDeviceDialog extends LitElement {
  static styles = [
    sharedStyles,
    css`
      dialog {
        background: var(--card);
        color: var(--text);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 24px;
        min-width: 420px;
        max-width: 90vw;
      }
      dialog::backdrop {
        background: rgba(0, 0, 0, 0.6);
      }
      .form-row {
        display: flex;
        flex-direction: column;
        gap: 4px;
        margin-bottom: 12px;
      }
      .form-row label {
        font-size: 12px;
        color: var(--muted);
      }
      .dialog-actions {
        display: flex;
        gap: 8px;
        justify-content: flex-end;
        margin-top: 16px;
      }
      .tx-row {
        display: flex;
        gap: 4px;
        align-items: center;
      }
      .tx-row select {
        flex: 1;
      }
      h2 {
        margin: 0 0 16px;
      }
      .err {
        color: var(--danger);
        font-size: 12px;
      }
    `,
  ];

  @state() private _tick = 0;
  @state() private _txLoading = false;
  @state() private _transmitters: TxEntity[] = [];
  @state() private _err = "";
  @state() private _busy = false;
  private _unsub: (() => void) | null = null;
  @query("#dlg") private _dlg!: HTMLDialogElement;
  @query("#name") private _nameEl!: HTMLInputElement;
  @query("#category") private _categoryEl!: HTMLSelectElement;
  @query("#manufacturer") private _manufacturerEl!: HTMLInputElement;
  @query("#model") private _modelEl!: HTMLInputElement;
  @query("#tx") private _txEl!: HTMLSelectElement;

  connectedCallback(): void {
    super.connectedCallback();
    this._unsub = subscribe(() => {
      const wasOpen = this._dlg?.open ?? false;
      this._tick++;
      // Open / close the native <dialog> when store toggles. Done in
      // updated() so we know the dialog element exists.
      queueMicrotask(() => {
        const dlg = this._dlg;
        if (!dlg) return;
        if (store.deviceDialog.open && !wasOpen) {
          dlg.showModal();
        } else if (!store.deviceDialog.open && wasOpen) {
          dlg.close();
        }
      });
    });
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsub?.();
  }

  protected updated(_changed: Map<string, unknown>): void {
    void _changed;
    void this._tick;
    const editing = store.deviceDialog.editing;
    // Populate form fields once the dialog becomes visible. We set
    // them imperatively to avoid re-rendering <select> state which
    // can lose the user's open dropdown.
    if (this._dlg?.open) {
      if (editing) {
        if (this._nameEl && document.activeElement !== this._nameEl) {
          this._nameEl.value = editing.name;
        }
        if (this._categoryEl && document.activeElement !== this._categoryEl) {
          this._categoryEl.value = editing.category;
        }
        if (this._manufacturerEl && document.activeElement !== this._manufacturerEl) {
          this._manufacturerEl.value = editing.manufacturer ?? "";
        }
        if (this._modelEl && document.activeElement !== this._modelEl) {
          this._modelEl.value = editing.model ?? "";
        }
      } else {
        if (this._nameEl && document.activeElement !== this._nameEl) {
          this._nameEl.value = "";
        }
        if (this._categoryEl && document.activeElement !== this._categoryEl) {
          this._categoryEl.value = "fan";
        }
        if (this._manufacturerEl && document.activeElement !== this._manufacturerEl) {
          this._manufacturerEl.value = "";
        }
        if (this._modelEl && document.activeElement !== this._modelEl) {
          this._modelEl.value = "";
        }
      }
      void this._loadTransmitters(editing?.transmitter_entity_ids ?? null);
    }
  }

  private async _loadTransmitters(selected: string[] | null): Promise<void> {
    this._txLoading = true;
    try {
      const { transmitters } = await api.transmitters();
      this._transmitters = transmitters ?? [];
      // Sync the <select> with loaded options.
      queueMicrotask(() => {
        if (!this._txEl) return;
        this._txEl.innerHTML = "";
        if (!this._transmitters.length) {
          const opt = document.createElement("option");
          opt.value = "";
          opt.textContent = "(no IR/RF emitters in HA)";
          this._txEl.appendChild(opt);
          return;
        }
        for (const t of this._transmitters) {
          const opt = document.createElement("option");
          opt.value = t.entity_id;
          opt.textContent = `${t.entity_id} (${t.state})`;
          if (selected && selected.includes(t.entity_id)) opt.selected = true;
          this._txEl.appendChild(opt);
        }
      });
    } catch (err) {
      this._transmitters = [];
      queueMicrotask(() => {
        if (!this._txEl) return;
        this._txEl.innerHTML = `<option>${(err as Error).message}</option>`;
      });
    } finally {
      this._txLoading = false;
    }
  }

  private _cancel(): void {
    store.closeDeviceDialog();
  }

  private async _save(): Promise<void> {
    this._err = "";
    const editing = store.deviceDialog.editing;
    const name = this._nameEl?.value.trim() ?? "";
    const category = this._categoryEl?.value ?? "fan";
    const tx = this._txEl?.value ?? "";
    const manufacturer = this._manufacturerEl?.value.trim() ?? "";
    const model = this._modelEl?.value.trim() ?? "";
    if (!name) {
      this._err = "Name is required";
      return;
    }
    if (!tx || tx.startsWith("(")) {
      this._err = "Pick a transmitter";
      return;
    }
    const payload = {
      name,
      category,
      transmitter: tx,
      manufacturer,
      model,
      discrete_speed_count: category === "fan" ? 3 : 0,
    };
    this._busy = true;
    try {
      if (editing) {
        await api.updateDevice({ device_id: editing.id, ...payload });
        store.pushToast("Updated", "ok");
      } else {
        await api.createDevice(payload);
        store.pushToast("Created", "ok");
      }
      store.closeDeviceDialog();
      const { devices } = await api.list();
      store.setDevices(devices ?? []);
    } catch (err) {
      this._err = (err as Error).message;
    } finally {
      this._busy = false;
    }
  }

  render() {
    const editing = store.deviceDialog.editing;
    return html`
      <dialog id="dlg" @close=${() => store.closeDeviceDialog()}>
        <h2>${editing ? "Edit device" : "Add device"}</h2>
        <div class="form-row">
          <label for="name">Name</label>
          <input id="name" placeholder="Bedroom fan" />
        </div>
        <div class="form-row">
          <label for="category">Category</label>
          <select id="category">
            ${CATEGORIES.map((c) => html`<option value=${c}>${c}</option>`)}
          </select>
        </div>
        <div class="form-row">
          <label for="manufacturer">Manufacturer (optional)</label>
          <input id="manufacturer" placeholder="Broadlink, ESPHome, ..." />
        </div>
        <div class="form-row">
          <label for="model">Model (optional)</label>
          <input id="model" placeholder="RM4 Pro, FRM97, ..." />
        </div>
        <div class="form-row">
          <label for="tx">Transmitter</label>
          <div class="tx-row">
            <select id="tx">
              <option>${this._txLoading ? "Loading…" : "(empty)"}</option>
            </select>
            <button
              class="secondary"
              type="button"
              @click=${() => this._loadTransmitters(editing?.transmitter_entity_ids ?? null)}
            >
              ↻
            </button>
          </div>
        </div>
        ${this._err ? html`<div class="err">${this._err}</div>` : ""}
        <div class="dialog-actions">
          <button class="secondary" type="button" @click=${this._cancel}>Cancel</button>
          <button type="button" @click=${this._save} ?disabled=${this._busy}>
            ${this._busy ? "Saving…" : "Save"}
          </button>
        </div>
      </dialog>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-device-dialog": RuneDeviceDialog;
  }
}
