"""Power monitor adapter — watches a wattage sensor and emits verdicts.

When a :class:`~custom_components.rune.domain.models.RuneDevice` has a
``power_sensor_entity_id`` configured, the power monitor watches the
sensor's state. The verdict logic:

- Reading ``<= power_off_below_w`` → :attr:`PowerVerdict.OFF`.
- Reading ``>= power_on_above_w`` → :attr:`PowerVerdict.ON`.
- In between (or first sample) → :attr:`PowerVerdict.UNKNOWN`.

The monitor debounces: only fire a verdict when the new state differs
from the last verdict AND at least ``debounce_seconds`` have passed
since the last verdict. This filters out the bouncing wattage of a
fan starting up.

Public surface:

- :class:`HAPowerMonitor` — the production adapter. Wraps a HA sensor
  state-change listener.
- :class:`InMemoryPowerMonitor` — in-process test double. Useful for
  unit tests that need to inject wattage readings.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from custom_components.rune.const import (
    DEFAULT_POWER_OFF_BELOW_W,
    DEFAULT_POWER_ON_ABOVE_W,
)
from custom_components.rune.domain.time import monotonic_seconds
from custom_components.rune.ports.power_monitor import (
    PowerCallback,
    PowerMonitorPort,
    PowerReading,
    PowerVerdict,
)

_LOGGER = logging.getLogger(__name__)


def classify_reading(
    *,
    watts: float | None,
    on_above_w: float,
    off_below_w: float,
) -> PowerVerdict:
    """Return the verdict for a wattage reading.

    Pure — no I/O. Symmetric around the gap between the two
    thresholds to avoid oscillation at the boundary.
    """
    if watts is None:
        return PowerVerdict.UNKNOWN
    if watts >= on_above_w:
        return PowerVerdict.ON
    if watts <= off_below_w:
        return PowerVerdict.OFF
    return PowerVerdict.UNKNOWN


class HAPowerMonitor(PowerMonitorPort):
    """Production power monitor — watches a HA sensor via state-change events."""

    def __init__(
        self,
        hass: Any,
        *,
        device_id: str,
        sensor_entity_id: str,
        off_below_w: float = DEFAULT_POWER_OFF_BELOW_W,
        on_above_w: float = DEFAULT_POWER_ON_ABOVE_W,
        debounce_seconds: float = 2.0,
    ) -> None:
        self._hass = hass
        self.device_id = device_id
        self.sensor_entity_id = sensor_entity_id
        self.off_below_w = off_below_w
        self.on_above_w = on_above_w
        self._debounce_seconds = debounce_seconds
        self._unsub: Callable[[], None] | None = None
        self._last_verdict: PowerVerdict | None = None
        self._last_verdict_monotonic: float = 0.0

    @property
    def is_available(self) -> bool:
        state = self._hass.states.get(self.sensor_entity_id)
        return state is not None and state.state not in ("unknown", "unavailable")

    def start(self, on_verdict: PowerCallback) -> Callable[[], None]:
        """Begin watching the sensor."""
        try:
            from homeassistant.core import callback
        except ImportError as err:
            raise RuntimeError("homeassistant.core is unavailable") from err

        @callback  # type: ignore[misc]
        def _on_state_change(event: Any) -> None:
            new_state = event.data.get("new_state")
            if new_state is None:
                return
            try:
                watts = float(new_state.state)
            except (TypeError, ValueError):
                return
            self._evaluate_and_emit(watts, on_verdict)

        try:
            from homeassistant.helpers.event import async_track_state_change_event
        except ImportError as err:
            raise RuntimeError("homeassistant.helpers.event is unavailable") from err

        self._unsub = async_track_state_change_event(
            self._hass,
            [self.sensor_entity_id],
            _on_state_change,
        )

        # Seed with the current reading so the platform entity has
        # an initial verdict to sync to.
        current_state = self._hass.states.get(self.sensor_entity_id)
        if current_state is not None:
            try:
                watts = float(current_state.state)
                self._evaluate_and_emit(watts, on_verdict)
            except (TypeError, ValueError):
                pass

        def _stop() -> None:
            if self._unsub is not None:
                self._unsub()
                self._unsub = None

        return _stop

    def stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    def _evaluate_and_emit(self, watts: float, on_verdict: PowerCallback) -> None:
        verdict = classify_reading(
            watts=watts,
            on_above_w=self.on_above_w,
            off_below_w=self.off_below_w,
        )
        now = monotonic_seconds()
        if verdict == self._last_verdict:
            return
        # Always fire the first verdict (no prior debounce deadline).
        # For subsequent transitions, suppress ones inside the debounce
        # window so a fan-startup bounce doesn't fire ON → OFF → ON.
        if (
            self._last_verdict is not None
            and now - self._last_verdict_monotonic < self._debounce_seconds
        ):
            return
        self._last_verdict = verdict
        self._last_verdict_monotonic = now
        on_verdict(
            PowerReading(
                device_id=self.device_id,
                verdict=verdict,
                watts=watts,
            )
        )


class InMemoryPowerMonitor(PowerMonitorPort):
    """In-process power monitor — accepts wattage via :meth:`inject`."""

    def __init__(
        self,
        *,
        device_id: str,
        sensor_entity_id: str = "sensor.test_power",
        off_below_w: float = DEFAULT_POWER_OFF_BELOW_W,
        on_above_w: float = DEFAULT_POWER_ON_ABOVE_W,
        debounce_seconds: float = 0.0,
        monotonic: Callable[[], float] = monotonic_seconds,
    ) -> None:
        self.device_id = device_id
        self.sensor_entity_id = sensor_entity_id
        self.off_below_w = off_below_w
        self.on_above_w = on_above_w
        self._debounce_seconds = debounce_seconds
        self._monotonic = monotonic
        self._on_verdict: PowerCallback | None = None
        self._last_verdict: PowerVerdict | None = None
        self._last_verdict_monotonic: float = 0.0
        self._last_reading: PowerReading | None = None

    @property
    def is_available(self) -> bool:
        return True

    def start(self, on_verdict: PowerCallback) -> Callable[[], None]:
        self._on_verdict = on_verdict

        def _stop() -> None:
            self._on_verdict = None

        return _stop

    def stop(self) -> None:
        self._on_verdict = None

    def inject(self, watts: float | None) -> None:
        """Push a synthetic wattage reading into the monitor."""
        verdict = classify_reading(
            watts=watts,
            on_above_w=self.on_above_w,
            off_below_w=self.off_below_w,
        )
        now = self._monotonic()
        if verdict == self._last_verdict:
            self._last_reading = PowerReading(
                device_id=self.device_id,
                verdict=verdict,
                watts=watts,
            )
            return
        # Always fire the first verdict (no prior debounce).
        if (
            self._last_verdict is not None
            and now - self._last_verdict_monotonic < self._debounce_seconds
        ):
            return
        self._last_verdict = verdict
        self._last_verdict_monotonic = now
        self._last_reading = PowerReading(
            device_id=self.device_id,
            verdict=verdict,
            watts=watts,
        )
        if self._on_verdict is not None:
            self._on_verdict(self._last_reading)

    @property
    def last_reading(self) -> PowerReading | None:
        return self._last_reading


__all__ = [
    "HAPowerMonitor",
    "InMemoryPowerMonitor",
    "classify_reading",
]
