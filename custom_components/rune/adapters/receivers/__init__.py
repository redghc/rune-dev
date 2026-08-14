"""Receivers subpackage — IR/RF listen paths.

- :mod:`native_ir` — ``infrared.async_subscribe_receiver`` (HA 2026.6+).
- :mod:`broadlink_rf` — Broadlink sweep + capture (the only RF RX path).
- :mod:`esphome_legacy_ir` — ESPHome ``esphome.remote_received`` event bus
  (pre-2026.6 fallback when native IR is unavailable).
- :mod:`mock` — in-process capture for tests.
- :mod:`factory` — picks an adapter from a receiver ``entity_id``.

All adapters subscribe to one receiver entity at a time. The sniffer
engine wires one adapter per receiver and multiplexes the captures
into the matcher pipeline.
"""
