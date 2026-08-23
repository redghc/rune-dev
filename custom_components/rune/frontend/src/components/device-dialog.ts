import { localized, msg, str } from "@lit/localize";
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
@localized()
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
    }
  }

  private _formFromEditing(editing: DeviceSummary | null): FormState {
    if (!editing) return { category: "fan" };
    const dev = editing as DeviceSummary & Record<string, unknown>;
    const txs = editing.transmitter_entity_ids ?? [];
    const rxs = editing.receiver_entity_ids ?? [];
    return {
      category: editing.category,
      name: editing.name,
      manufacturer: editing.manufacturer ?? "",
      model: editing.model ?? "",
      ir_transmitter: txs[0] ?? "",
      rf_transmitter: txs[1] ?? "",
      ir_receiver: rxs[0] ?? "",
      rf_receiver: rxs[1] ?? "",
      discrete_speed_count: dev["discrete_speed_count"] ?? 3,
    };
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

  private _onShow = (ev: Event): void => {
    // Only react to the dialog's own lifecycle events. Shoelace popups
    // (e.g. ``<sl-select>`` dropdowns) emit composed ``sl-show`` /
    // ``sl-after-hide`` events that bubble up to this host and would
    // otherwise steal focus or close the dialog when a select option
    // is picked.
    if (ev.target !== ev.currentTarget) return;
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

  private _onAfterHide = (ev: Event): void => {
    if (ev.target !== ev.currentTarget) return;
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
        const labelStr = typeof f.label === "function" ? String(f.label()) : f.label;
        this._err = msg(str`Field "${labelStr}" is required`);
        return;
      }
    }

    const irTx = String(this._form.ir_transmitter || "").trim();
    const rfTx = String(this._form.rf_transmitter || "").trim();
    if (!irTx && !rfTx) {
      this._err = msg(str`At least one transmitter (IR or RF) is required`);
      return;
    }

    const editing = store.deviceDialog.editing;
    const payload: Record<string, unknown> = {};
    for (const f of visible) {
      const v = this._form[f.key];
      if (v === undefined || v === "" || v === null) continue;
      payload[f.key] = v;
    }
    if (payload.category === "fan" && payload.discrete_speed_count === undefined) {
      payload.discrete_speed_count = 3;
    }

    const irRx = String(this._form.ir_receiver || "").trim();
    const rfRx = String(this._form.rf_receiver || "").trim();
    const txList = [irTx, rfTx].filter(Boolean);
    const rxList = [irRx, rfRx].filter(Boolean);
    payload.transmitter_entity_ids = txList;
    payload.receiver_entity_ids = rxList;
    payload.transmitter = txList[0];
    if (rxList.length > 0) {
      payload.receiver = rxList[0];
    }

    this._busy = true;
    try {
      if (editing) {
        await api.updateDevice({ device_id: editing.id, ...payload });
        store.pushToast(msg(str`Updated`), "ok");
      } else {
        await api.createDevice(payload);
        store.pushToast(msg(str`Created`), "ok");
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
        label: t.name || t.entity_id,
        description: t.entity_id,
      }));
    };
  }

  private _loadReceivers(): AsyncLoader {
    return async () => {
      const r = await api.receivers();
      const rxs = (r.receivers ?? []) as TxEntity[];
      if (rxs.length === 0) {
        return [
          {
            value: "",
            label: msg(str`(no receivers)`),
            description: msg(str`Add an IR or RF receiver first`),
          },
        ];
      }
      return rxs.map((t) => ({
        value: t.entity_id,
        label: t.name || t.entity_id,
        description: t.entity_id,
      }));
    };
  }

  private _resolveOptions(field: FieldDef): AsyncLoader | undefined {
    if (field.kind !== "async-select") return undefined;
    if (
      field.key === "ir_transmitter" ||
      field.key === "rf_transmitter" ||
      field.key === "transmitter"
    ) {
      return this._loadTransmitters();
    }
    if (field.key === "ir_receiver" || field.key === "rf_receiver" || field.key === "receiver") {
      return this._loadReceivers();
    }
    return field.loadOptions;
  }

  private _renderField(f: FieldDef): TemplateResult | typeof nothing {
    const value = this._form[f.key] ?? "";
    const labelNode = f.required ? html`${f.label()} <span aria-hidden="true">*</span>` : f.label();
    const helperNode = f.helper ? f.helper() : "";
    const placeholderNode = f.placeholder ? f.placeholder() : "";
    switch (f.kind) {
      case "text":
        return html`
          <rune-input
            .label=${labelNode}
            icon=${f.icon ?? ""}
            .placeholder=${placeholderNode}
            .helper=${helperNode}
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
            .label=${labelNode}
            icon=${f.icon ?? ""}
            .helper=${helperNode}
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
            .label=${labelNode}
            icon=${f.icon ?? ""}
            .helper=${helperNode}
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
            .label=${labelNode}
            icon=${f.icon ?? ""}
            .helper=${helperNode}
            .placeholder=${placeholderNode}
            ?searchable=${f.searchable ?? false}
            ?clearable=${f.clearable ?? false}
            .loadOptions=${this._resolveOptions(f)}
            .value=${String(value)}
            @rune-change=${(ev: CustomEvent<{ value: string }>) =>
              this._setField(f.key, ev.detail.value)}
          ></rune-select>
        `;
      default:
        return nothing;
    }
  }

  private _renderPreview(): TemplateResult {
    const cat = this._form.category || "fan";
    const label =
      cat === "fan"
        ? msg(str`Fan`)
        : cat === "climate"
          ? msg(str`Climate`)
          : cat === "light"
            ? msg(str`Light`)
            : cat === "cover"
              ? msg(str`Cover`)
              : cat === "media_player"
                ? msg(str`Media player`)
                : cat === "switch"
                  ? msg(str`Switch`)
                  : msg(str`Remote`);
    return html`
      <div class="preview">
        ${msg(html`HA will expose a <strong>${label}</strong> entity`)}${
          this._form.name ? html` ${msg(str` named `)}<strong>${this._form.name}</strong>` : ""
        }${
          cat === "fan" && this._form.discrete_speed_count
            ? html` ${msg(str` with `)}<strong>${this._form.discrete_speed_count}</strong>
                ${msg(str`speed step(s)`)}`
            : nothing
        }.
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
        .label=${editing ? msg(str`Edit device`) : msg(str`Add device`)}
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
            ${msg(str`Cancel`)}
          </rune-button>
          <rune-button
            variant="primary"
            icon=${editing ? "device-floppy" : "plus"}
            ?loading=${this._busy}
            @click=${this._save}
          >
            ${editing ? msg(str`Save`) : msg(str`Create`)}
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
