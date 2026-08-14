# RUNE — Remote Universal Network Engine

Universal IR + RF remote control integration for Home Assistant.

One integration to control every IR and RF device in your home — fans,
lights, covers, media players, switches, climate, generic remotes — through
your existing Broadlink / ESPHome / native HA infrared and radio-frequency
emitters.

## Why RUNE

- **GUI-first entity management.** Create, edit, duplicate, and delete
  devices through Home Assistant's Devices & Services panel. No YAML.
- **Two speed models side-by-side.** Continuous percentage **and**
  discrete N-step (`min/max/step`), both first-class, switchable per
  entity.
- **Permanent Sniffer mode.** Passive listener groups unknown signals by
  remote, dedupes across jitter, with dismissal and assign.
- **Action mapping.** Bind any captured signal to a pulse-button press,
  a HA service call, a scene, or a script — with min-hits window and
  receiver scope.
- **Multi-transport TX.** Broadlink, ESPHome (native IR + RF), and HA's
  native `infrared` and `radio_frequency` platforms. Zero hard-coded
  transport.
- **Power-aware state correction.** Optional power-sensor binding
  corrects optimistic state when the physical remote overrides.
- **Snapshot import/export.** Portable device bundles for backup / sharing.
- **Hexagonal core, DRY ports, SRP modules, early-return guards, no magic
  numbers, English naming, full type hints.**

## What works in v0.1.0

| Capability                          | Status      |
| ----------------------------------- | ----------- |
| Config flow (name + category + tx)  | ✅ working  |
| 8 platforms (fan, climate, …)       | ✅ entities |
| Pulse-button per command            | ✅ working  |
| TX gate (emitter stagger + mirror)  | ✅ working  |
| Power monitor + action bindings     | ✅ built    |
| Sniffer engine                      | ✅ built    |
| WebSocket API (`rune/list`, …)      | ✅ working  |
| Services (`rune.send_command`, …)   | ✅ working  |
| Translations EN + ES                | ✅ working  |
| 409 tests, 91% coverage, lint clean | ✅ passing  |

## Roadmap

- **v0.2 — Capture workflow.** `rune.learn_command` wizard + per-button
  capture orchestrator integration + sniffer auto-start from
  `__init__.py`.
- **v0.3 — Profile library.** SmartIR-style code library, snapshot
  import/export, climate matrix mode (full state lattice).
- **v0.4 — Frontend SPA.** Custom Lovelace panel (the YAML card is
  fine for now; the SPA ships post-MVP).

## Installation

### Via HACS (recommended)

1. HACS → Integrations → ⋯ → **Custom repositories**.
2. Repository: `https://github.com/rune/rune`
3. Category: **Integration**
4. Install → Restart Home Assistant.

### Manual

```bash
cp -R custom_components/rune /config/custom_components/
```

Then restart HA.

## Configuration

1. **Settings → Devices & Services → Add Integration → RUNE**.
2. Step 1: enter a name and pick a category (fan / climate / light / cover
   / media_player / switch / remote).
3. Step 2: pick your IR/RF emitter entity
   (`infrared.*`, `remote.*`, `radio_frequency.*`, or `esphome.*`).
4. The device shows up as a fan / climate / light / etc. plus a
   `button.<device>_<command>` sub-entity for every learned command.

## Commands

RUNE auto-generates one HA button entity per `PulseCommand`. Examples
for a fan:

- `button.bedroom_fan_power_on`
- `button.bedroom_fan_speed_2`
- `button.bedroom_fan_off`

Pressing a button sends the captured pulse through the TX gate (waits
for emitter stagger, marks the mirror entry) and out the IR/RF
transmitter.

## Architecture (1 minute)

```
Web UI / WebSocket API
        ↓
Config Flow + Setup
        ↓
Domain (pure Python)
   - SpeedMapper (% ↔ discrete ↔ named)
   - SignalMatcher (tiered identity)
   - TriggerEngine (min_hits + receiver scope)
   - PowerMonitor verdict
        ↓
Ports (abstract interfaces)
        ↓
Adapters (HA-specific)
   - HAStoreDeviceRepository / Action / Signal
   - NativeIR / NativeRF / Broadlink / ESPHome transmitters
   - CaptureOrchestrator + SnifferEngine + TxGate
        ↓
Home Assistant platforms (fan, climate, light, cover, media_player,
switch, button, remote)
```

See `PLAN.md` for the full architecture, taxonomy, and design rules.

## Development

```bash
# Install deps + test deps
uv sync

# Run the full suite
uv run pytest

# Lint
uv run ruff check custom_components/

# Coverage threshold is 90%; CI must pass clean.
```

409 tests pass. 91% coverage on `domain/` and `adapters/`. Zero lint
warnings. Full test isolation — no Home Assistant core required for
the domain layer or unit tests; HA is only needed at integration time
and for the platform-shell tests that subclass HA entities.

## License

MIT.
