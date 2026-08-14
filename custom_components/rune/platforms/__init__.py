"""HA platform adapters — thin entity shells for each device category.

The :file:`_coordinator.py` module wires RuneDevice aggregates to HA
platform entities. Each platform file (:file:`fan.py`,
:file:`climate.py`, etc.) is a *thin shell* — it instantiates one HA
entity per RuneDevice and delegates TX / state logic to the domain
mappers and the TX gate.

The platform layer is allowed to import from ``homeassistant.*``. It
does NOT touch the domain directly except through the domain mappers
(:file:`domain/mappers/speed_mapper.py`, etc.) and the model layer
(:file:`domain/models.py`).
"""
