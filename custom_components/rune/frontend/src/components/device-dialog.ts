import { localized, msg, str } from "@lit/localize";
import { css, html, LitElement, nothing } from "lit";
import { customElement, state } from "lit/decorators.js";

import type { TemplateResult } from "lit";

import "@/components/ui/index.js";

import { api, refreshDevices, refreshReceiverEntities } from "@/api/bridge.js";
import { attachDialogFocus } from "@/components/ui/dialog-focus.js";
import { attachStoreController } from "@/state/store-controller.js";
import { store } from "@/state/store.js";
import { sharedStyles } from "@/styles/shared.js";
import { nonEmpty } from "@/utils/format.js";

import {
  entityOptions,
  IR_DOMAINS,
  requiredFields,
  RF_DOMAINS,
  visibleFields,
} from "./devices/dialog-schema.js";

import type { FieldDef, FormState } from "./devices/dialog-schema.js";
import type { AsyncLoader } from "@/components/ui/select.js";
import type { DeviceSummary } from "@/types.js";

const CATEGORY_LABEL: Record<string, () => ReturnType<typeof msg>> = {
  fan: () => msg(str`Fan`),
  climate: () => msg(str`Climate`),
  light: () => msg(str`Light`),
  cover: () => msg(str`Cover`),
  media_player: () => msg(str`Media player`),
  switch: () => msg(str`Switch`),
  remote: () => msg(str`Remote`),
};

