"""Base class shared by every RUNE platform entity.

Every platform entity:

- Holds a reference to its parent :class:`RuneDevice`.
- Holds a reference to the :class:`DevicePlatformCoordinator` for TX.
- Implements ``async_send_pulse(command_key)`` — the standard way to
  fire a learned command.
- Tracks its own sub-role string (``""`` for primary entities,
  e.g. ``"speed_3"`` for sub-buttons).

This base class does NOT subclass any HA entity — each platform file
mixes it in via multiple inheritance. That keeps the HA-specific
imports confined to the platform files and makes the base unit-
testable in isolation.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.rune.domain.errors import (
    CommandNotLearnedError,
)
from custom_components.rune.domain.models import RuneDevice

if TYPE_CHECKING:
    from custom_components.rune.platforms._coordinator import (
        DevicePlatformCoordinator,
    )


class RunePlatformBase:
    """Mixin: shared helpers for every RUNE platform entity."""

    _attr_has_entity_name: bool = True
    _attr_should_poll: bool = False

    def __init__(
        self,
        *,
        device: RuneDevice,
        coordinator: DevicePlatformCoordinator,
        sub_role: str = "",
    ) -> None:
        self._device = device
        self._coordinator = coordinator
        self._sub_role = sub_role

    @property
    def device(self) -> RuneDevice:
        return self._device

    @property
    def sub_role(self) -> str:
        return self._sub_role

    @property
    def unique_id_suffix(self) -> str:
        """Stable suffix appended to every entity's unique_id."""
        return self._sub_role if self._sub_role else "primary"

    async def async_send_pulse(self, command_key: str) -> None:
        """Fire the pulse bound to ``command_key`` on this device."""
        command = self._device.commands.get(command_key)
        if command is None:
            raise CommandNotLearnedError(
                f"Device {self._device.id} has no command {command_key!r}"
            )
        await self._coordinator.async_send_command(
            device=self._device, command=command
        )

    async def async_send_command(self, command) -> None:
        """Variant that takes an explicit PulseCommand."""
        await self._coordinator.async_send_command(
            device=self._device, command=command
        )

    def device_info(self) -> dict:
        """Build the DeviceInfo dict for HA's device registry.

        Subclasses override ``device_info_extra`` to add platform-
        specific fields (manufacturer, model).
        """
        info: dict = {
            "identifiers": {("rune", self._device.id)},
            "name": self._device.name,
        }
        if self._device.manufacturer:
            info["manufacturer"] = self._device.manufacturer
        if self._device.model:
            info["model"] = self._device.model
        info.update(self.device_info_extra())
        return info

    def device_info_extra(self) -> dict:
        """Hook for subclasses to append platform-specific fields."""
        return {}

    def warn_unsupported(self, capability: str) -> None:
        """Log when an action is unsupported for the device's transport."""
        import logging

        logging.getLogger(__name__).debug(
            "rune: device %s (%s) does not support %s",
            self._device.id,
            self._device.category.value,
            capability,
        )


__all__ = ["RunePlatformBase"]
