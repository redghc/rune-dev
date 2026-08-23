import { css, html, LitElement, nothing } from "lit";
import { customElement, state } from "lit/decorators.js";

import type { TemplateResult } from "lit";

import "@/components/ui/index.js";

import { api } from "@/api/bridge.js";
import { store, subscribe } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";

import { requiredFields, visibleFields } from "./devices/dialog-schema.js";

import type { FieldDef, FormState } from "./devices/dialog-schema.js";
import type { AsyncLoader } from "@/components/ui/select.js";
import type { DeviceSummary, TxEntity } from "@/types.js";

@customElement("rune-device-dialog")
export class RuneDeviceDialog extends LitElement {
  static styles = [
    sharedStyles,
    css`
      :host {
        display: contents;
      }
      .grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0 var(--rune-space-3);
        row-gap: 0;
      }
      .grid > .full {
        grid-column: 1 / -1;
      }
      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: var(--rune-space-1);
        padding: var(--rune-space-1);
        border: 1px solid var(--rune-border);
        border-radius: var(--rune-radius-sm);
        background: var(--rune-surface);
        min-height: 34px;
        align-items: center;
        transition:
          box-shadow var(--rune-dur-fast) var(--rune-ease),
          border-color var(--rune-dur-fast) var(--rune-ease);
      }
      .chips:focus-within {
        border-color: var(--rune-primary);
        box-shadow: var(--rune-focus-ring);
      }
      .chips sl-tag::part(base) {
        cursor: default;
      }
      .chips sl-tag::part(remove-button) {
        color: var(--rune-text-muted);
      }
      .chip-input {
        flex: 1;
        min-width: 120px;
        border: 0;
        outline: none;
        background: transparent;
        color: var(--rune-text);
        font: inherit;
        font-size: var(--rune-fs-sm);
        padding: 2px 4px;
      }
      .preview {
        grid-column: 1 / -1;
        margin-top: var(--rune-space-3);
        padding: var(--rune-space-3);
        background: var(--rune-primary-soft);
        border-radius: var(--rune-radius-md);
        font-size: var(--rune-fs-sm);
        color: var(--rune-text);
      }
      .preview strong {
        color: var(--rune-primary-text);
        font-weight: var(--rune-fw-semibold);
      }
      .err {
        grid-column: 1 / -1;
        color: var(--rune-danger-text);
        background: var(--rune-danger-soft);
        padding: var(--rune-space-2) var(--rune-space-3);
        border-radius: var(--rune-radius-sm);
        font-size: var(--rune-fs-xs);
        margin-top: var(--rune-space-2);
      }
    `,
  ];

