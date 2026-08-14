"""Power monitor port — listen to a wattage sensor and emit verdicts.

When a device has a ``power_sensor_entity_id`` configured, the power
monitor watches it. When the reading crosses ``power_off_below_w``
(or ``power_on_above_w``) the monitor dispatches a ``PowerVerdict``
on its callback channel so platform entities can correct their
optimistic state.

This port is optional: a device with no power monitor just won't have
one wired up. Adapters translate HA state-change events into verdicts.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class PowerVerdict(StrEnum):
    """Result of evaluating the current wattage against thresholds."""

    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PowerReading:
    """A single evaluation of a power-sensor reading."""

    device_id: str
    verdict: PowerVerdict
    watts: float | None


PowerCallback = Callable[[PowerReading], None]


class PowerMonitorPort(Protocol):
    """Watches a single power sensor for one RuneDevice."""

    device_id: str
    sensor_entity_id: str
    off_below_w: float
    on_above_w: float

    @property
    def is_available(self) -> bool:
        """True when the sensor entity is loaded."""
        ...

    def start(self, on_verdict: PowerCallback) -> Callable[[], None]:
        """Begin watching the sensor.

        Returns an unsubscribe callable. Implementations MUST debounce
        rapid state changes (the wattage of a fan starting up bounces
        for several seconds before stabilizing).
        """
        ...

    def stop(self) -> None:
        """Detach and release resources."""
        ...
