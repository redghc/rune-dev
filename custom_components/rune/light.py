"""Light platform — :class:`RuneLightEntity`.

Two modes inferred from the command set:

- **On/Off only**: when the device has ``on`` and ``off`` commands
  but no ``brightness_*`` commands.
- **Brightness**: when ``brightness_*`` commands are present. The
  number of steps is inferred from the count of ``brightness_N`` keys.

Commands are dispatched through the coordinator. The light's state is
optimistic — there's no feedback path from the bulb to RUNE.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.rune._platform_support._base import RunePlatformBase
from custom_components.rune.domain.enums import EntityCategory
from custom_components.rune.domain.mappers.speed_mapper import SpeedMapper

if TYPE_CHECKING:
    pass

try:
    from homeassistant.components.light import LightEntity as _LightEntityBase
except ImportError:

    class _LightEntityBase:  # type: ignore[no-redef]
        """Fallback base when ``homeassistant`` is not installed."""


_LOGGER = logging.getLogger(__name__)


class RuneLightEntity(RunePlatformBase, _LightEntityBase):
    """One HA light entity per RuneDevice (category LIGHT)."""

    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(self, *, device, coordinator) -> None:
        super().__init__(device=device, coordinator=coordinator)
        self._is_on: bool = False
        self._brightness: int | None = None
        self._brightness_steps: list[int] = self._detect_brightness_steps()

    @property
    def name(self) -> str:
        return self._device.name

    @property
    def unique_id(self) -> str:
        return f"rune_{self._device.id}_light"

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def brightness(self) -> int | None:
        return self._brightness if self._is_on else None

    @property
    def brightness_steps(self) -> list[int]:
        return list(self._brightness_steps)

    @property
    def color_mode(self) -> str:
        try:
            from homeassistant.components.light import ColorMode
        except ImportError:
            return "onoff" if not self._brightness_steps else "brightness"
        if self._brightness_steps:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[str]:
        return {self.color_mode}

    @property
    def supported_features(self) -> int:
        return 0  # TURN_ON / TURN_OFF are implicit

    # ------------------------------------------------------------------
    # Service handlers
    # ------------------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        brightness = kwargs.get("brightness")
        if brightness is not None and self._brightness_steps:
            await self._send_brightness(brightness)
            self._brightness = brightness
        elif "on" in self._device.commands:
            await self.async_send_pulse("on")
        elif self._brightness_steps:
            # Default to max brightness.
            await self._send_brightness(255)
            self._brightness = 255
        else:
            self.warn_unsupported("turn_on")
            return
        self._is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        if "off" in self._device.commands:
            await self.async_send_pulse("off")
        self._is_on = False
        self._brightness = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_brightness_steps(self) -> list[int]:
        steps: list[int] = []
        for key in self._device.commands:
            if key.startswith("brightness_"):
                try:
                    steps.append(int(key.removeprefix("brightness_")))
                except ValueError:
                    continue
        return sorted(steps)

    async def _send_brightness(self, target_brightness: int) -> None:
        if not self._brightness_steps:
            return
        step = SpeedMapper.percent_to_discrete(
            int(target_brightness / 255 * 100),
            len(self._brightness_steps),
        )
        key = f"brightness_{self._brightness_steps[step - 1]}"
        await self.async_send_pulse(key)

    def device_info_extra(self) -> dict:
        return {"identifiers": {("rune", self._device.id)}}


class RuneLightPlatform:
    PLATFORM = "light"

    def __init__(self, hass: Any, coordinator: Any) -> None:
        self._hass = hass
        self._coordinator = coordinator

    async def async_setup_platform(
        self, async_add_entities, discovery_info=None
    ) -> None:
        devices = await self._coordinator._devices.load()  # type: ignore[attr-defined]
        entities = [
            RuneLightEntity(device=d, coordinator=self._coordinator)
            for d in devices
            if d.category == EntityCategory.LIGHT
        ]
        async_add_entities(entities)

    def build_entities_for_device(self, device):
        if device.category != EntityCategory.LIGHT:
            return []
        return [RuneLightEntity(device=device, coordinator=self._coordinator)]


async def async_setup_entry(hass: Any, entry: Any, async_add_entities: Any) -> None:
    """HA entry-setup hook for the light platform."""
    from custom_components.rune._platform_support.setup import setup_rune_platform

    await setup_rune_platform(
        hass=hass,
        entry=entry,
        async_add_entities=async_add_entities,
        platform_name="light",
        platform_cls=RuneLightPlatform,
    )


__all__ = ["RuneLightEntity", "RuneLightPlatform", "async_setup_entry"]
