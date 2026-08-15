// Reactive shared store. Components import the store and subscribe via
// Lit's ``@state`` + a host-update on the AppShell. We keep the API
// deliberately small — list refreshes, dialog state, toast queue.

import type {
  ActionBinding,
  DeviceSummary,
  Remote,
  RxEntity,
  TxEntity,
} from "../types.js";

export type Section = "devices" | "sniffer" | "actions" | "settings";

export interface ToastMsg {
  id: number;
  text: string;
  kind?: "ok" | "err";
}

export interface DeviceDialogState {
  open: boolean;
  editing: DeviceSummary | null;
}

export interface LearnDialogState {
  open: boolean;
  deviceId: string | null;
  commandKey: string;
  status: string;
  captured: import("../types.js").LearnResult["captured"] | null;
  rawTimings: number[] | null;
  carrierHz: number | null;
}

export const store = {
  version: "0.3.2",
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
    commandKey: "",
    status: "Idle — click Start learn",
    captured: null,
    rawTimings: null,
    carrierHz: null,
  } as LearnDialogState,

  setSection(s: Section): void {
    this.section = s;
    notify();
  },

  pushToast(text: string, kind?: "ok" | "err"): void {
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

  openLearnDialog(deviceId: string, commandKey: string): void {
    this.learnDialog = {
      open: true,
      deviceId,
      commandKey,
      status: "Idle — click Start learn",
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
      commandKey: "",
      status: "Idle — click Start learn",
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