  @state() private _tick = 0;
  @state() private _busy = false;
  @state() private _err = "";
  @state() private _form: FormState = { category: "fan" };
  @state() private _chips: Record<string, string[]> = {};
  private _unsub: (() => void) | null = null;
  private _lastEditingId: string | null = null;
  private _returnFocusTo: HTMLElement | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    this._unsub = subscribe(() => this._tick++);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsub?.();
  }

  protected willUpdate(): void {
    const editing = store.deviceDialog.editing;
    const editingId = editing?.id ?? null;
    if (editingId !== this._lastEditingId) {
      this._lastEditingId = editingId;
      this._form = this._formFromEditing(editing);
      this._chips = this._chipsFromEditing(editing);
    }
  }

  private _formFromEditing(editing: DeviceSummary | null): FormState {
    if (!editing) return { category: "fan" };
    const dev = editing as DeviceSummary & Record<string, unknown>;
    return {
      category: editing.category,
      name: editing.name,
      manufacturer: editing.manufacturer ?? "",
      model: editing.model ?? "",
      transmitter: editing.transmitter_entity_ids?.[0] ?? "",
      discrete_speed_count: dev["discrete_speed_count"] ?? 3,
    };
  }

  private _chipsFromEditing(editing: DeviceSummary | null): Record<string, string[]> {
    if (!editing) return {};
    return {};
  }

  private _setField(key: string, value: unknown): void {
    this._form = { ...this._form, [key]: value };
    void this._tick;
  }

  private _onClose = (): void => {
    this._lastEditingId = null;
    this._err = "";
    store.closeDeviceDialog();
  };

  private _onShow = (): void => {
    // When sl-dialog opens, capture the currently focused element so
    // we can restore focus when it closes.
    this._returnFocusTo = (this.getRootNode() as Document | ShadowRoot)
      .activeElement as HTMLElement | null;
    queueMicrotask(() => {
      const dlg = this.renderRoot.querySelector("rune-dialog");
      const target = dlg?.querySelector<HTMLElement>(
        "input, select, sl-input, sl-select, textarea, button",
      );
      target?.focus();
    });
  };

  private _onAfterHide = (): void => {
    // After the close animation finishes, restore focus to the element
    // that triggered the dialog (or null if there was none).
    this._returnFocusTo?.focus();
    this._returnFocusTo = null;
    // Sync the store if the user closed the dialog via the X button.
    if (store.deviceDialog.open) store.closeDeviceDialog();
  };

  private async _save(): Promise<void> {
    this._err = "";
    const visible = visibleFields(this._form);
    const required = requiredFields(this._form);
    for (const f of required) {
      const v = this._form[f.key];
      if (v === undefined || v === null || v === "") {
        this._err = `Field "${f.label}" is required`;
        return;
      }
    }
    const editing = store.deviceDialog.editing;
    const payload: Record<string, unknown> = {};
    for (const f of visible) {
      const v = this._form[f.key];
      if (v === undefined || v === "" || v === null) continue;
      payload[f.key] = v;
    }
    // Append chip arrays.
    for (const [k, arr] of Object.entries(this._chips)) {
      if (arr.length > 0) payload[k] = arr;
    }
    if (payload.category === "fan" && payload.discrete_speed_count === undefined) {
      payload.discrete_speed_count = 3;
    }
    this._busy = true;
    try {
      if (editing) {
        await api.updateDevice({ device_id: editing.id, ...payload });
        store.pushToast("Updated", "ok");
      } else {
        await api.createDevice(payload);
        store.pushToast("Created", "ok");
      }
      this._lastEditingId = null;
      store.closeDeviceDialog();
      const { devices } = await api.list();
      store.setDevices(devices ?? []);
    } catch (err) {
      this._err = (err as Error).message;
    } finally {
      this._busy = false;
    }
  }

  private _loadTransmitters(): AsyncLoader {
    return async () => {
      const r = await api.transmitters();
      const txs = (r.transmitters ?? []) as TxEntity[];
      return txs.map((t) => ({
        value: t.entity_id,
        label: t.entity_id,
        description: t.state,
      }));
    };
  }

  private _loadReceivers(): AsyncLoader {
    return async () => {
      const r = await api.receivers();
      const rxs = (r.receivers ?? []) as TxEntity[];
      if (rxs.length === 0) {
        return [{ value: "", label: "(no receivers)", description: "Add an RF receiver first" }];
      }
      return rxs.map((t) => ({
        value: t.entity_id,
        label: t.entity_id,
        description: t.state,
      }));
    };
  }

  private _loadSensors(): AsyncLoader {
    // The current WS API doesn't expose a sensor-list endpoint, so we
    // return an empty list and rely on the user typing the entity_id
    // via the searchable select. Future: add ``rune/entity/list``.
    return async () => [];
  }

  private _resolveOptions(field: FieldDef): AsyncLoader | undefined {
    if (field.kind !== "async-select") return undefined;
    if (field.key === "transmitter") return this._loadTransmitters();
    if (field.key === "receiver") return this._loadReceivers();
    if (
      field.key === "temperature_sensor" ||
      field.key === "humidity_sensor" ||
      field.key === "power_sensor"
    ) {
      return this._loadSensors();
    }
    return field.loadOptions;
  }

  private _renderField(f: FieldDef): TemplateResult | typeof nothing {
    const value = this._form[f.key] ?? "";
    const common = f.required ? " * " : " ";
    switch (f.kind) {
      case "text":
        return html`
          <rune-input
            label=${f.label + common}
            icon=${f.icon ?? ""}
            placeholder=${f.placeholder ?? ""}
            helper=${f.helper ?? ""}
            .value=${String(value)}
            maxlength=${f.maxLength ?? null}
            ?required=${f.required ?? false}
            @rune-input=${(ev: CustomEvent<{ value: string }>) =>
              this._setField(f.key, ev.detail.value)}
          ></rune-input>
        `;
      case "number":
        return html`
          <rune-input
            label=${f.label + common}
            icon=${f.icon ?? ""}
            helper=${f.helper ?? ""}
            type="number"
            .value=${String(value)}
            min=${f.min ?? null}
            max=${f.max ?? null}
            step=${f.step ?? null}
            @rune-input=${(ev: CustomEvent<{ value: string }>) =>
              this._setField(f.key, ev.detail.value === "" ? null : Number(ev.detail.value))}
          ></rune-input>
        `;
      case "select":
        return html`
          <rune-select
            label=${f.label + common}
            icon=${f.icon ?? ""}
            helper=${f.helper ?? ""}
            .options=${f.options ?? []}
            .value=${String(value)}
            ?required=${f.required ?? false}
            @rune-change=${(ev: CustomEvent<{ value: string }>) =>
              this._setField(f.key, ev.detail.value)}
          ></rune-select>
        `;
      case "async-select":
        return html`
          <rune-select
            label=${f.label + common}
            icon=${f.icon ?? ""}
            helper=${f.helper ?? ""}
            placeholder=${f.placeholder ?? ""}
            ?searchable=${f.searchable ?? false}
            ?clearable=${f.clearable ?? false}
            .loadOptions=${this._resolveOptions(f)}
            .value=${String(value)}
            @rune-change=${(ev: CustomEvent<{ value: string }>) =>
              this._setField(f.key, ev.detail.value)}
          ></rune-select>
        `;
      case "chips":
        return this._renderChips(f);
      case "switch":
        return html`
          <rune-input
            label=${f.label + common}
            icon=${f.icon ?? ""}
            helper=${f.helper ?? ""}
            type="text"
            .value=${String(value ?? "")}
            @rune-input=${(ev: CustomEvent<{ value: string }>) =>
              this._setField(f.key, ev.detail.value)}
          ></rune-input>
        `;
      default:
        return nothing;
    }
  }

  private _renderChips(f: FieldDef): TemplateResult {
    const values = this._chips[f.key] ?? [];
    const onKey = (ev: KeyboardEvent): void => {
      if (ev.key === "Enter" || ev.key === ",") {
        ev.preventDefault();
        const target = ev.target as HTMLInputElement;
        const v = target.value.trim().replace(/,$/, "");
        if (!v) return;
        this._chips = {
          ...this._chips,
          [f.key]: [...values, v],
        };
        target.value = "";
      } else if (ev.key === "Backspace" && !values.length) {
        ev.preventDefault();
        const arr = [...values];
        arr.pop();
        this._chips = { ...this._chips, [f.key]: arr };
      }
    };
    return html`
      <div class="full">
        <label
          style="display:block;font-size:10px;font-weight:var(--rune-fw-semibold);color:var(--rune-text-muted);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:2px"
        >
          ${f.label}${f.required ? " *" : ""}
        </label>
        <div class="chips">
          ${values.map(
            (v, i) => html`
              <rune-chip
                variant="primary"
                closable
                @rune-chip-remove=${() => {
                  const arr = [...values];
                  arr.splice(i, 1);
                  this._chips = { ...this._chips, [f.key]: arr };
                }}
              >
                ${v}
              </rune-chip>
            `,
          )}
          <input
            class="chip-input"
            placeholder=${values.length === 0 ? (f.chipPlaceholder ?? "") : ""}
            @keydown=${onKey}
          />
        </div>
        ${
          f.helper
            ? html`<div
                style="font-size:var(--rune-fs-xs);color:var(--rune-text-muted);margin-top:var(--rune-space-1)"
              >
                ${f.helper}
              </div>`
            : nothing
        }
      </div>
    `;
  }

  private _renderPreview(): TemplateResult {
    const cat = this._form.category || "fan";
    const label =
      cat === "fan"
        ? "Fan"
        : cat === "climate"
          ? "Climate"
          : cat === "light"
            ? "Light"
            : cat === "cover"
              ? "Cover"
              : cat === "media_player"
                ? "Media player"
                : cat === "switch"
                  ? "Switch"
                  : "Remote";
    return html`
      <div class="preview">
        HA will expose a <strong>${label}</strong> entity${
          this._form.name ? html` named <strong>${this._form.name}</strong>` : ""
        }
        ${
          cat === "fan" && this._form.discrete_speed_count
            ? html` with
                <strong>${this._form.discrete_speed_count}</strong>
                speed step(s)`
            : nothing
        }
        ${
          cat === "media_player" && (this._chips.source_list ?? []).length > 0
            ? html` and
                <strong>${this._chips.source_list.length}</strong>
                source(s)`
            : nothing
        }
        ${
          cat === "remote" && this._form.power_sensor
            ? html` driven by
                <strong>${this._form.power_sensor}</strong>`
            : nothing
        }
        .
      </div>
    `;
  }

  protected render() {
    const editing = store.deviceDialog.editing;
    const open = store.deviceDialog.open;
    const visible = visibleFields(this._form);

    return html`
      <rune-dialog
        ?open=${open}
        size="large"
        label=${editing ? "Edit device" : "Add device"}
        @sl-show=${this._onShow}
        @sl-after-hide=${this._onAfterHide}
      >
        <div class="grid">
          ${visible.map((f) => this._renderField(f))}
          ${this._err ? html`<div class="err">${this._err}</div>` : nothing}
          ${this._renderPreview()}
        </div>
        <div slot="footer" style="display:flex;gap:var(--rune-space-2);justify-content:flex-end">
          <rune-button variant="secondary" icon="x" ?disabled=${this._busy} @click=${this._onClose}>
            Cancel
          </rune-button>
          <rune-button
            variant="primary"
            icon=${editing ? "device-floppy" : "plus"}
            ?loading=${this._busy}
            @click=${this._save}
          >
            ${editing ? "Save" : "Create"}
          </rune-button>
        </div>
      </rune-dialog>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "rune-device-dialog": RuneDeviceDialog;
  }
}
