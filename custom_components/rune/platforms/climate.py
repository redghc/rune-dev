"""Climate platform — :class:`RuneClimateEntity`.

Single HVAC entity per CLIMATE device. Two operating modes:

- **Preset mode** (default): the device carries a fixed set of
  discrete commands — ``mode_cool``, ``mode_heat``, ``fan_low``,
  ``fan_med``, ``fan_high``, ``temp_18`` … ``temp_30``, etc. The
  entity translates user actions to the matching command.
- **Matrix mode**: when ``RuneDevice.climate_matrix`` is True, the
  full HVAC state is encoded as a matrix cell. (The lattice file is
  loaded separately — Phase 7.)

The platform is intentionally minimal: most of the heavy lifting
(matrix expansion, command lookup) lives in the domain layer. The
entity just routes user actions.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.rune.domain.enums import EntityCategory
from custom_components.rune.platforms._base import RunePlatformBase

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


# Mapping from HA HVAC modes to command-key fragments. Used by the
# preset-mode dispatcher.
_HVAC_MODE_FRAGMENT = {
    "cool": "mode_cool",
    "heat": "mode_heat",
    "fan_only": "mode_fan_only",
    "dry": "mode_dry",
    "auto": "mode_auto",
    "off": "off",
}


class RuneClimateEntity(RunePlatformBase):
    """One HA climate entity per RuneDevice (category CLIMATE)."""

    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(self, *, device, coordinator) -> None:
        super().__init__(device=device, coordinator=coordinator)
        self._hvac_mode: str | None = None
        self._target_temperature: float | None = None
        self._fan_mode: str | None = None

    @property
    def name(self) -> str:
        return self._device.name

    @property
    def unique_id(self) -> str:
        return f"rune_{self._device.id}_climate"

    @property
    def hvac_mode(self) -> str | None:
        return self._hvac_mode

    @property
    def target_temperature(self) -> float | None:
        return self._target_temperature

    @property
    def fan_mode(self) -> str | None:
        return self._fan_mode

    @property
    def supported_features(self) -> int:
        try:
            from homeassistant.components.climate import ClimateEntityFeature
        except ImportError:
            return 0

        features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
        )
        return features

    @property
    def hvac_modes(self) -> list[str]:
        # Always offer the basics; the dispatcher checks availability.
        return ["off", "cool", "heat", "fan_only", "dry", "auto"]

    @property
    def fan_modes(self) -> list[str]:
        return self._available_fan_modes()

    @property
    def min_temp(self) -> float:
        return 16.0

    @property
    def max_temp(self) -> float:
        return 30.0

    # ------------------------------------------------------------------
    # Service handlers
    # ------------------------------------------------------------------

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        fragment = _HVAC_MODE_FRAGMENT.get(hvac_mode, f"mode_{hvac_mode}")
        command_key = fragment if fragment in self._device.commands else None
        if command_key is None:
            self.warn_unsupported(f"hvac_mode {hvac_mode}")
            return
        await self.async_send_pulse(command_key)
        self._hvac_mode = hvac_mode

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode("cool")

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode("off")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        target = kwargs.get("temperature")
        if target is None:
            return
        rounded = round(target)
        command_key = f"temp_{rounded}"
        if command_key not in self._device.commands:
            self.warn_unsupported(f"temperature {rounded}")
            return
        await self.async_send_pulse(command_key)
        self._target_temperature = float(rounded)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        command_key = f"fan_{fan_mode}"
        if command_key not in self._device.commands:
            self.warn_unsupported(f"fan_mode {fan_mode}")
            return
        await self.async_send_pulse(command_key)
        self._fan_mode = fan_mode

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _available_fan_modes(self) -> list[str]:
        modes: list[str] = []
        for candidate in ("low", "med", "high", "auto"):
            if f"fan_{candidate}" in self._device.commands:
                modes.append(candidate)
        return modes

    def device_info_extra(self) -> dict:
        return {"identifiers": {("rune", self._device.id)}}


class RuneClimatePlatform:
    PLATFORM = "climate"

    def __init__(self, hass: Any, coordinator: Any) -> None:
        self._hass = hass
        self._coordinator = coordinator

    async def async_setup_platform(
        self, async_add_entities, discovery_info=None
    ) -> None:
        devices = await self._coordinator._devices.load()  # type: ignore[attr-defined]
        entities = [
            RuneClimateEntity(device=d, coordinator=self._coordinator)
            for d in devices
            if d.category == EntityCategory.CLIMATE
        ]
        async_add_entities(entities)


__all__ = ["RuneClimateEntity", "RuneClimatePlatform"]
