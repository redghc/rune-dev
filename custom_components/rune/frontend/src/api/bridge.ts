// Typed wrappers around the WS API surface used by the SPA.

import { store } from "@/state/store.js";

import type {
  ActionBinding,
  DeviceSummary,
  LearnResult,
  ListResponse,
  Remote,
  RxEntity,
  TxEntity,
} from "@/types.js";

// postMessage bridge to the HA parent window.
//
// Mirrors the protocol defined in ``src/shim.ts``. Every call returns
// a promise; the parent replies with ``rune-bridge-result`` carrying
// the same numeric id. If no reply arrives within ``BRIDGE_TIMEOUT_MS``
// the promise rejects so the UI doesn't hang forever on a stuck bridge.
//
// On boot the parent posts a ``rune-init`` carrying the integration
// version + entry_id. We pick those up here so the Lit SPA doesn't have
// to hardcode either field.

const BRIDGE_TIMEOUT_MS = 8000;

// Bridge traffic is verbose enough to drown the console in production.
// Opt in with ``?rune-debug=1`` (or ``localStorage.runeDebug = "1"``) when
// chasing a flaky parent <-> iframe roundtrip.
const DEBUG = (() => {
  if (typeof window === "undefined") return false;
  try {
    if (localStorage.getItem("rune-debug") === "1") return true;
  } catch {
    /* ignore */
  }
  return new URLSearchParams(window.location.search).get("rune-debug") === "1";
})();
const dlog = DEBUG ? (...args: unknown[]) => console.warn("[rune-bridge]", ...args) : () => {};

