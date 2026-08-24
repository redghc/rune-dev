"""Cover platform — :class:`RuneCoverEntity`.

Maps device commands to HA cover service calls:

- ``open`` → ``async_open_cover``
- ``close`` → ``async_close_cover``
- ``stop`` (when present) → ``async_stop_cover``

Position is inferred when ``position_open`` / ``position_close``
commands are present. Otherwise the cover is reported as
``is_closed = None`` (state unknown) — RUNE cannot read the physical
position.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.rune._platform_support._base import RunePlatformBase
from custom_components.rune.domain.enums import EntityCategory

if TYPE_CHECKING:
    pass

try:
    from homeassistant.components.cover import CoverEntity as _CoverEntityBase
except ImportError:

    class _CoverEntityBase:  # type: ignore[no-redef]
        """Fallback base when ``homeassistant`` is not installed."""


_LOGGER = logging.getLogger(__name__)


class RuneCoverEntity(RunePlatformBase, _CoverEntityBase):
    """One HA cover entity per RuneDevice (category COVER)."""

    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(self, *, device, coordinator) -> None:
        super().__init__(device=device, coordinator=coordinator)
        self._is_closed: bool | None = None
        self._is_opening: bool = False
        self._is_closing: bool = False

    @property
    def name(self) -> str:
        return self._device.name

    @property
    def unique_id(self) -> str:
        return f"rune_{self._device.id}_cover"

    @property
    def is_closed(self) -> bool | None:
        return self._is_closed

    @property
    def is_opening(self) -> bool:
        return self._is_opening

    @property
    def is_closing(self) -> bool:
        return self._is_closing

    @property
    def supported_features(self) -> int:
        try:
            from homeassistant.components.cover import CoverEntityFeature
        except ImportError:
            return 0

        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        if "stop" in self._device.commands:
            features |= CoverEntityFeature.STOP
        if "position_open" in self._device.commands or "position_close" in self._device.commands:
            features |= CoverEntityFeature.SET_POSITION
        return features

    # ------------------------------------------------------------------
    # Service handlers
    # ------------------------------------------------------------------

    async def async_open_cover(self, **kwargs: Any) -> None:
        if "open" in self._device.commands:
            await self.async_send_pulse("open")
        self._is_closed = False

    async def async_close_cover(self, **kwargs: Any) -> None:
        if "close" in self._device.commands:
            await self.async_send_pulse("close")
        self._is_closed = True

    async def async_stop_cover(self, **kwargs: Any) -> None:
        if "stop" in self._device.commands:
            await self.async_send_pulse("stop")

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        position = kwargs.get("position")
        if position is None:
            return
        # Snap to discrete position commands when available.
        if position >= 50 and "position_open" in self._device.commands:
            await self.async_send_pulse("position_open")
            self._is_closed = False
        elif position < 50 and "position_close" in self._device.commands:
            await self.async_send_pulse("position_close")
            self._is_closed = True

    def device_info_extra(self) -> dict:
        return {"identifiers": {("rune", self._device.id)}}


class RuneCoverPlatform:
    PLATFORM = "cover"

    def __init__(self, hass: Any, coordinator: Any) -> None:
        self._hass = hass
        self._coordinator = coordinator

    async def async_setup_platform(
        self, async_add_entities, discovery_info=None
    ) -> None:
        devices = await self._coordinator._devices.load()  # type: ignore[attr-defined]
        entities = [
            RuneCoverEntity(device=d, coordinator=self._coordinator)
            for d in devices
            if d.category == EntityCategory.COVER
        ]
        async_add_entities(entities)

    def build_entities_for_device(self, device):
        if device.category != EntityCategory.COVER:
            return []
        return [RuneCoverEntity(device=device, coordinator=self._coordinator)]


async def async_setup_entry(hass: Any, entry: Any, async_add_entities: Any) -> None:
    """HA entry-setup hook for the cover platform."""
    from custom_components.rune._platform_support.setup import setup_rune_platform

    await setup_rune_platform(
        hass=hass,
        entry=entry,
        async_add_entities=async_add_entities,
        platform_name="cover",
        platform_cls=RuneCoverPlatform,
    )


__all__ = ["RuneCoverEntity", "RuneCoverPlatform", "async_setup_entry"]
