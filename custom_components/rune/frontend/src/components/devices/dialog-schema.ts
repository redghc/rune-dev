// Schema-driven field definitions for the device dialog.
//
// The dialog renders any number of fields from this schema, hiding /
// showing them reactively as the user changes ``category`` or other
// upstream values. Add a new field here once and every device creation
// / edit form picks it up automatically — no dialog code changes
// required.
//
// Localizable strings are stored as getter functions (e.g. ``label``)
// rather than plain strings so that ``msg()`` is re-evaluated on every
// render. That keeps the dialog fully reactive when the user switches
// locale — ``@localized()`` triggers ``requestUpdate()``, which calls
// the getters again with the current locale.

import { msg, str } from "@lit/localize";

import type { AsyncLoader, RuneSelectOption } from "@/components/ui/select.js";
import type { TemplateResult } from "lit";

export type FieldKind = "text" | "textarea" | "number" | "select" | "async-select";

export interface SelectOption {
  value: string;
  label: () => TemplateResult | string;
  description?: () => TemplateResult | string;
  icon?: string;
}

export interface FieldDef {
  /** Stable key — used to read/write the value from form state. */
  key: string;
  /** Human label rendered above the input. */
  label: () => TemplateResult | string;
  /** Helper text shown below the input. */
  helper?: () => TemplateResult | string;
  /** Tabler icon name (e.g. ``"device-gamepad"``). */
  icon?: string;
  kind: FieldKind;
  placeholder?: () => TemplateResult | string;
  required?: boolean;
  /** Show this field only when the predicate returns true. */
  visibleWhen?: (state: FormState) => boolean;

  // number
  min?: number;
  max?: number;
  step?: number;

  // text
  maxLength?: number;

  // select / async-select
  options?: SelectOption[];
  loadOptions?: AsyncLoader;
  searchable?: boolean;
  clearable?: boolean;
}

export interface FormState {
  category: string;
  [key: string]: unknown;
}

/** Fields rendered for every category. */
const COMMON_FIELDS: FieldDef[] = [
  {
    key: "name",
    label: () => msg(str`Name`),
    helper: () => msg(str`How the device appears in Home Assistant`),
    icon: "device-gamepad",
    kind: "text",
    placeholder: () => msg(str`Bedroom fan`),
    required: true,
    maxLength: 64,
  },
  {
    key: "category",
    label: () => msg(str`Category`),
    helper: () => msg(str`Determines which entities HA exposes`),
    icon: "category",
    kind: "select",
    required: true,
    options: [
      { value: "fan", label: () => msg(str`Fan`), icon: "fan" },
      { value: "climate", label: () => msg(str`Climate`), icon: "temperature" },
      { value: "light", label: () => msg(str`Light`), icon: "bulb" },
      { value: "cover", label: () => msg(str`Cover / Blinds`), icon: "blinds" },
      {
        value: "media_player",
        label: () => msg(str`Media player`),
        icon: "device-tv",
      },
      { value: "switch", label: () => msg(str`Switch / Outlet`), icon: "plug" },
      { value: "remote", label: () => msg(str`Generic remote`), icon: "remote" },
    ],
  },
  {
    key: "ir_transmitter",
    label: () => msg(str`IR Transmitter`),
    helper: () => msg(str`IR emitter entity that sends commands`),
    icon: "antenna-bars-5",
    kind: "async-select",
    searchable: true,
    clearable: true,
    placeholder: () => msg(str`Pick an IR emitter…`),
  },
  {
    key: "rf_transmitter",
    label: () => msg(str`RF Transmitter`),
    helper: () => msg(str`RF emitter entity that sends commands`),
    icon: "antenna-bars-5",
    kind: "async-select",
    searchable: true,
    clearable: true,
    placeholder: () => msg(str`Pick an RF emitter…`),
  },
  {
    key: "ir_receiver",
    label: () => msg(str`IR Receiver`),
    helper: () => msg(str`Optional — receiver for IR signals & learn`),
    icon: "antenna",
    kind: "async-select",
    searchable: true,
    clearable: true,
    placeholder: () => msg(str`(none)`),
  },
  {
    key: "rf_receiver",
    label: () => msg(str`RF Receiver`),
    helper: () => msg(str`Optional — receiver for RF signals & learn`),
    icon: "antenna",
    kind: "async-select",
    searchable: true,
    clearable: true,
    placeholder: () => msg(str`(none)`),
  },
  {
    key: "manufacturer",
    label: () => msg(str`Manufacturer`),
    icon: "building",
    kind: "text",
    placeholder: () => msg(str`Broadlink, ESPHome, …`),
    maxLength: 64,
  },
  {
    key: "model",
    label: () => msg(str`Model`),
    icon: "barcode",
    kind: "text",
    placeholder: () => msg(str`RM4 Pro, FRM97, …`),
    maxLength: 64,
  },
];

