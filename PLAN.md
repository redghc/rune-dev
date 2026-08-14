# RUNE — Remote Universal Network Engine

## Architecture & Implementation Plan (v2)

---

## Implementation Status

> **Target HA**: 2026.6+ only
> **Frontend v1**: Custom SPA panel (`ha-panel-rune`)

| Phase | Scope                                                                 | Status                          |
| ----- | --------------------------------------------------------------------- | ------------------------------- |
| 0     | Skeleton: manifest, const, enums, errors, time, models                | ✅ done (56 tests, 97% cov)     |
| 1     | Pure domain logic: encoding, identity, mappers, signal, triggers      | ✅ done (187 tests, 97% cov)    |
| 2     | Ports + Repositories (storage adapters + migrations)                  | ✅ done (51 new tests, 97% cov) |
| 3     | Transmitters + Receivers (native IR/RF, Broadlink, ESPHome) | ✅ done (41 new tests, 96% cov) |
| 4     | Capture + Sniffer + Power monitor + TX gate        | ✅ done (65 new tests, 91% cov) |
| 5     | Platforms (fan, climate, light, cover, media, switch, button, remote) | ✅ done (49 new tests, 91% cov) |
| 6     | Config flow + Options + WebSocket API               | ✅ done (MVP-ready, 16 new tests, 91% cov) |
| 7     | Profiles + Snapshot import/export + SmartIR compat                    | ⏳ pending                      |
| 8     | Hardening (diagnostics, README, HACS, quality scale)                  | ⏳ pending                      |

### Phase 0 — Detailed Progress

- [x] Plan written
- [x] Repo init + manifest.json
- [x] `const.py` with all magic numbers
- [x] `domain/enums.py`
- [x] `domain/errors.py`
- [x] `domain/time.py`
- [x] `domain/models.py` (with to_dict/from_dict)
- [x] First pytest run passing on domain — **56 tests, 97% coverage**

### Phase 1 — Detailed Progress

- [x] `domain/encoding/pronto.py` — Pronto hex ⇄ raw timings (round-trip)
- [x] `domain/encoding/broadlink.py` — LIRC ⇄ Broadlink pack + base64 + RF packet decode
- [x] `domain/encoding/timing.py` — trim_idle + bounded terminator
- [x] `domain/identity/signal_identity.py` — 3-tier matcher (decoded > byte_hash > S/L)
- [x] `domain/identity/byte_hash.py` — Pronto byte quantization
- [x] `domain/identity/sl_pattern.py` — short/long fingerprint + NEC address extraction
- [x] `domain/mappers/speed_mapper.py` — discrete ⇄ % ⇄ named (HA convention)
- [x] `domain/signal/normalize.py` — raw timings → NormalizedSignal
- [x] `domain/signal/matcher.py` — tier-by-tier lookup across unknown remotes
- [x] `domain/signal/quality.py` — split repeats + consensus + clean_frame
- [x] `domain/triggers/engine.py` — min_hits + reset window + receiver scope + multi-receiver dedup
- [x] Unit tests ≥95% coverage — **187 tests, 97% coverage**

### Phase 2 — Detailed Progress

- [x] `ports/clock.py` — `ClockPort` (wall + monotonic, frozen variant)
- [x] `ports/repository.py` — `DeviceRepository`, `ActionRepository`, `SignalRepository`
- [x] `ports/transmitter.py` — `TransmitterPort`
- [x] `ports/receiver.py` — `ReceiverPort` + `CapturedPulse` DTO
- [x] `ports/power_monitor.py` — `PowerMonitorPort` + `PowerVerdict`
- [x] `adapters/clock.py` — `SystemClockAdapter`, `FrozenClockAdapter`
- [x] `adapters/storage/memory.py` — in-memory repos for tests
- [x] `adapters/storage/ha_store.py` — HA Store-backed repos (3 separate stores)
- [x] `migrations.py` — pure-function migration chain + decorators
- [x] Unit tests ≥90% coverage — **238 tests, 97% coverage** (HA-Store contract skipped when HA not installed)

### Phase 3 — Detailed Progress
- [x] `adapters/transmitters/base.py` — shared `prepare_timings`, encoder dispatch
- [x] `adapters/transmitters/native_ir.py` — `infrared.async_send_command` + ProntoCommand wrapper
- [x] `adapters/transmitters/native_rf.py` — `radio_frequency.async_send_command` + RadioFrequencyCommand
- [x] `adapters/transmitters/broadlink_ir.py` — Pronto → Broadlink pack → base64 (dual path: native IR or legacy service)
- [x] `adapters/transmitters/broadlink_rf.py` — raw timings → `broadlink.send_packet` (or native RF helper)
- [x] `adapters/transmitters/esphome_ir.py` — Pronto → ESPHome legacy service (or native IR helper)
- [x] `adapters/transmitters/esphome_rf.py` — raw timings → ESPHome legacy service (or native RF helper)
- [x] `adapters/transmitters/mock.py` — in-process capture for tests
- [x] `adapters/transmitters/factory.py` — `entity_id` → adapter
- [x] `adapters/receivers/native_ir.py` — `infrared.async_subscribe_receiver`
- [x] `adapters/receivers/broadlink_rf.py` — two-phase sweep + capture flow
- [x] `adapters/receivers/esphome_legacy_ir.py` — `esphome.remote_received` event bus
- [x] `adapters/receivers/mock.py` — in-process capture for tests
- [x] `adapters/receivers/factory.py` — `entity_id` → adapter
- [x] Tests — **279 passed, 12 skipped (HA-only contracts), 96% coverage**

### Phase 4 — Detailed Progress
- [x] `adapters/capture/orchestrator.py` — `CaptureOrchestrator` (asyncio.Lock + listener notifications + HA bus events)
- [x] `adapters/capture/providers.py` — `CaptureProvider` ABC + `MockProvider`
- [x] `sniffer/rate_limiter.py` — per-device token bucket (`TokenBucket` + `RateLimiter`)
- [x] `sniffer/capacity.py` — per-device + global caps with age/hit eviction
- [x] `sniffer/mirror.py` — `MirrorLog` (TX history + garbled-echo claim) + `build_mirror_remote`
- [x] `sniffer/engine.py` — `SnifferEngine` (repeat suppression → rate limit → echo swallow → matcher → bump/mint → capacity caps)
- [x] `adapters/tx_gate.py` — `TxGate` (emitter stagger + same-emitter pacing + mirror entry stamping)
- [x] `adapters/power_monitor.py` — `HAPowerMonitor` (state-change listener + debounce) + `InMemoryPowerMonitor` + `classify_reading`
- [x] Tests — **344 passed, 12 skipped (HA-only contracts), 91% coverage**

