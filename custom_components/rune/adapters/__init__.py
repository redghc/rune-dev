"""Adapters package — concrete implementations of every port.

Subpackages group adapters by what they talk to:

- ``storage`` — repositories (in-memory + Home Assistant Store)
- ``transmitters`` — IR/RF send paths (Phase 3)
- ``receivers`` — IR/RF listen paths (Phase 3)
- ``capture`` — capture orchestrator + providers (Phase 4)
- ``power_monitor`` — wattage-sensor watcher (Phase 4)

``factory.py`` wires ports to adapters at integration startup.
"""
