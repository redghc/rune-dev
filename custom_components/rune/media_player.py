"""Media player platform — :class:`RuneMediaPlayerEntity`.

Thin shell mapping commands to actions:

- ``power_on`` / ``power_off`` → ``turn_on`` / ``turn_off``
- ``volume_up`` / ``volume_down`` / ``mute``
- ``play`` / ``pause`` / ``stop`` / ``next`` / ``previous``
- ``source_<name>`` → HA source selection

Source list is inferred from ``source_*`` command keys.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.rune._platform_support._base import RunePlatformBase
from custom_components.rune.domain.enums import EntityCategory

if TYPE_CHECKING:
    pass

try:
    from homeassistant.components.media_player import (
        MediaPlayerEntity as _MediaPlayerEntityBase,
    )
except ImportError:

    class _MediaPlayerEntityBase:  # type: ignore[no-redef]
        """Fallback base when ``homeassistant`` is not installed."""


_LOGGER = logging.getLogger(__name__)


class RuneMediaPlayerEntity(RunePlatformBase, _MediaPlayerEntityBase):
    """One HA media player per RuneDevice (category MEDIA_PLAYER)."""

    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(self, *, device, coordinator) -> None:
        super().__init__(device=device, coordinator=coordinator)
        self._is_on: bool = False
        self._source: str | None = None

    @property
    def name(self) -> str:
        return self._device.name

    @property
    def unique_id(self) -> str:
        return f"rune_{self._device.id}_media_player"

    @property
    def state(self) -> str:
        if not self._is_on:
            return "off"
        return "idle"

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def source(self) -> str | None:
        return self._source

    @property
    def source_list(self) -> list[str]:
        return [
            key.removeprefix("source_")
            for key in self._device.commands
            if key.startswith("source_")
        ]

    @property
    def supported_features(self) -> int:
        try:
            from homeassistant.components.media_player import MediaPlayerEntityFeature
        except ImportError:
            return 0

        features = 0
        if "power_on" in self._device.commands:
            features |= MediaPlayerEntityFeature.TURN_ON
        if "power_off" in self._device.commands:
            features |= MediaPlayerEntityFeature.TURN_OFF
        if "volume_up" in self._device.commands:
            features |= MediaPlayerEntityFeature.VOLUME_UP
        if "volume_down" in self._device.commands:
            features |= MediaPlayerEntityFeature.VOLUME_DOWN
        if "mute" in self._device.commands:
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if "play" in self._device.commands:
            features |= MediaPlayerEntityFeature.PLAY
        if "pause" in self._device.commands:
            features |= MediaPlayerEntityFeature.PAUSE
        if "stop" in self._device.commands:
            features |= MediaPlayerEntityFeature.STOP
        if "next" in self._device.commands:
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if "previous" in self._device.commands:
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        if self.source_list:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        return features

    # ------------------------------------------------------------------
    # Service handlers
    # ------------------------------------------------------------------

    async def async_turn_on(self) -> None:
        if "power_on" in self._device.commands:
            await self.async_send_pulse("power_on")
        self._is_on = True

    async def async_turn_off(self) -> None:
        if "power_off" in self._device.commands:
            await self.async_send_pulse("power_off")
        self._is_on = False

    async def async_volume_up(self) -> None:
        await self.async_send_pulse("volume_up")

    async def async_volume_down(self) -> None:
        await self.async_send_pulse("volume_down")

    async def async_mute_volume(self, mute: bool) -> None:
        if mute and "mute" in self._device.commands:
            await self.async_send_pulse("mute")

    async def async_media_play(self) -> None:
        await self.async_send_pulse("play")

    async def async_media_pause(self) -> None:
        await self.async_send_pulse("pause")

    async def async_media_stop(self) -> None:
        await self.async_send_pulse("stop")

    async def async_media_next_track(self) -> None:
        await self.async_send_pulse("next")

    async def async_media_previous_track(self) -> None:
        await self.async_send_pulse("previous")

    async def async_select_source(self, source: str) -> None:
        key = f"source_{source}"
        if key not in self._device.commands:
            self.warn_unsupported(f"source {source}")
            return
        await self.async_send_pulse(key)
        self._source = source

    def device_info_extra(self) -> dict:
        return {"identifiers": {("rune", self._device.id)}}


class RuneMediaPlayerPlatform:
    PLATFORM = "media_player"

    def __init__(self, hass: Any, coordinator: Any) -> None:
        self._hass = hass
        self._coordinator = coordinator

    async def async_setup_platform(
        self, async_add_entities, discovery_info=None
    ) -> None:
        devices = await self._coordinator._devices.load()  # type: ignore[attr-defined]
        entities = [
            RuneMediaPlayerEntity(device=d, coordinator=self._coordinator)
            for d in devices
            if d.category == EntityCategory.MEDIA_PLAYER
        ]
        async_add_entities(entities)

    def build_entities_for_device(self, device):
        if device.category != EntityCategory.MEDIA_PLAYER:
            return []
        return [RuneMediaPlayerEntity(device=device, coordinator=self._coordinator)]


async def async_setup_entry(hass: Any, entry: Any, async_add_entities: Any) -> None:
    """HA entry-setup hook for the media_player platform."""
    from custom_components.rune._platform_support.setup import setup_rune_platform

    await setup_rune_platform(
        hass=hass,
        entry=entry,
        async_add_entities=async_add_entities,
        platform_name="media_player",
        platform_cls=RuneMediaPlayerPlatform,
    )


__all__ = ["RuneMediaPlayerEntity", "RuneMediaPlayerPlatform", "async_setup_entry"]
