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
  if (typeof data.error === "string") r.reject(new Error(data.error));
  else r.resolve(data.result);
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
        console.debug(`[rune-bridge] ok id=${id} result=${JSON.stringify(v)}`);
        resolve(v);
      },
      reject: (e) => {
        clearTimeout(timer);
        console.warn(`[rune-bridge] err id=${id} msg=${e.message}`);
        reject(e);
      },
    };
    pending.set(id, resolver);
    console.debug(`[rune-bridge] -> id=${id} payload=${JSON.stringify(payload)}`);
    window.parent.postMessage({ type: "rune-bridge", id, ...payload }, "*");
  });
}

export const api = {
  list: (): Promise<ListResponse> =>
    bridgeCall({ kind: "ws", message: { type: "rune/list" } }) as Promise<ListResponse>,

  getDevice: (id: string): Promise<{ device: DeviceSummary }> =>
    bridgeCall({
      kind: "ws",
      message: { type: "rune/device/get", device_id: id },
    }) as Promise<{ device: DeviceSummary }>,

  createDevice: (payload: Record<string, unknown>): Promise<{ device: DeviceSummary }> =>
    bridgeCall({
      kind: "ws",
      message: { type: "rune/device/create", ...payload },
    }) as Promise<{ device: DeviceSummary }>,

  updateDevice: (payload: Record<string, unknown>): Promise<{ device: DeviceSummary }> =>
    bridgeCall({
      kind: "ws",
      message: { type: "rune/device/update", ...payload },
    }) as Promise<{ device: DeviceSummary }>,

  deleteDevice: (id: string): Promise<{ ok: true }> =>
    bridgeCall({
      kind: "ws",
      message: { type: "rune/device/delete", device_id: id },
    }) as Promise<{ ok: true }>,

  learnCommand: (payload: Record<string, unknown>): Promise<LearnResult> =>
    bridgeCall({
      kind: "ws",
      message: { type: "rune/command/learn", ...payload },
    }) as Promise<LearnResult>,

  listSniffer: (): Promise<{ remotes: Remote[] }> =>
    bridgeCall({
      kind: "ws",
      message: { type: "rune/sniffer/list" },
    }) as Promise<{ remotes: Remote[] }>,

  dismissRemote: (remoteId: string): Promise<{ ok: true }> =>
    bridgeCall({
      kind: "ws",
      message: { type: "rune/sniffer/dismiss", remote_id: remoteId },
    }) as Promise<{ ok: true }>,

  listActions: (): Promise<{ actions: ActionBinding[] }> =>
    bridgeCall({
      kind: "ws",
      message: { type: "rune/action/list" },
    }) as Promise<{ actions: ActionBinding[] }>,

  transmitters: (): Promise<{ transmitters: TxEntity[] }> =>
    bridgeCall({
      kind: "ws",
      message: { type: "rune/transmitter/list" },
    }) as Promise<{ transmitters: TxEntity[] }>,

  receivers: (): Promise<{ receivers: RxEntity[] }> =>
    bridgeCall({
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
