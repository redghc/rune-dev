"""Pulse button platform — one ButtonEntity per PulseCommand.

Every RuneDevice exposes its commands as standalone button entities:

- ``button.<device>_power_on`` — fires the learned ``power_on`` pulse.
- ``button.<device>_speed_3`` — fires the ``speed_3`` pulse (for fans).

For fans, climate, lights, covers, etc., the command keys are
auto-derived from the device category (e.g. ``off``, ``speed_1`` … ``speed_N``
for fans). The user's command key naming drives the entity ID; the
button's name is the command's human-readable ``label``.

Sub-entities:

- For fan devices, each ``speed_N`` command is ALSO exposed as a
  dedicated ``button.<device>_speed_n`` sub-entity, mirroring how
  HA's own fan platform exposes individual speed buttons.
- For cover devices, ``open``, ``close``, and (when present) ``stop``
  are exposed as buttons alongside the cover entity.

The platform is intentionally thin: it does NOT compute the button's
state (a button has no state beyond the last-press timestamp). All the
work is in :meth:`async_press` which delegates to the coordinator.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.rune._platform_support._base import RunePlatformBase
from custom_components.rune.domain.enums import (
    CommandCategory,
)

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class RunePulseButtonEntity(RunePlatformBase):
    """A pressable button that sends one learned pulse."""

    _attr_available = True

    def __init__(
        self,
        *,
        device,
        coordinator,
        command_key: str,
        command_label: str,
        command_category: CommandCategory,
        sub_role: str = "",
    ) -> None:
        super().__init__(device=device, coordinator=coordinator, sub_role=sub_role)
        self._command_key = command_key
        self._command_label = command_label
        self._command_category = command_category

    @property
    def command_key(self) -> str:
        return self._command_key

    @property
    def command_label(self) -> str:
        return self._command_label

    @property
    def command_category(self) -> CommandCategory:
        return self._command_category

    @property
    def name(self) -> str:
        return self._command_label or self._command_key

    @property
    def unique_id(self) -> str:
        return f"rune_{self._device.id}_{self.unique_id_suffix}"

    async def async_press(self) -> None:
        await self.async_send_pulse(self._command_key)

    def device_info_extra(self) -> dict:
        return {"identifiers": {("rune", self._device.id)}}


class RuneButtonPlatform:
    """Factory: enumerate RuneDevice commands into button entities.

    Public surface: :meth:`async_setup_platform` which HA calls.
    """

    PLATFORM = "button"

    def __init__(self, hass: Any, coordinator: Any) -> None:
        self._hass = hass
        self._coordinator = coordinator

    async def async_setup_platform(
        self, async_add_entities, discovery_info=None
    ) -> None:
        """Build one button entity per PulseCommand on every device."""
        devices = await self._coordinator._devices.load()  # type: ignore[attr-defined]
        entities: list[RunePulseButtonEntity] = []
        for device in devices:
            entities.extend(self._build_for_device(device))
        async_add_entities(entities)

    def _build_for_device(self, device) -> list[RunePulseButtonEntity]:
        entities: list[RunePulseButtonEntity] = []
        for key, command in device.commands.items():
            entities.append(
                RunePulseButtonEntity(
                    device=device,
                    coordinator=self._coordinator,
                    command_key=key,
                    command_label=command.label,
                    command_category=command.category,
                )
            )
        return entities


__all__ = ["RuneButtonPlatform", "RunePulseButtonEntity"]