interface PendingResolver {
  resolve: (value: unknown) => void;
  reject: (reason: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

const pending = new Map<number, PendingResolver>();
let nextId = 1;

interface BridgeResultMessage {
  type: "rune-bridge-result";
  id: number;
  result?: unknown;
  error?: string;
}

interface InitMessage {
  type: "rune-init";
  version?: string;
  entry_id?: string;
  locale?: string;
}

type IncomingMessage = Partial<BridgeResultMessage | InitMessage>;

window.addEventListener("message", (event: MessageEvent) => {
  const data = (event.data ?? {}) as IncomingMessage;
  if (!data) return;
  // ``rune-init`` is the bootstrap handshake from the parent shim —
  // it carries the integration version + entry_id. We only need to
  // hydrate fields the store doesn't already have right.
  if (data.type === "rune-init") {
    if (typeof data.version === "string" && data.version.length > 0) {
      store.version = data.version;
    }
    if (typeof data.entry_id === "string" && data.entry_id.length > 0) {
      store.entryId = data.entry_id;
    }
    if (typeof data.locale === "string" && data.locale.length > 0) {
      store.locale = data.locale;
    }
    return;
  }
  if (data.type !== "rune-bridge-result") return;
  if (typeof data.id !== "number") return;
  const r = pending.get(data.id);
  if (!r) return;
  pending.delete(data.id);
  if (typeof data.error === "string") {
    r.reject(new Error(data.error));
  } else if (data.error && typeof data.error === "object") {
    // Defensive: the shim flattens to a string today, but if it ever
    // forwards the HA envelope raw we already know how to read it.
    const e = data.error as { code?: unknown; message?: unknown };
    const code = typeof e.code === "string" ? e.code : "";
    const msg = typeof e.message === "string" ? e.message : "Unknown error";
    r.reject(new Error(code && code !== "unknown_error" ? `${code}: ${msg}` : msg));
  } else {
    r.resolve(data.result);
  }
});

function bridgeCall(payload: Record<string, unknown>): Promise<unknown> {
  const id = nextId++;
  return new Promise<unknown>((resolve, reject) => {
    const timer = setTimeout(() => {
      if (pending.has(id)) {
        pending.delete(id);
        console.warn(`[rune-bridge] timeout id=${id} payload=${JSON.stringify(payload)}`);
        reject(new Error("bridge timeout (no response from HA)"));
      }
    }, BRIDGE_TIMEOUT_MS);
    const resolver: PendingResolver = {
      timer,
      resolve: (v) => {
        clearTimeout(timer);
        dlog(`ok id=${id} result=${JSON.stringify(v)}`);
        resolve(v);
      },
      reject: (e) => {
        clearTimeout(timer);
        console.warn(`[rune-bridge] err id=${id} msg=${e.message}`);
        reject(e);
      },
    };
    pending.set(id, resolver);
    dlog(`-> id=${id} payload=${JSON.stringify(payload)}`);
    window.parent.postMessage({ type: "rune-bridge", id, ...payload }, "*");
  });
}

/** HA wraps every WS rejection as ``{code, message, translation_domain,
 *  translation_key}``. ``Error.message`` only catches the literal
 *  ``message`` field — which on older HA builds defaults to
 *  ``"Unknown error"`` when the integration forgets to set one. We
 *  flatten the envelope into a single readable string so the panel
 *  surfaces whatever the backend actually meant. */
function bridgeReject(err: unknown): never {
  if (err && typeof err === "object" && "message" in err) {
    const e = err as { code?: unknown; message?: unknown; translation_key?: unknown };
    const code = typeof e.code === "string" ? e.code : "";
    const msg = typeof e.message === "string" ? e.message : String(err);
    if (code && code !== "unknown_error") {
      throw new Error(`${code}: ${msg}`);
    }
    throw new Error(msg);
  }
  throw new Error(String(err));
}

/** Wrap a ``bridgeCall`` so the HA WS error envelope is flattened
 *  into a readable message before the caller's ``catch`` sees it. */
function bridgeWs<T>(payload: Record<string, unknown>): Promise<T> {
  return bridgeCall(payload).catch(bridgeReject) as Promise<T>;
}

export const api = {
  list: (): Promise<ListResponse> =>
    bridgeWs({ kind: "ws", message: { type: "rune/list" } }) as Promise<ListResponse>,

  getDevice: (id: string): Promise<{ device: DeviceSummary }> =>
    bridgeWs({
      kind: "ws",
      message: { type: "rune/device/get", device_id: id },
    }) as Promise<{ device: DeviceSummary }>,

  createDevice: (payload: Record<string, unknown>): Promise<{ device: DeviceSummary }> =>
    bridgeWs({
      kind: "ws",
      message: { type: "rune/device/create", ...payload },
    }) as Promise<{ device: DeviceSummary }>,

  updateDevice: (payload: Record<string, unknown>): Promise<{ device: DeviceSummary }> =>
    bridgeWs({
      kind: "ws",
      message: { type: "rune/device/update", ...payload },
    }) as Promise<{ device: DeviceSummary }>,

  deleteDevice: (id: string): Promise<{ ok: true }> =>
    bridgeWs({
      kind: "ws",
      message: { type: "rune/device/delete", device_id: id },
    }) as Promise<{ ok: true }>,

  learnCommand: (payload: Record<string, unknown>): Promise<LearnResult> =>
    bridgeWs({
      kind: "ws",
      message: { type: "rune/command/learn", ...payload },
    }) as Promise<LearnResult>,

  cancelLearnCommand: (deviceId: string, commandKey: string): Promise<{ cancelled: boolean }> =>
    bridgeWs({
      kind: "ws",
      message: {
        type: "rune/command/learn/cancel",
        device_id: deviceId,
        command_key: commandKey,
      },
    }) as Promise<{ cancelled: boolean }>,

  listSniffer: (): Promise<{ remotes: Remote[] }> =>
    bridgeWs({
      kind: "ws",
      message: { type: "rune/sniffer/list" },
    }) as Promise<{ remotes: Remote[] }>,

  dismissRemote: (remoteId: string): Promise<{ ok: true }> =>
    bridgeWs({
      kind: "ws",
      message: { type: "rune/sniffer/dismiss", remote_id: remoteId },
    }) as Promise<{ ok: true }>,

  listActions: (): Promise<{ actions: ActionBinding[] }> =>
    bridgeWs({
      kind: "ws",
      message: { type: "rune/action/list" },
    }) as Promise<{ actions: ActionBinding[] }>,

  transmitters: (): Promise<{ transmitters: TxEntity[] }> =>
    bridgeWs({
      kind: "ws",
      message: { type: "rune/transmitter/list" },
    }) as Promise<{ transmitters: TxEntity[] }>,

  receivers: (): Promise<{ receivers: RxEntity[] }> =>
    bridgeWs({
      kind: "ws",
      message: { type: "rune/receiver/list" },
    }) as Promise<{ receivers: RxEntity[] }>,

  sendCommand: (deviceId: string, commandKey: string): Promise<true> =>
    bridgeCall({
      kind: "service",
      domain: "rune",
      service: "send_command",
      service_data: { device_id: deviceId, command_key: commandKey },
    }) as Promise<true>,
};

/** Fetch the full device list and write it into the store. Used by every
 *  view that needs the list (initial load + after every mutation). */
export async function refreshDevices(): Promise<void> {
  const { devices } = await api.list();
  store.setDevices(devices ?? []);
}

/** Fetch receivers + transmitters and write them into the store.
 *
 *  The Learn dialog needs the receiver list to populate the entity
 *  selector. Until this commit the list only got populated when the
 *  user visited the Settings tab — opening the Learn dialog straight
 *  from the Devices view left the selector empty and the dialog
 *  stuck on Step 1. This helper fires whenever a dialog that
 *  depends on the list opens and the cache is cold.
 */
export async function refreshReceiverEntities(): Promise<void> {
  const [{ transmitters }, { receivers }] = await Promise.all([
    api.transmitters(),
    api.receivers(),
  ]);
  store.setTransmitters(transmitters ?? []);
  store.setReceivers(receivers ?? []);
  store.hasReceiverEntitiesLoaded = true;
}
