"""Constants for the RUNE integration.

All magic numbers, default timeouts, capacity limits, and tuning knobs
live here. Domain code references these by import; it never inlines a
literal threshold.

Anything that varies per install (frequencies chosen by the user during
learn) is NOT a constant — it is stored on the device or signal record.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Domain identity
# ---------------------------------------------------------------------------

DOMAIN = "rune"

# Config-flow field names.
CONF_NAME = "name"
CONF_CATEGORY = "category"
CONF_TRANSMITTER = "transmitter"
CONF_RECEIVER = "receiver"
MANUFACTURER = "RUNE"
PANEL_TITLE = "RUNE"
PANEL_ICON = "mdi:remote"
PANEL_URL = "rune"

# Platform names forwarded to HA. Strings (not the HA ``Platform``
# enum) so the constant can be imported without HA core.
PLATFORMS = [
    "fan",
    "climate",
    "light",
    "cover",
    "media_player",
    "switch",
    "button",
    "remote",
]

# Storage keys (separate stores so corruption in one cannot damage others)
DEVICE_STORAGE_KEY = "rune.devices"
DEVICE_STORAGE_VERSION = 1

ACTION_STORAGE_KEY = "rune.actions"
ACTION_STORAGE_VERSION = 1

UNKNOWN_SIGNAL_STORAGE_KEY = "rune.unknown_signals"
UNKNOWN_SIGNAL_STORAGE_VERSION = 1

PROFILE_CACHE_STORAGE_KEY = "rune.profiles.cache"
PROFILE_CACHE_STORAGE_VERSION = 1

# ---------------------------------------------------------------------------
# Carrier frequencies (Hz)
# ---------------------------------------------------------------------------

DEFAULT_IR_CARRIER_HZ = 38_000
DEFAULT_RF_FREQUENCY_HZ = 433_920_000  # 433.92 MHz — the cheap-fan band

# ---------------------------------------------------------------------------
# Sniffer / signal capture
# ---------------------------------------------------------------------------

# Per-device rate cap on incoming captures.
SNIFER_RATE_LIMIT_PER_S = 10
# Hard cap on signals per single unknown remote (phantom-device defense,
# see HAIR GH #72). A full AC matrix tops out around 100 distinct signals.
SNIFER_MAX_SIGNALS_PER_DEVICE = 200
# Global cap across all unknown remotes.
SNIFER_MAX_TOTAL_SIGNALS = 20_000
# Signals with fewer hits than this AND older than this are evicted first.
SNIFER_EVICT_MIN_HITS = 5
SNIFER_EVICT_AGE_DAYS = 30
# Within this many ms of the previous capture from the same remote, the
# new capture is treated as a NEC ditto of the same physical press.
SNIFER_REPEAT_SUPPRESS_MS = 300
# Re-exported under the SIGNAL_* alias for symmetry with HAIR.
SIGNAL_REPEAT_SUPPRESS_MS = SNIFER_REPEAT_SUPPRESS_MS
# Push at most this many WS events per second for live signal feed.
SNIFER_WS_PUSH_RATE_LIMIT = 5
# Minimum captures with the same identity before we mint a new unknown
# remote (instead of dropping). Prevents one-off noise from creating rows.
SNIFER_CLUSTER_THRESHOLD = 3
# Re-exported under the SIGNAL_* alias for symmetry with HAIR's
# constant naming convention (kept for documentation cross-reference).
SIGNAL_CLUSTER_THRESHOLD = SNIFER_CLUSTER_THRESHOLD

# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------

# All hits for a single trigger chain must land within this many seconds
# of the FIRST hit in the chain. A press arriving after the window closes
# starts a fresh chain.
TRIGGER_HIT_RESET_WINDOW_S = 5.0
# Two captures from different receivers within this window of each other
# count as ONE press per (trigger, fingerprint). Sized against Sony SIRC's
# ~45ms inter-frame repeat cadence.
MULTI_RECEIVER_DEDUP_WINDOW_S = 0.100
# Window in which a capture arriving after our own send may be claimed
# as that send's echo (not a fresh signal).
MIRROR_ECHO_TTL_S = 2.5
# Window during which a beacon on an emitter is treated as our own send
# beacon, not a foreign integration's.
MIRROR_OWN_BEACON_WINDOW_S = 3.0

# ---------------------------------------------------------------------------
# Transmit gate (collision avoidance)
# ---------------------------------------------------------------------------

# Minimum gap between transmissions on DIFFERENT emitters (prevents
# cross-emitter hybrid signals).
EMITTER_STAGGER_GAP_S = 0.3
# Gap between back-to-back same-emitter sends (device queue pacing).
SEND_REPEAT_GAP_S = 0.1
# Edit-distance ratio below which an arriving capture is treated as a
# garbled echo of our own send and swallowed.
ECHO_GARBLE_SIMILARITY = 0.35

# ---------------------------------------------------------------------------
# Learn / capture flow
# ---------------------------------------------------------------------------

# Total timeout for any single learn phase (sweep OR capture).
LEARNING_TIMEOUT_S = 30.0
# Default user-facing learn timeout in the WS API (sniffer OR button learn).
DEFAULT_LEARN_TIMEOUT_S = 15.0
# Default per-session capture window used by the orchestrator.
DEFAULT_CAPTURE_TIMEOUT_S = 15.0

# ---------------------------------------------------------------------------
# Encoding (timing)
# ---------------------------------------------------------------------------

# Drop leading/trailing idle gaps longer than this (microseconds). Real
# inter-frame gaps are well below this; learning-timeout gaps are well
# above.
IDLE_TRIM_US = 20_000
# Bounded terminator added at the transmit boundary only. Must be small
# enough to fit uint16 (65,535 us) on Tuya/ZoSung blasters AND large
# enough to be dead air to any receiver. 50ms exceeds the Daikin 35ms
# frame gap, the largest in the SmartIR corpus.
TERMINATOR_SPACE_US = 50_000
# Broadlink RF tick resolution, microseconds per encoded pulse byte.
BROADLINK_RF_TICK_US = 32.84

# ---------------------------------------------------------------------------
# Identity / fingerprinting
# ---------------------------------------------------------------------------

# Timing-word magnitude (microseconds) above which a pair is "long".
# Calibrated against NEC data bits: 1690 us space = "long",
# 560 us mark = "long".
SL_THRESHOLD_US = 500
# Timing-word magnitude (microseconds) above which the S/L extractor
# treats it as an end-of-signal gap and stops. Must exceed the
# largest data space in any supported protocol; the NEC inter-frame
# gap (~40ms) is well above this, the Sony inter-frame gap (~45ms)
# also. Daikin's 35ms interior frame gap sits comfortably under.
GAP_THRESHOLD_US = 25_000
# Byte-hash quantization bin, in Pronto timing units (carrier cycles).
# Smaller bin = more sensitive to jitter; larger = more collisions.
PRONTO_BYTE_HASH_BIN = 20
# Number of S/L pairs from the preamble used for device grouping.
PRONTO_DEVICE_PREAMBLE_PAIRS = 1
# NEC-family address length in burst pairs (8 address bits = 8 pairs).
PRONTO_NEC_ADDRESS_PAIRS = 8

# ---------------------------------------------------------------------------
# Pulse repeat / send knobs
# ---------------------------------------------------------------------------

# Default NEC ditto count (per-protocol sub-frame repeats).
DEFAULT_REPEAT_COUNT = 1
# Default whole-frame loop count for a TX.
DEFAULT_SEND_COUNT = 1
# Hard upper bound on either knob. Mirrors HAIR's MAX_SEND_COUNT.
MAX_SEND_COUNT = 10
MAX_DITTO_COUNT = 20

# ---------------------------------------------------------------------------
# Power monitor
# ---------------------------------------------------------------------------

# Default hysteresis window — if wattage crosses these thresholds, the
# power monitor dispatches a verdict signal that platform entities pick up.
DEFAULT_POWER_OFF_BELOW_W = 1.0
DEFAULT_POWER_ON_ABOVE_W = 3.0

# ---------------------------------------------------------------------------
# Climate matrix
# ---------------------------------------------------------------------------

# Hard ceiling on cells in a single climate matrix to bound resource use.
MAX_CLIMATE_MATRIX_CELLS = 512

# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

WS_PREFIX = "rune"

# Bus event names (kept short for the event log).
EVENT_COMMAND_CAPTURED = f"{DOMAIN}_command_captured"
EVENT_CAPTURE_TIMEOUT = f"{DOMAIN}_capture_timeout"
EVENT_CAPTURE_ERROR = f"{DOMAIN}_capture_error"
EVENT_SIGNAL_DETECTED = f"{DOMAIN}_signal_detected"
EVENT_SIGNAL_UPDATED = f"{DOMAIN}_signal_updated"
EVENT_ACTION_FIRED = f"{DOMAIN}_action_fired"
EVENT_POWER_VERDICT = f"{DOMAIN}_power_verdict"

# Mirror synthetic device (logs every HA-originated TX).
MIRROR_DEVICE_ID = "rune-mirror"
MIRROR_DEVICE_LABEL = "Mirror"
MIRROR_UNKNOWN_SEND_FP_PREFIX = "mirror-unknown::"
