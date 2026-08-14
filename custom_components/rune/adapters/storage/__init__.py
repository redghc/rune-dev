"""Storage subpackage — repository implementations.

- :mod:`memory` — in-memory test/development adapters (zero deps).
- :mod:`ha_store` — Home Assistant Store adapters (Phase 2 deliverable).
- :mod:`profile_cache` — SmartIR-style profile cache (Phase 7).

Adapters here may import from ``homeassistant.*``. Everything outside
``adapters/`` must remain HA-free.
"""
