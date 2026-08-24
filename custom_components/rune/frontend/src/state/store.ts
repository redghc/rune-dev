// Reactive shared store. Components import the store and subscribe via
// Lit's ``@state`` + a host-update on the AppShell. We keep the API
// deliberately small — list refreshes, dialog state, toast queue.

import type {
  ActionBinding,
  DeviceSummary,
  LearnResult,
  Remote,
  RxEntity,
  TxEntity,
} from "@/types.js";

export type Section = "devices" | "sniffer" | "actions" | "settings";

export interface ToastMsg {
  id: number;
  text: string | unknown;
  kind?: "ok" | "err";
}

export interface DeviceDialogState {
  open: boolean;
  editing: DeviceSummary | null;
}

export type LearnStatus =
  | { kind: "idle" }
  | { kind: "capturing" }
  | { kind: "captured"; protocol: string; carrierHz: number }
  | { kind: "no_signal" }
  | { kind: "failed"; message: string };

export type LearnStep = "pick" | "capture" | "review";

export interface LearnDialogState {
  open: boolean;
  deviceId: string | null;
  step: LearnStep;
  commandKey: string;
  commandLabel: string;
  status: LearnStatus;
  captured: LearnResult["captured"] | null;
  rawTimings: number[] | null;
  carrierHz: number | null;
}

export const store = {
  version: "0.4.0",
  entryId: "" as string,
  locale: "" as string,
  section: "devices" as Section,
  devices: [] as DeviceSummary[],
  remotes: [] as Remote[],
  actions: [] as ActionBinding[],
  transmitters: [] as TxEntity[],
  receivers: [] as RxEntity[],
  toasts: [] as ToastMsg[],
  deviceDialog: { open: false, editing: null } as DeviceDialogState,
  learnDialog: {
    open: false,
    deviceId: null,
    step: "pick" as LearnStep,
    commandKey: "",
    commandLabel: "",
    status: { kind: "idle" } as LearnStatus,
    captured: null,
    rawTimings: null,
    carrierHz: null,
  } as LearnDialogState,

  setSection(s: Section): void {
    this.section = s;
    notify();
  },

  pushToast(text: string | unknown, kind?: "ok" | "err"): void {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    this.toasts = [...this.toasts, { id, text, kind }];
    notify();
    setTimeout(() => {
      this.toasts = this.toasts.filter((t) => t.id !== id);
      notify();
    }, 2400);
  },

  openDeviceDialog(d: DeviceSummary | null = null): void {
    this.deviceDialog = { open: true, editing: d };
    notify();
  },

  closeDeviceDialog(): void {
    this.deviceDialog = { open: false, editing: null };
    notify();
  },

  openLearnDialog(deviceId: string, commandKey = "", commandLabel = ""): void {
    const hasKey = commandKey.trim().length > 0;
    this.learnDialog = {
      open: true,
      deviceId,
      step: hasKey ? "capture" : "pick",
      commandKey: commandKey.trim(),
      commandLabel: commandLabel.trim(),
      status: { kind: "idle" },
      captured: null,
      rawTimings: null,
      carrierHz: null,
    };
    notify();
  },

  closeLearnDialog(): void {
    this.learnDialog = {
      open: false,
      deviceId: null,
      step: "pick",
      commandKey: "",
      commandLabel: "",
      status: { kind: "idle" },
      captured: null,
      rawTimings: null,
      carrierHz: null,
    };
    notify();
  },

  setLearnStep(step: LearnStep): void {
    if (this.learnDialog.step === step) return;
    this.learnDialog = { ...this.learnDialog, step };
    notify();
  },

  resetLearnCapture(): void {
    this.learnDialog = {
      ...this.learnDialog,
      status: { kind: "idle" },
      captured: null,
      rawTimings: null,
      carrierHz: null,
    };
    notify();
  },

  updateLearn(patch: Partial<LearnDialogState>): void {
    this.learnDialog = { ...this.learnDialog, ...patch };
    notify();
  },

  setDevices(d: DeviceSummary[]): void {
    this.devices = d;
    notify();
  },

  setRemotes(r: Remote[]): void {
    this.remotes = r;
    notify();
  },

  setActions(a: ActionBinding[]): void {
    this.actions = a;
    notify();
  },

  setTransmitters(t: TxEntity[]): void {
    this.transmitters = t;
    notify();
  },

  setReceivers(r: RxEntity[]): void {
    this.receivers = r;
    notify();
  },
};

// ---- subscriber plumbing ----

type Listener = () => void;
const listeners = new Set<Listener>();

export function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function notify(): void {
  for (const fn of listeners) fn();
}

/** Surface an Error (or unknown thrown value) as an error toast. Pass
 *  a ``prefix`` (already-localized ``msg(...)`` template) to give the
 *  user context — e.g. ``reportError(err, msg(str`Load devices`))``
 *  renders as ``"Load devices: <message>"``. */
export function reportError(err: unknown, prefix?: string | unknown): void {
  const message = err instanceof Error ? err.message : String(err);
  const text = prefix !== undefined && prefix !== "" ? `${prefix}: ${message}` : message;
  store.pushToast(text, "err");
}