### Phase 5 — Detailed Progress
- [x] `platforms/_base.py` — `RunePlatformBase` mixin (TX helpers + device_info)
- [x] `platforms/_coordinator.py` — `DevicePlatformCoordinator` (TX dispatch + action dispatch + power-monitor bootstrap)
- [x] `platforms/button.py` — `RunePulseButtonEntity` (one button per PulseCommand)
- [x] `platforms/fan.py` — `RuneFanEntity` with `SpeedMapper` (discrete/%/hybrid, turn_on/off, set_percentage)
- [x] `platforms/climate.py` — `RuneClimateEntity` (mode_*, fan_*, temp_NN)
- [x] `platforms/light.py` — `RuneLightEntity` (onoff or brightness_N)
- [x] `platforms/cover.py` — `RuneCoverEntity` (open/close/stop + position_open/close)
- [x] `platforms/media_player.py` — `RuneMediaPlayerEntity` (power/volume/play/pause/source_*)
- [x] `platforms/switch.py` — `RuneSwitchEntity` (with power-verdict sync)
- [x] `platforms/remote.py` — `RuneRemoteEntity` (generic command board)
- [x] Tests — **393 passed, 12 skipped (HA-only contracts), 91% coverage**

### Phase 6 — Detailed Progress
- [x] `__init__.py` — `async_setup_entry` + `async_unload_entry` + `async_remove_entry` + auto-migration
- [x] `config_flow.py` — two-screen setup (name + category, then transmitter picker) + no-op options flow
- [x] `services.yaml` — `rune.send_command` + `rune.learn_command` definitions
- [x] `translations/en.json` + `translations/es.json` — full config + options + services strings
- [x] `websocket_api.py` — `rune/list`, `rune/device/get`, `rune/device/create` (stub), `rune/device/delete`, `rune/transmitter/list`, `rune/receiver/list`
- [x] Tests — **409 passed, 12 skipped (HA-only contracts), 91% coverage**

### 🟢 MVP Gate — Ready to load into Home Assistant

What works end-to-end today:

- ✅ Integration manifest (`manifest.json`)
- ✅ Config flow: name + category + transmitter
- ✅ All 8 platforms wired (fan, climate, light, cover, media_player, switch, button, remote)
- ✅ Pulse button platform: one button per learned command
- ✅ TX path: command → TX gate (emitter stagger) → transmitter (native IR/RF / Broadlink / ESPHome) → hardware
- ✅ WebSocket API: list/get/delete devices, list transmitters/receivers
- ✅ Services: `rune.send_command`, `rune.learn_command` (stub)
- ✅ Power monitor + action bindings ready (sniffer engine idle, awaiting receiver subscription)
- ✅ Translations EN + ES
- ✅ 409 tests pass, 91% coverage, 0 lint warnings

What is stubbed for the MVP (full implementations land in Phase 7):

- ⚠ `rune.device/create` WS handler — returns "not implemented" (use the config flow)
- ⚠ `rune.learn_command` service — logs the request, full capture orchestrator wired in Phase 4's sniffer integration
- ⚠ Sniffer engine is built but not yet auto-started from `__init__.py` (Phase 4 ↔ 6 bridge)
- ⚠ Climate matrix mode (full lattice lookup)
- ⚠ Snapshot import/export + SmartIR code library

To load into HA:

1. Copy `RUNE/custom_components/rune/` into your HA's `config/custom_components/`.
2. Restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → "RUNE"**.
4. Pick a name, choose a category, select an existing transmitter entity (`infrared.*`, `remote.*`, `radio_frequency.*`, or `esphome.*`).
5. The device shows up as a fan / climate / light / etc. plus a `button.<device>_power_on` (and similar) for every command.
6. Press a button → pulse goes out through the TX gate to your emitter.
7. Trigger automations via `rune.send_command` service or `button.press` event.

Known limitations on first load (no data, just entities):

- A newly-added device has NO commands yet — it shows up as a fan with no speed keys, a switch with no on/off, etc. The `rune.learn_command` wizard (Phase 7) is the path forward.
- Until you wire a receiver, the sniffer engine has nothing to listen to.
- The climate matrix file (for full state-space devices) is read-only for now; edit YAML in Phase 7.

---

> Modern Home Assistant custom integration synthesizing the best of
> **SmartIR** (multi-controller code library), **HAIR** (GUI + sniffer +
> triggers + native IR APIs), and **RF_FAN** (RF learn flow + discrete-speed
> fan + clean-frame replay). Design-first, code-light, no copy-paste.

---

## Table of Contents

