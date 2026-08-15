"""Fan platform — :class:`RuneFanEntity` with discrete / percentage / hybrid.

RUNE fans expose one HA ``FanEntity`` per RuneDevice. The speed model
is configurable per-device via :attr:`SpeedMode`:

- ``PERCENTAGE`` — 0..100 only. Each percentage maps to one discrete
  step via :class:`SpeedMapper` (HA convention).
- ``DISCRETE`` — 1..N only. No percentage exposed.
- ``HYBRID`` — both percentage and discrete (the default).

State handling:

- Optimistic: RUNE always assumes the requested speed/state took
  effect, since RF is one-way. The :class:`SpeedMapper` keeps the
  displayed state coherent with what was last sent.
- Power monitor (optional): when configured, the verdict signal
  updates ``is_on`` to match the physical wattage.

Sending commands:

- ``async_turn_on(percentage=…)`` — sends the discrete command for the
  mapped step (e.g. ``speed_2``).
- ``async_turn_off`` — sends the ``off`` command.
- ``async_set_percentage(percent)`` — same as turn_on with a percentage.

The fan also exposes the discrete speed commands as button entities
via the button platform (e.g. ``speed_1`` → button entity).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.rune._platform_support._base import RunePlatformBase
from custom_components.rune.domain.enums import EntityCategory
from custom_components.rune.domain.mappers.speed_mapper import SpeedMapper
from custom_components.rune.domain.models import RuneDevice

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class RuneFanEntity(RunePlatformBase):
    """One HA fan entity per RuneDevice."""

    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(
        self,
        *,
        device: RuneDevice,
        coordinator: Any,
    ) -> None:
        super().__init__(device=device, coordinator=coordinator)
        self._is_on: bool = False
        self._percentage: int | None = None

    # ------------------------------------------------------------------
    # HA FanEntity properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._device.name

    @property
    def unique_id(self) -> str:
        return f"rune_{self._device.id}_fan"

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def percentage(self) -> int | None:
        if not self._is_on:
            return 0
        return self._percentage

    @property
    def speed_count(self) -> int:
        return self._device.discrete_speed_count

    @property
    def supported_features(self) -> int:
        try:
            from homeassistant.components.fan import FanEntityFeature
        except ImportError:
            return 0

        return (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )

    # ------------------------------------------------------------------
    # HA FanEntity service handlers
    # ------------------------------------------------------------------

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        # No percentage: resume last speed or step 1.
        if self._device.commands.get("on"):
            await self.async_send_pulse("on")
            self._is_on = True
            self._percentage = SpeedMapper.discrete_to_percent(
                1, self._device.discrete_speed_count
            )
        else:
            step = self._current_step() or 1
            await self._send_speed_step(step)
            self._is_on = True
            self._percentage = SpeedMapper.discrete_to_percent(
                step, self._device.discrete_speed_count
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._device.commands.get("off"):
            await self.async_send_pulse("off")
        self._is_on = False
        self._percentage = 0

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage <= 0:
            await self.async_turn_off()
            return
        step = SpeedMapper.percent_to_discrete(percentage, self._device.discrete_speed_count)
        await self._send_speed_step(step)
        self._is_on = True
        self._percentage = SpeedMapper.discrete_to_percent(step, self._device.discrete_speed_count)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _current_step(self) -> int | None:
        if self._percentage is None or self._percentage <= 0:
            return None
        return SpeedMapper.percent_to_discrete(
            self._percentage, self._device.discrete_speed_count
        )

    async def _send_speed_step(self, step: int) -> None:
        key = f"speed_{step}"
        if key not in self._device.commands:
            self.warn_unsupported(f"speed step {step}")
            return
        await self.async_send_pulse(key)

    def device_info_extra(self) -> dict:
        return {"identifiers": {("rune", self._device.id)}}


class RuneFanPlatform:
    """Fan platform factory."""

    PLATFORM = "fan"

    def __init__(self, hass: Any, coordinator: Any) -> None:
        self._hass = hass
        self._coordinator = coordinator

    async def async_setup_platform(
        self, async_add_entities, discovery_info=None
    ) -> None:
        devices = await self._coordinator._devices.load()  # type: ignore[attr-defined]
        entities = [
            RuneFanEntity(device=d, coordinator=self._coordinator)
            for d in devices
            if d.category == EntityCategory.FAN
        ]
        async_add_entities(entities)


__all__ = ["RuneFanEntity", "RuneFanPlatform", "SpeedMapper"]
