// Domain types shared by the Lit SPA. These mirror the Python side
// in ``custom_components/rune/websocket_api.py`` and the device model
// in ``custom_components/rune/domain``. Keep field names identical.

export type DeviceCategory =
  "fan" | "climate" | "light" | "cover" | "media_player" | "switch" | "remote";

export interface PulseCommand {
  key: string;
  label?: string;
  category?: string;
  signal_category?: Record<string, unknown>;
  payload?: Record<string, unknown>;
  /** Set by the compact ``rune/list`` summary so the SPA can warn
   *  before sending a command that has no usable signal. */
  has_payload?: boolean;
}

export interface DeviceSummary {
  id: string;
  name: string;
  category: DeviceCategory;
  manufacturer?: string;
  model?: string;
  command_count: number;
  transmitter_entity_ids: string[];
  receiver_entity_ids?: string[];
  commands: PulseCommand[];
}

export interface RemoteSignal {
  id: string;
  alias?: string;
  fingerprint?: string;
  decoded_fingerprint?: string;
  hit_count: number;
  last_seen: string;
}

export interface Remote {
  id: string;
  label?: string;
  protocol_label?: string;
  signal_count: number;
  dismissed?: boolean;
  signals: RemoteSignal[];
}

export interface ActionBinding {
  id: string;
  name?: string;
  signal_id: string;
  min_hits: number;
  target: { kind: string };
}

export interface TxEntity {
  entity_id: string;
  name?: string;
  state: string;
  /** Optional area / room from the HA registry. */
  area?: string;
  /** Optional device friendly name from the HA device registry. */
  device_name?: string;
}

export interface RxEntity {
  entity_id: string;
  name?: string;
  state: string;
  /** Optional area / room from the HA registry. */
  area?: string;
  /** Optional device friendly name from the HA device registry. */
  device_name?: string;
  /**
   * ``true`` when the entity belongs to a Broadlink RM Pro / RM4 Pro
   * registered with HA's Broadlink integration. Drives the RF Learn
   * dialog's receiver filter — Broadlink-owned entities are valid
   * RF capture targets regardless of their domain prefix.
   */
  broadlink?: boolean;
}

export interface ListResponse {
  devices: DeviceSummary[];
}

export interface LearnResult {
  captured: {
    protocol_label?: string;
    signal_category: Record<string, unknown>;
    payload: Record<string, unknown>;
  };
  raw_timings: number[];
  carrier_frequency_hz: number;
}

/**
 * Compact view returned by ``rune/command/list``. The panel uses this
 * to render the per-command context menu (rename / re-learn /
 * delete) without paying the bandwidth cost of shipping every full
 * PulseCommand (raw timings can be several KB each).
 */
export interface CommandSummary {
  key: string;
  label?: string;
  category?: string;
  transport?: string;
  carrier_frequency_hz?: number;
  has_payload?: boolean;
  timings_count?: number;
  repeat_count?: number;
  send_count?: number;
}
