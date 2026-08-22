// Schema-driven field definitions for the device dialog.
//
// The dialog renders any number of fields from this schema, hiding /
// showing them reactively as the user changes ``category`` or other
// upstream values. Add a new field here once and every device creation
// / edit form picks it up automatically — no dialog code changes
// required.

import type { AsyncLoader } from "@/components/ui/select.js";

export type FieldKind =
  "text" | "textarea" | "number" | "select" | "async-select" | "chips" | "switch";

export interface SelectOption {
  value: string;
  label: string;
  description?: string;
  icon?: string;
}

export interface FieldDef {
  /** Stable key — used to read/write the value from form state. */
  key: string;
  /** Human label rendered above the input. */
  label: string;
  /** Helper text shown below the input. */
  helper?: string;
  /** Tabler icon name (e.g. ``"device-gamepad"``). */
  icon?: string;
  kind: FieldKind;
  placeholder?: string;
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

  // chips
  chipPlaceholder?: string;
}

export interface FormState {
  category: string;
  [key: string]: unknown;
}

/** Fields rendered for every category. */
const COMMON_FIELDS: FieldDef[] = [
  {
    key: "name",
    label: "Name",
    helper: "How the device appears in Home Assistant",
    icon: "device-gamepad",
    kind: "text",
    placeholder: "Bedroom fan",
    required: true,
    maxLength: 64,
  },
  {
    key: "category",
    label: "Category",
    helper: "Determines which entities HA exposes",
    icon: "category",
    kind: "select",
    required: true,
    options: [
      { value: "fan", label: "Fan", icon: "fan" },
      { value: "climate", label: "Climate", icon: "temperature" },
      { value: "light", label: "Light", icon: "bulb" },
      { value: "cover", label: "Cover / Blinds", icon: "blinds" },
      { value: "media_player", label: "Media player", icon: "device-tv" },
      { value: "switch", label: "Switch / Outlet", icon: "plug" },
      { value: "remote", label: "Generic remote", icon: "remote" },
    ],
  },
  {
    key: "transmitter",
    label: "Transmitter",
    helper: "IR / RF emitter entity that sends commands",
    icon: "antenna-bars-5",
    kind: "async-select",
    required: true,
    searchable: true,
    clearable: false,
    placeholder: "Pick an emitter…",
  },
  {
    key: "receiver",
    label: "Receiver",
    helper: "Optional — needed for cover / learn workflows",
    icon: "antenna",
    kind: "async-select",
    searchable: true,
    clearable: true,
    placeholder: "(none)",
  },
  {
    key: "manufacturer",
    label: "Manufacturer",
    icon: "building",
    kind: "text",
    placeholder: "Broadlink, ESPHome, …",
    maxLength: 64,
  },
  {
    key: "model",
    label: "Model",
    icon: "barcode",
    kind: "text",
    placeholder: "RM4 Pro, FRM97, …",
    maxLength: 64,
  },
];

/** Category-specific extras. ``visibleWhen`` defaults to matching
 *  the field's own ``category`` key when omitted. */
const CATEGORY_FIELDS: FieldDef[] = [
  // ---- fan ----
  {
    key: "discrete_speed_count",
    label: "Speed steps",
    helper: "How many discrete speed levels this fan exposes",
    icon: "gauge",
    kind: "number",
    min: 1,
    max: 7,
    step: 1,
    visibleWhen: (s) => s.category === "fan",
  },
  {
    key: "speed_mode",
    label: "Speed mode",
    helper: "Hybrid sends both step + percent commands",
    icon: "adjustments",
    kind: "select",
    visibleWhen: (s) => s.category === "fan",
    options: [
      { value: "hybrid", label: "Hybrid (recommended)", description: "Steps + percent" },
      { value: "discrete", label: "Discrete only", description: "Just the steps" },
      { value: "percent", label: "Percent only", description: "Smooth percentage" },
    ],
  },

  // ---- climate ----
  {
    key: "climate_matrix",
    label: "Full HVAC matrix",
    helper: "Generate every (mode × fan) × (on/off) combo",
    icon: "matrix",
    kind: "switch",
    visibleWhen: (s) => s.category === "climate",
  },
  {
    key: "temperature_sensor",
    label: "Temperature sensor",
    helper: "Optional — drives current temp on the climate entity",
    icon: "temperature",
    kind: "async-select",
    searchable: true,
    clearable: true,
    placeholder: "(none)",
    visibleWhen: (s) => s.category === "climate",
  },
  {
    key: "humidity_sensor",
    label: "Humidity sensor",
    icon: "droplet",
    kind: "async-select",
    searchable: true,
    clearable: true,
    placeholder: "(none)",
    visibleWhen: (s) => s.category === "climate",
  },

  // ---- media_player ----
  {
    key: "source_list",
    label: "Sources",
    helper: "Press Enter to add each source name",
    icon: "list",
    kind: "chips",
    chipPlaceholder: "HDMI1, Bluetooth, …",
    visibleWhen: (s) => s.category === "media_player",
  },

  // ---- remote (power-aware) ----
  {
    key: "power_sensor",
    label: "Power sensor",
    helper: "W sensor — used to detect real on/off state",
    icon: "bolt",
    kind: "async-select",
    searchable: true,
    clearable: true,
    placeholder: "(none)",
    visibleWhen: (s) => s.category === "remote",
  },
  {
    key: "power_off_below_w",
    label: "Off threshold (W)",
    helper: "Device is off when reading drops below this",
    icon: "battery-3",
    kind: "number",
    min: 0,
    max: 5000,
    step: 1,
    visibleWhen: (s) => s.category === "remote",
  },
  {
    key: "power_on_above_w",
    label: "On threshold (W)",
    helper: "Device is on when reading rises above this",
    icon: "battery-4",
    kind: "number",
    min: 0,
    max: 5000,
    step: 1,
    visibleWhen: (s) => s.category === "remote",
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