const TRANSMITTER_KEYS = new Set(["ir_transmitter", "rf_transmitter", "transmitter"]);
const RECEIVER_KEYS = new Set(["ir_receiver", "rf_receiver", "receiver"]);

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
        grid-template-columns: 1fr;
        row-gap: var(--rune-space-3);
      }
      .grid > * {
        grid-column: 1 / -1;
      }
      .grid > ::slotted(*) {
        margin-bottom: 0;
      }
      .preview {
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
        color: var(--rune-danger-text);
        background: var(--rune-danger-soft);
        padding: var(--rune-space-2) var(--rune-space-3);
        border-radius: var(--rune-radius-sm);
        font-size: var(--rune-fs-xs);
        margin-top: var(--rune-space-2);
      }
    `,
  ];

  constructor() {
    super();
    attachStoreController(this);
    attachDialogFocus(this, () => {
      if (store.deviceDialog.open) store.closeDeviceDialog();
    });
  }

  @state() private _busy = false;
  @state() private _err = "";
  @state() private _form: FormState = { category: "fan" };
  private _lastEditingId: string | null = null;

  protected willUpdate(): void {
    const editing = store.deviceDialog.editing;
    const editingId = editing?.id ?? null;
    if (editingId !== this._lastEditingId) {
      this._lastEditingId = editingId;
      this._form = this._formFromEditing(editing);
    }
    // The dialog's receiver/transmitter selectors depend on the
    // store caches; make sure they're warm when the user opens the
    // dialog straight from the Devices tab (skipping Settings).
    if (store.deviceDialog.open && !store.hasReceiverEntitiesLoaded) {
      void refreshReceiverEntities();
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
  }

  private _onClose = (): void => {
    this._lastEditingId = null;
    this._err = "";
    store.closeDeviceDialog();
  };

  /** Returns an error message if the form is invalid, or ``null`` when
   *  validation passes. */
  private _validate(): string | null {
    const required = requiredFields(this._form);
    for (const f of required) {
      const v = this._form[f.key];
      if (v === undefined || v === null || v === "") {
        const labelStr = typeof f.label === "function" ? String(f.label()) : f.label;
        return msg(str`Field "${labelStr}" is required`);
      }
    }
    const irTx = String(this._form.ir_transmitter || "").trim();
    const rfTx = String(this._form.rf_transmitter || "").trim();
    if (!irTx && !rfTx) {
      return msg(str`At least one transmitter (IR or RF) is required`);
    }
    return null;
  }

  /** Convert the form state into a flat payload accepted by the API. */
  private _buildPayload(): Record<string, unknown> {
    const visible = visibleFields(this._form);
    const payload: Record<string, unknown> = {};
    for (const f of visible) {
      const v = this._form[f.key];
      if (v === undefined || v === "" || v === null) continue;
      payload[f.key] = v;
    }
    if (payload.category === "fan" && payload.discrete_speed_count === undefined) {
      payload.discrete_speed_count = 3;
    }
    const irTx = String(this._form.ir_transmitter || "").trim();
    const rfTx = String(this._form.rf_transmitter || "").trim();
    const irRx = String(this._form.ir_receiver || "").trim();
    const rfRx = String(this._form.rf_receiver || "").trim();
    const txList = nonEmpty(irTx, rfTx);
    const rxList = nonEmpty(irRx, rfRx);
    payload.transmitter_entity_ids = txList;
    payload.receiver_entity_ids = rxList;
    payload.transmitter = txList[0];
    if (rxList.length > 0) {
      payload.receiver = rxList[0];
    }
    return payload;
  }

  private async _submit(): Promise<void> {
    const editing = store.deviceDialog.editing;
    const payload = this._buildPayload();
    if (editing) {
      await api.updateDevice({ device_id: editing.id, ...payload });
      store.pushToast(msg(str`Updated`), "ok");
    } else {
      await api.createDevice(payload);
      store.pushToast(msg(str`Created`), "ok");
    }
    this._lastEditingId = null;
    store.closeDeviceDialog();
    await refreshDevices();
  }

  private async _save(): Promise<void> {
    const err = this._validate();
    if (err !== null) {
      this._err = err;
      return;
    }
    this._err = "";
    this._busy = true;
    try {
      await this._submit();
    } catch (e) {
      this._err = (e as Error).message;
    } finally {
      this._busy = false;
    }
  }

  private _loadTransmitters(acceptDomains?: ReadonlySet<string>): AsyncLoader {
    return async () => {
      const { transmitters } = await api.transmitters();
      return entityOptions(transmitters ?? [], undefined, acceptDomains);
    };
  }

  private _loadReceivers(acceptDomains?: ReadonlySet<string>): AsyncLoader {
    return async () => {
      const { receivers } = await api.receivers();
      return entityOptions(
        receivers ?? [],
        {
          value: "",
          label: msg(str`(no receivers)`),
          description: msg(str`Add an IR or RF receiver first`),
        },
        acceptDomains,
      );
    };
  }

  private _resolveOptions(field: FieldDef): AsyncLoader | undefined {
    if (field.kind !== "async-select") return undefined;
    if (field.key === "ir_transmitter" || field.key === "ir_receiver") {
      const loader = TRANSMITTER_KEYS.has(field.key)
        ? this._loadTransmitters(IR_DOMAINS)
        : this._loadReceivers(IR_DOMAINS);
      return loader;
    }
    if (field.key === "rf_transmitter" || field.key === "rf_receiver") {
      const loader = TRANSMITTER_KEYS.has(field.key)
        ? this._loadTransmitters(RF_DOMAINS)
        : this._loadReceivers(RF_DOMAINS);
      return loader;
    }
    if (TRANSMITTER_KEYS.has(field.key)) return this._loadTransmitters();
    if (RECEIVER_KEYS.has(field.key)) return this._loadReceivers();
    return field.loadOptions;
  }

  private _renderField(f: FieldDef): TemplateResult | typeof nothing {
    const value = this._form[f.key] ?? "";
    const helperNode = f.helper ? f.helper() : "";
    const placeholderNode = f.placeholder ? f.placeholder() : "";
    // ``<rune-input>`` delegates to ``<sl-input>`` which already paints a
    // trailing ``*`` on the label when ``required`` is set, so we skip the
    // manual asterisk here. ``<rune-select>`` renders its own label and
    // has no built-in required indicator, so we paint one ourselves.
    const inputLabel = f.label();
    const selectLabel = f.required
      ? html`${inputLabel} <span class="req" aria-hidden="true">*</span>`
      : inputLabel;
    switch (f.kind) {
      case "text":
        return html`
          <rune-input
            .label=${inputLabel}
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
            .label=${inputLabel}
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
            .label=${selectLabel}
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
            .label=${selectLabel}
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
    const label = (CATEGORY_LABEL[cat] ?? CATEGORY_LABEL.fan)();
    return html`
      <div class="preview">
        ${msg(html`HA will expose a <strong>${label}</strong> entity`)}${
          this._form.name ? html` ${msg(str` with name `)}<strong>${this._form.name}</strong>` : ""
        }${
          cat === "fan" && this._form.discrete_speed_count
            ? html` ${msg(str` and `)}<strong>${this._form.discrete_speed_count}</strong>
                ${msg(str`${this._form.discrete_speed_count === 1 ? msg(str`speed step`) : msg(str`speed steps`)}`)}`
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
      >
        <div
          slot="subtitle"
          style="font-family:var(--rune-font);font-size:var(--rune-fs-sm);color:var(--rune-text-muted);line-height:var(--rune-lh-normal);margin-bottom:var(--rune-space-3)"
        >
          ${msg(
            str`Define the device's category, name, and the emitter entity that will broadcast commands.`,
          )}
        </div>
        <div class="grid">
          ${visible.map((f) => this._renderField(f))}
          ${this._err ? html`<div class="err">${this._err}</div>` : nothing}
          ${this._renderPreview()}
        </div>
        <div slot="footer">
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