/** Category-specific extras. ``visibleWhen`` defaults to matching
 *  the field's own ``category`` key when omitted. */
const CATEGORY_FIELDS: FieldDef[] = [
  // ---- fan ----
  {
    key: "discrete_speed_count",
    label: () => msg(str`Speed steps`),
    helper: () => msg(str`How many discrete speed levels this fan exposes`),
    icon: "gauge",
    kind: "number",
    min: 1,
    max: 7,
    step: 1,
    visibleWhen: (s) => s.category === "fan",
  },
];

/** Full field set rendered by the dialog, in display order. */
export function getFields(): FieldDef[] {
  return [...COMMON_FIELDS, ...CATEGORY_FIELDS];
}

/** Returns only fields whose ``visibleWhen`` (if any) returns true for
 *  the given form state. */
export function visibleFields(state: FormState): FieldDef[] {
  return getFields().filter((f) => !f.visibleWhen || f.visibleWhen(state));
}

/** Collects the visible ``required`` fields — used by the dialog to
 *  decide whether Save can fire. */
export function requiredFields(state: FormState): FieldDef[] {
  return visibleFields(state).filter((f) => f.required);
}

/** Minimal contract for entity-shaped rows returned by the
 *  ``rune/transmitter/list`` and ``rune/receiver/list`` WS endpoints. */
export interface EntityLike {
  entity_id: string;
  name?: string;
  /** Optional area / room from the HA registry — surfaced as the
   *  "location" segment of the row sub-line. */
  area?: string;
  /** Optional device friendly name from the HA device registry —
   *  surfaced as the "type name" segment of the row sub-line.
   *  Falls back to the entity's object-id when the backend doesn't
   *  expose it (older HA cores, tests without a device registry). */
  device_name?: string;
}

/** Domain → human label + tabler icon. Drives the right-aligned tag
 *  in the rich row. Falls back to a generic entry for unknown
 *  domains. */
const DOMAIN_META: Record<string, { label: () => TemplateResult | string; icon: string }> = {
  remote: { label: () => msg(str`Radio Frequency`), icon: "antenna-bars-5" },
  infrared: { label: () => msg(str`Infrared`), icon: "antenna" },
  esphome: { label: () => msg(str`ESPHome`), icon: "wifi" },
};
const FALLBACK_META = { label: () => msg(str`Other`), icon: "broadcast" };

function domainOf(entityId: string): string {
  const dot = entityId.indexOf(".");
  return dot >= 0 ? entityId.slice(0, dot) : "";
}

/** Map entity rows to ``<rune-select>`` options. ``empty`` renders a
 *  single placeholder when the source list is empty (the receiver
 *  picker uses this to nudge the user to add hardware).
 *
 *  Each row carries four slots that mirror the entity picker shown in
 *  the design mockup:
 *    • ``label``     → entity friendly name (top line, bold; also
 *                      doubles as the device name in this domain since
 *                      each entity IS its own device)
 *    • ``description``→ breadcrumb sub-line ``location ▸ type-name``
 *    • ``id``        → entity_id shown as a third monospace line in
 *                      the dropdown
 *    • ``meta``      → right-aligned category tag (e.g. "Radio
 *                      Frequency"), derived from the entity domain
 *    • ``icon``      → tabler icon picked from the same domain map
 *
 *  ``area`` and ``model`` are optional — when the backend doesn't
 *  expose them yet, the row falls back to ``domain ▸ object-id``
 *  which is still informative. */
export function entityOptions(
  entities: readonly EntityLike[],
  empty?: RuneSelectOption,
): RuneSelectOption[] {
  if (entities.length === 0 && empty) return [empty];
  return entities.map((e) => {
    const domain = domainOf(e.entity_id);
    const meta = DOMAIN_META[domain] ?? FALLBACK_META;
    const location = (e.area ?? "").trim();
    const typeName = (e.device_name ?? "").trim();
    const breadcrumb =
      location && typeName ? `${location} ▸ ${typeName}` : location || typeName || "";
    return {
      value: e.entity_id,
      label: e.name || e.entity_id,
      description: breadcrumb,
      id: e.entity_id,
      icon: meta.icon,
      meta: meta.label,
    };
  });
}