1. [Goals & Non-Goals](#1-goals--non-goals)
2. [Feature Inventory & Attribution](#2-feature-inventory--attribution)
3. [Hexagonal Architecture](#3-hexagonal-architecture)
4. [Domain Taxonomy](#4-domain-taxonomy)
5. [Data Model](#5-data-model)
6. [Ports & Adapters](#6-ports--adapters)
7. [Signal Lifecycle & Sniffer](#7-signal-lifecycle--sniffer)
8. [Capture Pipeline](#8-capture-pipeline)
9. [Transmit Pipeline](#9-transmit-pipeline)
10. [Trigger & Action Engine](#10-trigger--action-engine)
11. [Home Assistant Platform Adapters](#11-home-assistant-platform-adapters)
12. [Configuration Flow & Options](#12-configuration-flow--options)
13. [WebSocket API & Frontend Surface](#13-websocket-api--frontend-surface)
14. [Storage, Migrations & Versioning](#14-storage-migrations--versioning)
15. [Errors, Logging & Observability](#15-errors-logging--observability)
16. [Testing Strategy](#16-testing-strategy)
17. [Directory Layout](#17-directory-layout)
18. [Implementation Roadmap](#18-implementation-roadmap)

---

## 1. Goals & Non-Goals

### Goals

- **GUI-first**: create, edit, duplicate, delete entities without YAML.
- **One engine, many entity shapes**: Fan, Climate, Light, Cover, Media
  Player, Switch, Remote, plus ad-hoc Pulse Buttons.
- **Two speed models side-by-side**: continuous percentage **and** discrete
  N-speed (`min/max/step`), both first-class, switchable per entity.
- **Permanent Sniffer mode**: passive listener that groups unknown signals by
  remote, clusters them, dedupes across jitter, with dismissal and assign.
- **Action mapping**: bind any captured signal to a pulse-button press, an HA
  service call, a scene, or a script — with min-hits window + receiver scope.
- **Multi-transport TX**: Broadlink, ESPHome (native IR + RF), native
  `infrared` and `radio_frequency` platforms. Zero hard-coded transport.
- **Power-aware state correction**: optional power-sensor binding fixes
  optimistic state when the physical remote overrides (HAIR).
- **Code library**: vendor device profiles (JSON) usable both as pre-seeded
  templates and as live runtime references (SmartIR).
- **Snapshot import/export**: portable device bundles for backup / sharing
  (HAIR's wig closet, simplified).
- **Hexagonal core, DRY ports, SRP modules, early-return guards, no magic
  numbers, English naming, full type hints.**

### Non-Goals

- Cloud sync, telemetry, vendor accounts.
- Building emitters or receivers — RUNE consumes existing HA platform
  entities only.
- Voice control, media library indexing, complex automation editor.
- A bundled custom-panel SPA in v1 (use Lovelace resources + YAML cards;
  full panel can land in v2).

---

## 2. Feature Inventory & Attribution

| Capability                                                      | Origin    | Notes carried over                                       |
| --------------------------------------------------------------- | --------- | -------------------------------------------------------- |
| Multi-controller code library                                   | SmartIR   | JSON profiles, Base64/Hex/Pronto/Raw encodings           |
| Pronto → LIRC → Broadlink encode                                | SmartIR   | Helper-style pure functions in `domain/encoding/`        |
| Climate HVAC matrix (lattice)                                   | HAIR      | Optional `matrix` mode, kept as a flag on Climate entity |
| GUI entity creation via WS API                                  | HAIR      | `rune/<command>` handlers, full CRUD                     |
| Always-on Sniffer / Mirror / Dismiss                            | HAIR      | Dedup tiers (decoded > byte_hash > fingerprint)          |
| Capture providers (Native/Broadlink/ESP/Mock)                   | HAIR      | Pluggable `CaptureProvider` protocol, async session lock |
| Command categories & device types                               | HAIR      | `CommandCategory`, `EntityCategory` enums                |
| Trigger min-hits / receiver scope                               | HAIR      | Anchored reset window, multi-receiver dedup              |
| Power monitor verdict                                           | HAIR      | Power sensor + dual thresholds, dispatcher signal        |
| TX gate (echo suppression + stagger)                            | HAIR      | Per-emitter stagger, garbled-echo swallow                |
| Two-phase RF learn (sweep + capture)                            | RF_FAN    | Direct-capture path for short-burst remotes              |
| Discrete N-speed fan with optimistic                            | RF_FAN    | `speed_count`, `has_on_button`, sub-entities             |
| Sub-entities per config entry                                   | RF_FAN    | Same UI primary + sub-entities pattern                   |
| Clean-frame consensus replay                                    | RF_FAN    | Split frames + cell-string majority vote                 |
| Trim idle gaps                                                  | RF_FAN    | `_IDLE_TRIM_US`, plus bounded terminator (HAIR tweak)    |
| Migration with version-bump reload                              | RF_FAN    | `async_migrate_entry`, update listener                   |
| Discrete `speed_N` buttons exposed as Pulse Button sub-entities | All three | Per-tx pusher next to the parent entity                  |
| `radio_frequency.async_get_transmitters`                        | HA native | Frequency + modulation filter (OOK today)                |
| `infrared.async_subscribe_receiver`                             | HA native | HA 2026.6+ receiver subscription                         |
| Native IR emitter via `InfraredEmitterConsumerEntity`           | HA native | Tx base class                                            |

---

## 3. Hexagonal Architecture

```
                ┌──────────────────────────────────────────────┐
                │           Driver Adapters (Inbound)          │
                │  ConfigFlow  •  WebSocketAPI  •  REST service│
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌──────────────────────────────────────────────┐
                │       Application Layer (Use Cases)          │
                │  CreateDevice  •  LearnCommand  •  SniffLoop  │
                │  TriggerFire   •  SendCommand   •  BindAction │
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌──────────────────────────────────────────────┐
                │     Domain Core (Pure Python, zero HA)       │
                │   Entities • Signals • Actions • Mappers     │
                │   Decoders • Matchers • Validators           │
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌──────────────────────────────────────────────┐
                │       Ports (Abstract Interfaces)            │
                │  Repository • Transmitter • Receiver • Clock │
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌──────────────────────────────────────────────┐
                │         Driven Adapters (Outbound)           │
                │  HAStore • BroadlinkAPI • NativeIR • NativeRF│
                │  ESPHomeEvents • InMemoryRepo • MockClock     │
                └──────────────────────────────────────────────┘
```

### Rules

- `domain/` imports **nothing** from `homeassistant.*`. Testable in isolation.
- `ports/` declare abstract contracts only — Python `ABC` + `Protocol`.
- `adapters/` are the only layer allowed to import `homeassistant.*`.
- `platforms/` are HA entity shells — thin, delegate to use cases.
- No cross-port circular imports. Dependency direction strictly inward.

---

## 4. Domain Taxonomy

### 4.1 EntityCategory (what the user-facing entity _is_)

```python
class EntityCategory(StrEnum):
    FAN            = "fan"            # discrete or % fan
    CLIMATE        = "climate"        # HVAC, supports matrix mode
    LIGHT          = "light"          # on/off or dimmable
    COVER          = "cover"          # open/close/stop
    MEDIA_PLAYER   = "media_player"   # power/volume/source
    SWITCH         = "switch"         # binary toggle
    REMOTE         = "remote"         # generic remote board (loose buttons)
    CUSTOM         = "custom"         # user-defined shape
```

### 4.2 SignalCategory (the _carrier_ of a command)

```python
class SignalTransport(StrEnum):
    RF = "rf"
    IR = "ir"

class SignalEncoding(StrEnum):
    RAW_TIMINGS   = "raw_timings"     # signed microsecond list
    DECODED       = "decoded"         # NEC/RC5/Samsung/Sony/Pronto hex
    BASE64_PACKET = "base64_packet"   # Broadlink packed RF/IR
    JSON_PAYLOAD  = "json_payload"    # ESPHome native action payload

@dataclass(frozen=True)
class SignalCategory:
    transport: SignalTransport
    encoding: SignalEncoding
    carrier_frequency_hz: int  # 38_000, 433_920_000, 315_000_000, ...
```

### 4.3 CommandCategory (semantic of a learned pulse)

```python
class CommandCategory(StrEnum):
    POWER         = "power"
    TRANSPORT     = "transport"       # play/pause/stop/next/prev
    VOLUME        = "volume"
    CHANNEL       = "channel"
    NAVIGATION    = "navigation"      # up/down/left/right/ok
    MODE          = "mode"            # hvac mode / fan mode / source
    TEMPERATURE   = "temperature"
    FAN_SPEED     = "fan_speed"
    BRIGHTNESS    = "brightness"
    COLOR_TEMP    = "color_temp"
    COVER         = "cover"
    SPEED_PRESET  = "speed_preset"    # discrete speed_N
    CUSTOM        = "custom"
```

### 4.4 ActionTarget (what to _do_ when a signal fires)

```python
class ActionKind(StrEnum):
    PRESS_BUTTON     = "press_button"     # device_id + command_key
    CALL_SERVICE     = "call_service"     # domain + service + data
    ACTIVATE_SCENE   = "activate_scene"   # scene entity_id
    RUN_SCRIPT       = "run_script"       # script entity_id
    FIRE_EVENT       = "fire_event"       # HA bus event
```

### 4.5 SpeedMode (per fan entity)

```python
class SpeedMode(StrEnum):
    PERCENTAGE = "percentage"   # 0–100, mapped to N steps
    DISCRETE   = "discrete"     # 1..N, no percentage at all
    HYBRID     = "hybrid"       # both exposed
```

---

## 5. Data Model

All models live in `domain/models.py` (pure Python) with `to_dict` /
`from_dict` for persistence. **Frozen** dataclasses for value objects;
**mutable** for aggregates.

### 5.1 Value Objects (frozen)

```python
@dataclass(frozen=True)
class PulseCommand:
    key: str                        # unique within device
    label: str                      # user-visible name
    category: CommandCategory
    signal: SignalCategory
    payload: PulsePayload           # discriminated union, see below

@dataclass(frozen=True)
class PulsePayload:                  # tagged union
    raw_timings: list[int] | None = None
    decoded_hex: str | None = None
    base64_packet: str | None = None
    json_payload: dict | None = None
    repeat_count: int = 1           # protocol ditto count
    send_count: int = 1             # whole-frame loop count
```

### 5.2 Aggregates (mutable)

```python
@dataclass
class RuneDevice:
    id: str
    name: str
    category: EntityCategory
    manufacturer: str | None
    model: str | None
    transmitter_entity_ids: list[str]
    receiver_entity_ids: list[str]            # for sniffer scope
    speed_mode: SpeedMode = SpeedMode.HYBRID
    discrete_speed_count: int = 3
    power_sensor_entity_id: str | None = None
    power_off_below_w: float | None = None
    power_on_above_w: float | None = None
    temperature_sensor_entity_id: str | None = None
    humidity_sensor_entity_id: str | None = None
    climate_matrix: bool = False
    commands: dict[str, PulseCommand] = field(default_factory=dict)
    actions: dict[str, ActionBinding] = field(default_factory=dict)
    version: int = 1
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)

@dataclass
class UnknownSignal:
    id: str
    fingerprint: str               # tier-3 identity
    byte_hash: str | None          # tier-2 (sub-threshold protocols)
    decoded_fingerprint: str | None  # tier-1 (NEC:0xABCD:0xEF)
    category: SignalCategory
    protocol_label: str | None
    code_hex: str | None
    raw_timings: list[int]
    first_seen: str
    last_seen: str
    hit_count: int
    alias: str = ""
    source: Literal["sniffed", "manual", "imported"] = "sniffed"

@dataclass
class UnknownRemote:
    id: str
    label: str | None
    protocol_label: str | None
    device_address: str | None
    signals: list[UnknownSignal]
    dismissed: bool = False
    first_seen: str
    last_seen: str
    hit_count: int

@dataclass
class ActionBinding:
    id: str
    name: str
    signal_id: str
    target: ActionTarget           # kind + payload
    min_hits: int = 1
    receiver_entity_ids: list[str] = field(default_factory=list)
    enabled: bool = True
    created_at: str = field(default_factory=utcnow_iso)
```

### 5.3 ProfileLibrary (SmartIR-style codes)

```python
@dataclass
class DeviceProfile:               # immutable template
    code: int                       # SmartIR-style numeric id
    category: EntityCategory
    manufacturer: str
    supported_models: list[str]
    supported_transports: list[SignalTransport]
    commands: dict[str, PulsePayload]   # state_key → payload
    speed_list: list[str] | None = None  # ["low","med","high"]
    matrix: ClimateMatrix | None = None  # optional lattice
```

`DeviceProfile` is the only place Pronto/Hex conversion logic lives.

---

## 6. Ports & Adapters

### 6.1 Inbound (driver) ports

```
ConfigFlowDriver
WebSocketAPIDriver      # rune/list, rune/device/create, ...
RestServiceDriver       # rune.send_command, rune.learn
```

### 6.2 Outbound (driven) ports

```python
class DeviceRepository(Protocol):
    async def load(self) -> list[RuneDevice]: ...
    async def save(self, devices: list[RuneDevice]) -> None: ...
    async def get(self, device_id: str) -> RuneDevice | None: ...
    async def upsert(self, device: RuneDevice) -> None: ...
    async def delete(self, device_id: str) -> None: ...

class SignalRepository(Protocol):
    async def load_remotes(self) -> list[UnknownRemote]: ...
    async def save_remotes(self, remotes: list[UnknownRemote]) -> None: ...
    async def append_signal(self, signal: UnknownSignal) -> None: ...
    async def remove_signal(self, signal_id: str) -> None: ...

class ActionRepository(Protocol):
    async def load(self) -> list[ActionBinding]: ...
    async def save(self, actions: list[ActionBinding]) -> None: ...

class TransmitterPort(Protocol):
    """One concrete impl per transport kind."""
    transport: SignalTransport
    async def send(self, command: PulseCommand) -> None: ...
    async def learn(self, frequency_hz: int | None = None) -> CapturedPulse: ...

class ReceiverPort(Protocol):
    transport: SignalTransport
    async def start_listening(self, on_signal: Callable[[CapturedPulse], Awaitable[None]]) -> Callable[[], None]: ...
    async def stop_listening(self) -> None: ...

class ClockPort(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...
```

### 6.3 Adapter map

| Port                   | Adapters                                                                                                    |
| ---------------------- | ----------------------------------------------------------------------------------------------------------- |
| `DeviceRepository`     | `HAStoreAdapter` (uses `homeassistant.helpers.storage.Store`)                                               |
| `SignalRepository`     | `HASignalStoreAdapter` (separate `rune_unknown_signals` store)                                              |
| `ActionRepository`     | `HAActionStoreAdapter`                                                                                      |
| `TransmitterPort` (IR) | `NativeIRAdapter`, `BroadlinkNativeAdapter`, `ESPHomeIRAdapter`                                             |
| `TransmitterPort` (RF) | `NativeRFAdapter`, `BroadlinkRFAdapter`, `ESPHomeRFAdapter`                                                 |
| `ReceiverPort` (IR)    | `NativeIRReceiverAdapter` (`infrared.async_subscribe_receiver`), `ESPHomeLegacyReceiverAdapter` (event bus) |
| `ReceiverPort` (RF)    | `BroadlinkRFReceiverAdapter` (sweep + capture flow)                                                         |
| `ClockPort`            | `SystemClockAdapter`, `FrozenClockAdapter` (tests)                                                          |

Every adapter implements exactly one port; selection happens in the
application factory at startup based on installed HA platforms.

---

## 7. Signal Lifecycle & Sniffer

### 7.1 Lifecycle

```
CapturedPulse (raw)
      │
      ▼ normalize(signal)         ← domain/signal/normalize.py
NormalizedSignal (carries tiered identity)
      │
      ▼ tier_match(existing_remotes) ← domain/signal/matcher.py
  ┌─────────────────────────────────────────────────────────────┐
  │ tier 1: decoded_fingerprint (e.g. "NEC:0xFB04:0x08")        │
  │ tier 2: byte_hash (quantized Pronto timing bytes)           │
  │ tier 3: S/L fingerprint (short/long pattern)                │
  └─────────────────────────────────────────────────────────────┘
      │
      ├─ hit on existing UnknownSignal ─► bump hit_count, last_seen
      ├─ hit on assigned PulseCommand ──► route to TriggerEngine
      └─ miss ─► cluster-or-mint new UnknownSignal on a remote
```

### 7.2 Sniffer engine responsibilities

- One async task per `ReceiverPort`, owns its subscription lifecycle.
- **Rate limit** (default 10/s/device) — prevents phantom devices (HAIR GH #72).
- **Repeat suppression** (default 300ms) — collapse NEC dittos.
- **Capacity guard** (per-device + global signal caps, eviction by age).
- **Mirror device** — every HA-originated TX is logged to `Mirror` with
  its echoing receiver ids.
- **Garbled-echo swallow** — captures within the send window whose
  edit-distance to the live transmitted pattern is below
  `ECHO_GARBLE_SIMILARITY` are dropped.
- **Emitter stagger** — TX gate enforces minimum gap between different
  emitters to prevent cross-emitter hybrid signals.

### 7.3 Persisted unknowns live in their own store

Key: `rune_unknown_signals`, separate from `rune_devices` so a corrupt
or oversized signal feed can't take the main device store down (the
HAIR lesson learned the hard way).

---

## 8. Capture Pipeline

### 8.1 Phases

```
user presses Learn on a button
        │
        ▼
Phase 1 — Carrier Detect
  - RF: sweep frequency (Broadlink sweep_frequency API) or direct
  - IR: rely on emitter/receiver native API (no carrier detection needed)
        │
        ▼
Phase 2 — Pulse Capture
  - single-shot listen at locked carrier
  - returns raw timings + (optional) protocol decode + Pronto encode
        │
        ▼
Phase 3 — Normalize + Quality Check
  - trim idle gaps (>20ms)
  - consensus vote for noisy captures (Mercator-style cell-string majority)
  - bounded trailing terminator (50ms — fits uint16, exceeds 35ms Daikin)
        │
        ▼
Phase 4 — Decode Attempt
  - infrared_protocols library: try NEC / RC5 / Samsung / Sony / Panasonic / Pronto
  - populate tier-1 identity when successful
        │
        ▼
Phase 5 — User Confirm
  - present: raw timings length, decoded protocol/address/command, repeat/send knobs
  - user may: keep, retry, abort, edit repeat_count/send_count/force_raw
```

### 8.2 Provider model

```python
class CaptureProvider(ABC):
    transport: SignalTransport
    async def is_available(self) -> bool: ...
    async def start_capture(self, timeout_s: float) -> None: ...
    async def wait_for_signal(self) -> CapturedPulse: ...
    async def stop_capture(self) -> None: ...
```

Built-in providers: `NativeIRProvider`, `NativeRFProvider`,
`BroadlinkRFProvider`, `ESPHomeLegacyIRProvider`, `MockProvider`.

`CaptureOrchestrator` is a thin use case: it owns the asyncio lock,
notifies WS subscribers, manages session lifecycle. One orchestrator per
RUNE instance.

---

## 9. Transmit Pipeline

```
PulseCommand
    │
    ▼ resolve_transmitter(device)        ← pick first compatible TX
    │
    ▼ apply_tx_knobs(payload)             ← bounded terminator, idle trim
    │
    ▼ TX gate
        ├── different emitter? wait EMITTER_STAGGER_GAP_S
        ├── same emitter? wait SEND_REPEAT_GAP_S between repeats
        └── mark mirror row, fire mirror event
    │
    ▼ TransmitterPort.send(payload)        ← dispatch per transport
    │
    ▼ record echo candidates               ← for sniffer to claim
```

### 9.1 Transport encoding rules

| Transport    | Source field                           | Carrier                |
| ------------ | -------------------------------------- | ---------------------- |
| IR native    | `PulsePayload.raw_timings` (signed µs) | emitter's `modulation` |
| RF native    | `PulsePayload.raw_timings`             | device's frequency     |
| IR Broadlink | Pronto hex → LIRC → Broadlink pack     | 38 kHz                 |
| RF Broadlink | `PulsePayload.raw_timings`             | learned frequency      |
| ESPHome IR   | Pronto hex                             | YAML-configured        |
| ESPHome RF   | `PulsePayload.raw_timings`             | YAML-configured        |

All conversions go through `domain/encoding/` — no ad-hoc encoding in
adapters.

---

## 10. Trigger & Action Engine

### 10.1 ActionBinding rules

- Source: `UnknownSignal.id` **or** `PulseCommand.key`.
- Trigger condition: arrival within `TRIGGER_HIT_RESET_WINDOW_S` of
  the first press, hit count >= `min_hits`.
- Multi-receiver dedup window: `MULTI_RECEIVER_DEDUP_WINDOW_S` (100ms
  default — fits Sony SIRC repeat cadence).
- Receiver scope: if non-empty, only fires for signals from listed
  receiver entities (None never matches scoped trigger).
- Fire outcome: execute `ActionTarget` exactly once per chain.

### 10.2 Target types

- `PRESS_BUTTON` → call into `DeviceRepository.get(device_id)` then
  invoke that device's TX path.
- `CALL_SERVICE` → `hass.services.async_call(domain, service, data)`.
- `ACTIVATE_SCENE` → `scene.turn_on`.
- `RUN_SCRIPT` → `script.<entity>` turn-on.
- `FIRE_EVENT` → `hass.bus.async_fire(event_type, data)`.

### 10.3 Power Monitor verdict (HAIR-style, optional)

- Subscribe to a `sensor.<power>` entity with `device_class: power`.
- On change: if `< power_off_below_w` → mark all device entities OFF;
  if `> power_on_above_w` → mark ON. Verdict dispatched via HA signal;
  platform entities listen and update assumed state.

---

## 11. Home Assistant Platform Adapters

Each platform file is a **thin shell**: load devices from the repository,
instantiate one HA entity per (device, role) pair, register update
callbacks. All domain logic lives in `domain/`.

### 11.1 Platforms exposed

| Platform       | Entity shape                        | Notes                                 |
| -------------- | ----------------------------------- | ------------------------------------- |
| `fan`          | `FanEntity` + discrete/%/hybrid     | Sub-entities allowed per device       |
| `climate`      | `ClimateEntity`                     | Preset or matrix mode                 |
| `light`        | `LightEntity` (onoff or brightness) | Brightness when 2+ dim commands exist |
| `cover`        | `CoverEntity` (open/close/stop)     | Position when commands permit         |
| `media_player` | `MediaPlayerEntity`                 | Source list, volume                   |
| `switch`       | `SwitchEntity`                      | Optimistic, optional power monitor    |
| `button`       | `ButtonEntity`                      | One per PulseCommand                  |
| `remote`       | `RemoteEntity`                      | Sends raw via selected emitter        |

### 11.2 Speed mapping (single source of truth)

```python
class SpeedMapper:
    """Pure Python; lives in domain/mappers/speed_mapper.py."""

    @staticmethod
    def discrete_to_percent(step: int, total: int) -> int: ...

    @staticmethod
    def percent_to_discrete(percent: int, total: int) -> int:
        if percent <= 0: return 0
        return max(1, min(total, math.ceil(percent_to_ranged_value((1, total), percent))))

    @staticmethod
    def percent_to_named(percent: int, names: list[str]) -> str | None: ...

    @staticmethod
    def named_to_percent(name: str, names: list[str]) -> int | None: ...
```

`fan.py` calls `SpeedMapper` — never recomputes percentages inline.
`climate.py` uses `percent_to_named` against the device's fan-mode list.

### 11.3 Pulse Button generation

- Every `PulseCommand` produces **one** `ButtonEntity`.
- For fan entities, `speed_1..speed_N` are also exposed as buttons (in
  addition to the numeric step on the fan entity itself).
- Buttons inherit the device's `DeviceInfo` (one HA device per
  `RuneDevice`, not per button).

---

## 12. Configuration Flow & Options

### 12.1 Two flows

**Setup flow** (single-instance hub):

1. Detect available transports (IR/RF emitters + receivers).
2. Pick primary device name + first entity category.
3. First learn wizard (optional — user may skip and add devices manually).

**Options flow** (per-config-entry):

1. Add device (type + name + tx + rx + speed config).
2. Edit device (rename, change tx/rx, toggle matrix mode).
3. Duplicate device.
4. Delete device.
5. Re-learn existing command.
6. Add new pulse command to existing device.
7. Configure power monitor thresholds.
8. Manage action bindings.
9. Manage unknowns (view, alias, dismiss, restore, assign).

### 12.2 Reusable mixin

A `_LearnFlowMixin` (like rf_fan's) is reused by both setup and options
flows, sharing the same `learn` → `learn_press` → `learn_capture` →
`learn_result` → `confirm`/`test`/`retry` state machine.

### 12.3 Migration

`async_migrate_entry` handles version bumps. v1 schema → v2 schema → ...
Each bump is its own function for clarity and testability.

---

## 13. WebSocket API & Frontend Surface

### 13.1 Command namespace: `rune/<verb>`

| Command                     | Purpose                                 |
| --------------------------- | --------------------------------------- |
| `rune/list`                 | List devices + counts                   |
| `rune/device/get`           | Full device detail                      |
| `rune/device/create`        | Create with empty commands              |
| `rune/device/update`        | Patch device metadata                   |
| `rune/device/duplicate`     | Deep clone with new id                  |
| `rune/device/delete`        | Remove + cleanup triggers               |
| `rune/command/add`          | Begin learn wizard (returns session_id) |
| `rune/command/learn_event`  | Stream learn state changes              |
| `rune/command/learn_cancel` | Abort active session                    |
| `rune/command/save`         | Persist captured pulse                  |
| `rune/command/relearn`      | Re-learn existing key                   |
| `rune/command/delete`       | Remove pulse                            |
| `rune/command/reorder`      | Drag-to-reorder                         |
| `rune/action/create`        | New action binding                      |
| `rune/action/update`        | Patch action                            |
| `rune/action/delete`        | Remove action                           |
| `rune/unknown/list`         | List unknown remotes/signals            |
| `rune/unknown/dismiss`      | Hide from default view                  |
| `rune/unknown/restore`      | Show again                              |
| `rune/unknown/assign`       | Convert UnknownSignal → PulseCommand    |
| `rune/unknown/alias`        | Rename for UI                           |
| `rune/unknown/delete`       | Forget signal                           |
| `rune/transmitter/list`     | Discover compatible emitters            |
| `rune/receiver/list`        | Discover receivers                      |

### 13.2 Server-pushed events (HA bus)

- `rune_command_captured`
- `rune_capture_timeout`
- `rune_capture_error`
- `rune_signal_detected`
- `rune_signal_updated`
- `rune_action_fired`
- `rune_power_verdict`

### 13.3 Frontend (v1)

- YAML Lovelace card + resources. No custom panel required to start.
- v2: optional custom-panel SPA (post-MVP, out of scope).

---

## 14. Storage, Migrations & Versioning

### 14.1 Storage keys

| Key                    | Version | Purpose                            |
| ---------------------- | ------- | ---------------------------------- |
| `rune.devices`         | 1       | `RuneDevice` list                  |
| `rune.actions`         | 1       | `ActionBinding` list               |
| `rune.unknown_signals` | 1       | Unknown remotes/signals (separate) |
| `rune.profiles.cache`  | 1       | Downloaded device profiles         |

Separate stores so signal-store corruption can't destroy device state
(HAIR's failure mode).

### 14.2 Migration pattern

```python
async def async_migrate_entry(hass, entry) -> bool:
    if entry.version < 2:
        await _migrate_v1_to_v2(hass, entry)
    if entry.version < 3:
        await _migrate_v2_to_v3(hass, entry)
    return True
```

Each migration function is pure (no side effects beyond store update),
unit-testable in isolation, and logs the schema delta.

### 14.3 Update listener

`entry.async_on_unload(entry.add_update_listener(_async_reload))`
ensures any options change reloads the entry and rehydrates entities.

---

## 15. Errors, Logging & Observability

### 15.1 Error hierarchy (in `domain/errors.py`)

```
RuneError
├── ConfigError
│   ├── NoTransmitterError
│   ├── NoReceiverError
│   └── InvalidProfileError
├── CaptureError
│   ├── CaptureTimeoutError
│   ├── CaptureAbortedError
│   └── CaptureProviderUnavailableError
├── TransmitError
│   ├── UnsupportedHardwareError
│   └── TxGateTimeoutError
├── StorageError
│   ├── MigrationError
│   └── ValidationError
└── ActionError
    └── ActionTargetNotFoundError
```

Raise typed errors only. Never bare `Exception`; `noqa: BLE001` is
forbidden.

### 15.2 Logging conventions

- One module-level `_LOGGER = logging.getLogger(__name__)`.
- Structured extra fields: `device_id`, `command_key`, `signal_id`,
  `receiver_id`, `transport`, `frequency_hz`.
- Never log raw pulse timings (potentially huge).
- INFO for learn start/end; WARNING for retries; ERROR for failures;
  DEBUG for per-pulse routing.

### 15.3 Diagnostics

- `diagnostics.py` exposes device counts, last-capture timestamp,
  sniffer rates, recent errors — redacts pulse payloads.

---

## 16. Testing Strategy

### 16.1 Layers

| Layer            | Test style                  | Speed  |
| ---------------- | --------------------------- | ------ |
| `domain/`        | pure pytest, no HA          | < 1s   |
| `ports/`         | contract pytest             | < 1s   |
| `adapters/`      | pytest with HA test fixture | 5–20s  |
| `platforms/`     | pytest + mock repos         | 5–20s  |
| `config_flow/`   | HA flow harness             | 5–10s  |
| `websocket_api/` | HA WS harness               | 10–30s |

### 16.2 Fixtures

- `FakeClock` — frozen time + monotonic.
- `InMemoryDeviceRepository` — port conformance suite.
- `MockTransmitter` — captures sends without hardware.
- `MockReceiver` — replays captured pulse streams for sniffer tests.

### 16.3 Property-based

- `SpeedMapper`: roundtrip identity on valid range.
- `SignalIdentity`: tier precedence monotonicity.
- `Mercator.consensus`: deterministic for fixed inputs.

### 16.4 Coverage target

- `domain/`: 95%+
- `adapters/`: 80%+
- `platforms/`: 70%+
- `websocket_api/`: 80%+

---

## 17. Directory Layout

```
custom_components/rune/
├── __init__.py                     # entry, async_setup, async_setup_entry, migrate
├── manifest.json                   # deps: infrared, esphome, broadlink (soft)
├── config_flow.py                  # setup + options flow, learn mixin
├── const.py                        # domain, version, ALL magic numbers live here
├── diagnostics.py                  # HA diagnostics export
│
├── domain/                         # PURE PYTHON — no homeassistant imports
│   ├── __init__.py
│   ├── enums.py                    # EntityCategory, SignalCategory, CommandCategory, SpeedMode, ActionKind
│   ├── models.py                   # RuneDevice, PulseCommand, UnknownSignal, ActionBinding, DeviceProfile
│   ├── errors.py                   # RuneError hierarchy
│   ├── time.py                     # utcnow_iso, monotonic_ms
│   ├── encoding/
│   │   ├── pronto.py               # pronto hex ⇄ raw timings
│   │   ├── broadlink.py            # lirc2broadlink, base64 wrap
│   │   └── timing.py               # trim idle, bounded terminator
│   ├── identity/
│   │   ├── signal_identity.py      # tiered matching
│   │   ├── byte_hash.py            # Pronto byte quantization
│   │   └── sl_pattern.py           # short/long fingerprint
│   ├── signal/
│   │   ├── normalize.py            # raw → NormalizedSignal
│   │   ├── matcher.py              # tier lookup across unknown remotes
│   │   ├── cluster.py              # group by remote
│   │   └── quality.py              # consensus vote, idle trim
│   ├── mappers/
│   │   ├── speed_mapper.py         # % ⇄ discrete ⇄ named
│   │   ├── climate_mapper.py       # state lattice
│   │   └── action_mapper.py        # signal → action dispatch
│   ├── profiles/
│   │   ├── library.py              # DeviceProfile load + match
│   │   └── builtin.py              # minimal bundled profiles
│   └── triggers/
│       ├── engine.py               # min_hits, reset window, dedup
│       └── evaluator.py            # receiver scope check
│
├── ports/                          # abstract interfaces
│   ├── __init__.py
│   ├── repository.py               # DeviceRepository, SignalRepository, ActionRepository
│   ├── transmitter.py              # TransmitterPort
│   ├── receiver.py                 # ReceiverPort
│   ├── capture_provider.py         # CaptureProvider
│   ├── clock.py                    # ClockPort
│   └── power_monitor.py            # PowerMonitorPort
│
├── adapters/                       # concrete impls, allowed to import HA
│   ├── __init__.py
│   ├── storage/
│   │   ├── device_store.py         # HA Store adapter
│   │   ├── signal_store.py
│   │   ├── action_store.py
│   │   └── profile_cache.py
│   ├── transmitters/
│   │   ├── base.py                 # common helpers
│   │   ├── native_ir.py
│   │   ├── native_rf.py
│   │   ├── broadlink_ir.py
│   │   ├── broadlink_rf.py
│   │   ├── esphome_ir.py
│   │   └── esphome_rf.py
│   ├── receivers/
│   │   ├── native_ir.py            # infrared.async_subscribe_receiver
│   │   ├── broadlink_rf.py         # sweep + capture
│   │   └── esphome_legacy_ir.py    # esphome.remote_received event
│   ├── capture/
│   │   ├── orchestrator.py
│   │   ├── native_ir.py
│   │   ├── native_rf.py
│   │   ├── broadlink_rf.py
│   │   ├── esphome_legacy_ir.py
│   │   └── mock.py
│   ├── power_monitor.py
│   ├── tx_gate.py
│   ├── clock.py
│   └── factory.py                  # wires ports → adapters at startup
│
├── sniffer/
│   ├── __init__.py
│   ├── engine.py                   # main listener loop
│   ├── rate_limiter.py
│   ├── capacity.py                 # signal caps + eviction
│   └── mirror.py                   # synthetic mirror device
│
├── platforms/                      # HA entity shells (thin)
│   ├── fan.py
│   ├── climate.py
│   ├── light.py
│   ├── cover.py
│   ├── media_player.py
│   ├── switch.py
│   ├── button.py
│   └── remote.py
│
├── services.yaml                   # rune.* service definitions
├── websocket_api.py                # all rune/* WS commands
├── migrations.py                   # versioned schema migrations
├── translations/
│   ├── en.json
│   └── es.json
└── tests/
    ├── conftest.py
    ├── domain/
    ├── adapters/
    ├── platforms/
    └── websocket_api/
```

---

## 18. Implementation Roadmap

### Phase 0 — Skeleton

- [ ] Repo init, manifest.json, `const.py` with all magic numbers
- [ ] Domain enums, errors, time helpers
- [ ] Pure models with `to_dict`/`from_dict`
- [ ] First pytest run passing on `domain/`

### Phase 1 — Core domain logic

- [ ] `encoding/pronto.py`, `encoding/broadlink.py`, `encoding/timing.py`
- [ ] `identity/signal_identity.py` (tiers 1–3)
- [ ] `mappers/speed_mapper.py` (the canonical mapper)
- [ ] `signal/normalize.py`, `signal/matcher.py`, `signal/quality.py`
- [ ] `triggers/engine.py`
- [ ] Unit tests, ≥95% coverage on domain

### Phase 2 — Ports & Repositories

- [ ] Port interfaces (`ports/`)
- [ ] In-memory test implementations
- [ ] `adapters/storage/*` (HA Store)
- [ ] Migration v0 → v1
- [ ] Repository contract tests

### Phase 3 — Transmitters & Receivers

- [ ] `adapters/transmitters/native_ir.py`
- [ ] `adapters/transmitters/native_rf.py`
- [ ] `adapters/transmitters/broadlink_*` (IR via Pronto, RF via raw)
- [ ] `adapters/transmitters/esphome_*` (IR Pronto, RF raw via service)
- [ ] `adapters/receivers/native_ir.py`
- [ ] `adapters/receivers/broadlink_rf.py` (sweep + capture flow)
- [ ] `adapters/receivers/esphome_legacy_ir.py` (event bus)
- [ ] `adapters/tx_gate.py`

### Phase 4 — Capture & Sniffer

- [ ] `adapters/capture/orchestrator.py` (single-session lock)
- [ ] `adapters/capture/*_provider.py`
- [ ] `sniffer/engine.py` with rate limit + capacity + mirror
- [ ] `adapters/power_monitor.py`
- [ ] `adapters/clock.py`

### Phase 5 — Platforms (thin shells)

- [ ] `platforms/button.py` (always-on; one button per PulseCommand)
- [ ] `platforms/fan.py` (discrete + percentage via SpeedMapper)
- [ ] `platforms/light.py`, `cover.py`, `switch.py`
- [ ] `platforms/media_player.py`
- [ ] `platforms/climate.py` (preset + matrix mode)
- [ ] `platforms/remote.py`

### Phase 6 — Config & WebSocket

- [ ] `config_flow.py` setup + options + `_LearnFlowMixin`
- [ ] `websocket_api.py` for every command in §13.1
- [ ] `services.yaml` for HA service panel
- [ ] `translations/en.json`, `translations/es.json`

### Phase 7 — Profiles & Import/Export

- [ ] `domain/profiles/library.py` + bundled subset
- [ ] `domain/profiles/builtin.py` (a few popular ACs/fans/lights)
- [ ] Snapshot export/import (JSON zip)
- [ ] SmartIR code import (compat layer)

### Phase 8 — Hardening

- [ ] `diagnostics.py`
- [ ] README + HACS metadata
- [ ] Quality scale: silver → gold
- [ ] End-to-end test on real Broadlink + ESPHome setup

---

## Appendix A — Naming Conventions

- **Variables**: snake_case, descriptive English, no abbreviations beyond
  common domain terms (`tx`, `rx`, `id`, `pct` ok; `cmd`, `sig`, `cfg` no).
- **Functions**: verb-led (`async_send_pulse`, `resolve_transmitter`,
  `discrete_to_percent`).
- **Classes**: noun (`SpeedMapper`, `CaptureOrchestrator`).
- **Constants**: SCREAMING_SNAKE in `const.py` or module-local.
- **Type hints**: mandatory on public surface; `from __future__ import
annotations` at the top of every file.
- **Imports**: stdlib → third-party → local; absolute only.
- **Docstrings**: Google style; one-line summary first, then details.
- **Comments**: only when _why_ is non-obvious; never restate code.

## Appendix B — Magic Number Policy

Zero inline numeric literals in `domain/`, `platforms/`, `adapters/`
(except obvious literals like 0, 1, -1 in pure math). Every threshold,
timeout, capacity, and frequency lives in `const.py` with a short
rationale comment.

```
# const.py excerpt (illustrative)
DEFAULT_CARRIER_FREQUENCY_HZ = 38_000
DEFAULT_RF_FREQUENCY_HZ      = 433_920_000
TRIGGER_HIT_RESET_WINDOW_S   = 5.0
MULTI_RECEIVER_DEDUP_WINDOW_S = 0.100
SNIFER_RATE_LIMIT_PER_S       = 10
SNIFER_MAX_SIGNALS_PER_DEVICE = 200
SNIFER_MAX_TOTAL_SIGNALS      = 20_000
SNIFER_EVICT_AGE_DAYS         = 30
SNIFER_REPEAT_SUPPRESS_MS     = 300
TERMINATOR_SPACE_US           = 50_000
IDLE_TRIM_US                  = 20_000
EMITTER_STAGGER_GAP_S         = 0.3
SEND_REPEAT_GAP_S             = 0.1
LEARNING_TIMEOUT_S            = 30.0
```
