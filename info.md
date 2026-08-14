# RUNE — Remote Universal Network Engine

Universal IR + RF remote control integration for Home Assistant.

## Quick start

1. **Settings → Devices & Services → Add Integration → RUNE**
2. Enter a name, choose a category (fan / climate / light / cover / media_player / switch / remote)
3. Pick your IR/RF emitter entity
4. Use the auto-generated button entities to fire commands

## How it works

RUNE is the integration Home Assistant has been missing for IR/RF
remote control: GUI-first, multi-transport, with full capture
(sniffer) + replay (TX) + action binding + power-aware state.

## Architecture

- Pure-Python domain (no HA imports) — tested in isolation
- Hexagonal ports + adapters
- 8 HA platforms wired (fan, climate, light, cover, media_player, switch, button, remote)
- TX gate for collision avoidance between emitters
- Mirror log for echo discrimination
- Sniffer engine with rate limit + tiered identity + capacity guard

## Development

```bash
uv sync
uv run pytest
uv run ruff check custom_components/
```

409 tests pass. 91% coverage on `domain/` and `adapters/`. Zero lint warnings.

## Status

MVP released. Phase 7 (capture workflow + profile library) in progress.