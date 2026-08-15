"""Remote platform — :class:`RuneRemoteEntity`.

Generic remote board: exposes every command as a HA
:class:`RemoteEntity` ``command`` list. Users send raw commands via
``remote.send_command`` and the coordinator picks the matching
PulseCommand and dispatches it.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.rune._platform_support._base import RunePlatformBase
from custom_components.rune.domain.enums import EntityCategory

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class RuneRemoteEntity(RunePlatformBase):
    """One HA remote per RuneDevice (category REMOTE)."""

    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(self, *, device, coordinator) -> None:
        super().__init__(device=device, coordinator=coordinator)

    @property
    def name(self) -> str:
        return self._device.name

    @property
    def unique_id(self) -> str:
        return f"rune_{self._device.id}_remote"

    @property
    def supported_features(self) -> int:
        try:
            from homeassistant.components.remote import RemoteEntityFeature
        except ImportError:
            return 0
        return RemoteEntityFeature.LEARN_COMMAND

    async def async_send_command(
        self,
        command: list[str] | str,
        **kwargs: Any,
    ) -> None:
        command_list = [command] if isinstance(command, str) else list(command)
        for key in command_list:
            if key in self._device.commands:
                await self.async_send_pulse(key)

    def device_info_extra(self) -> dict:
        return {"identifiers": {("rune", self._device.id)}}


class RuneRemotePlatform:
    PLATFORM = "remote"

    def __init__(self, hass: Any, coordinator: Any) -> None:
        self._hass = hass
        self._coordinator = coordinator

    async def async_setup_platform(
        self, async_add_entities, discovery_info=None
    ) -> None:
        devices = await self._coordinator._devices.load()  # type: ignore[attr-defined]
        entities = [
            RuneRemoteEntity(device=d, coordinator=self._coordinator)
            for d in devices
            if d.category == EntityCategory.REMOTE
        ]
        async_add_entities(entities)


__all__ = ["RuneRemoteEntity", "RuneRemotePlatform"]
