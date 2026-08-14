"""Ports package — abstract interfaces for every external dependency.

A port declares a contract (Python ``Protocol`` or ``ABC``) the domain
depends on. Adapters in ``custom_components.rune.adapters`` implement
those contracts against concrete systems (Home Assistant Store, native
infrared, Broadlink, ESPHome, etc.).

Rules:

- Ports may NOT import from ``homeassistant.*``. They are pure Python.
- Ports may import from ``custom_components.rune.domain``.
- One port = one responsibility.
"""
