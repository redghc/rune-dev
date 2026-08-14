"""Transmitters subpackage — IR/RF send paths.

- :mod:`base` — common helpers (TX gate prep, encoding dispatch).
- :mod:`native_ir` — ``infrared.async_send_command`` (HA 2026.6+).
- :mod:`native_rf` — ``radio_frequency.async_send_command``.
- :mod:`broadlink_ir` — Pronto → Broadlink base64 → ``remote.send_command``.
- :mod:`broadlink_rf` — raw timings → Broadlink RF service.
- :mod:`esphome_ir` — ESPHome IR via Pronto.
- :mod:`esphome_rf` — ESPHome RF via raw timings.
- :mod:`mock` — in-process capture for tests.
- :mod:`factory` — picks an adapter from a transmitter ``entity_id``.

Each adapter depends on Home Assistant APIs (services, ``infrared`` /
``radio_frequency`` helpers). The port contract lives in
:mod:`custom_components.rune.ports.transmitter`; these adapters are
the only layer that imports ``homeassistant.*``.
"""
