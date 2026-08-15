"""Switch platform — :class:`RuneSwitchEntity`.

Binary on/off entity per SWITCH device. RUNE assumes optimistic state
— the switch is "on" after a successful ``on`` command until either
an explicit ``off`` command or a power-monitor verdict says otherwise.

Optional power-monitor wiring:

- When :attr:`RuneDevice.power_sensor_entity_id` is set, the coordinator
  attaches a :class:`HAPowerMonitor`. Its verdicts update the
  switch's ``is_on`` to match the physical wattage.
- The verdict is the only feedback path; without it, ``is_on`` tracks
  the last sent command.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.rune._platform_support._base import RunePlatformBase
from custom_components.rune.domain.enums import EntityCategory

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class RuneSwitchEntity(RunePlatformBase):
    """One HA switch entity per RuneDevice (category SWITCH)."""

    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(self, *, device, coordinator) -> None:
        super().__init__(device=device, coordinator=coordinator)
        self._is_on: bool = False

    @property
    def name(self) -> str:
        return self._device.name

    @property
    def unique_id(self) -> str:
        return f"rune_{self._device.id}_switch"

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def supported_features(self) -> int:
        return 0  # implicit TURN_ON/TURN_OFF

    # ------------------------------------------------------------------
    # Service handlers
    # ------------------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        if "on" not in self._device.commands:
            self.warn_unsupported("turn_on")
            return
        await self.async_send_pulse("on")
        self._is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        if "off" not in self._device.commands:
            self.warn_unsupported("turn_off")
            return
        await self.async_send_pulse("off")
        self._is_on = False

    def apply_power_verdict(self, is_on: bool) -> None:
        """Update state from a power-monitor verdict (in-place)."""
        if self._is_on != is_on:
            self._is_on = is_on

    def device_info_extra(self) -> dict:
        return {"identifiers": {("rune", self._device.id)}}


class RuneSwitchPlatform:
    PLATFORM = "switch"

    def __init__(self, hass: Any, coordinator: Any) -> None:
        self._hass = hass
        self._coordinator = coordinator

    async def async_setup_platform(
        self, async_add_entities, discovery_info=None
    ) -> None:
        devices = await self._coordinator._devices.load()  # type: ignore[attr-defined]
        entities = [
            RuneSwitchEntity(device=d, coordinator=self._coordinator)
            for d in devices
            if d.category == EntityCategory.SWITCH
        ]
        async_add_entities(entities)


__all__ = ["RuneSwitchEntity", "RuneSwitchPlatform"]
