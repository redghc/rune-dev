"""Broadlink RF transmitter.

Two paths:

1. **New style** (HA 2026.5+): Broadlink exposes a
   ``RadioFrequencyTransmitterEntity`` and we use
   ``radio_frequency.async_send_command``.
2. **Legacy style** (HA ≤ 2026.4): Broadlink's own
   ``broadlink.send_packet`` service handles raw timings.

The right path is selected at runtime. On either path the command
carries the raw timings directly — Broadlink RF does not use Pronto.

We deliberately skip ``super().__init__`` on the
``CapturedCommand`` subclass so the adapter is immune to constructor
changes across ``rf_protocols`` releases (rf_fan's lesson learned).
"""
from __future__ import annotations

import logging
from typing import Any

from custom_components.rune.adapters.transmitters.base import prepare_timings
from custom_components.rune.domain.enums import (
    SignalTransport,
    TransmitterSourceKind,
)
from custom_components.rune.domain.errors import (
    CommandNotLearnedError,
    UnsupportedHardwareError,
)
from custom_components.rune.domain.models import PulseCommand
from custom_components.rune.ports.transmitter import TransmitterPort

_LOGGER = logging.getLogger(__name__)


class BroadlinkRFTransmitter(TransmitterPort):
    """Sends RF via a Broadlink device."""

    transport = SignalTransport.RF
    source_kind = TransmitterSourceKind.NATIVE_RADIO_FREQUENCY

    def __init__(self, hass: Any, entity_id: str) -> None:
        self._hass = hass
        self._entity_id = entity_id

    @property
    def is_available(self) -> bool:
        state = self._hass.states.get(self._entity_id)
        return state is not None and state.state != "unavailable"

    async def send(self, command: PulseCommand) -> None:
        prepared = prepare_timings(command)
        if prepared is None:
            raise CommandNotLearnedError(
                f"Command {command.key!r} has no raw timings to send"
            )

        if self._supports_native_rf():
            await self._send_via_native_rf(prepared)
            return

        await self._send_via_legacy_service(prepared)

    # ------------------------------------------------------------------
    # Path detection
    # ------------------------------------------------------------------

    def _supports_native_rf(self) -> bool:
        try:
            from homeassistant.components.radio_frequency import (
                RadioFrequencyTransmitterEntity,
            )
        except ImportError:
            return False
        platform = getattr(self._hass, "data", {}).get("entity_components", {})
        for component in platform.values():
            entity = component.entities.get(self._entity_id)
            if isinstance(entity, RadioFrequencyTransmitterEntity):
                return True
        return False

    # ------------------------------------------------------------------
    # Send paths
    # ------------------------------------------------------------------

    async def _send_via_native_rf(self, prepared: Any) -> None:
        try:
            from homeassistant.components import radio_frequency
        except ImportError as err:
            raise UnsupportedHardwareError(
                "Native RF stack unavailable on this HA version"
            ) from err

        # Use RUNE's RawTimingRFCommand shim — duck-typed
        # ``RadioFrequencyCommand`` that does NOT depend on the optional
        # ``rf_protocols`` library. HA's RF emitters (ESPHome, Broadlink)
        # only consume ``frequency`` / ``modulation`` / ``repeat_count``
        # / ``get_raw_timings()``, which the shim provides.
        from custom_components.rune.domain.encoding.commands import RawTimingRFCommand

        rf_command = RawTimingRFCommand(
            frequency=prepared.carrier_frequency_hz,
            timings=prepared.raw_timings,
            repeat_count=prepared.repeat_count,
        )
        await radio_frequency.async_send_command(self._hass, self._entity_id, rf_command)

    async def _send_via_legacy_service(self, prepared: Any) -> None:
        """Send via Broadlink's own ``broadlink.send_packet`` service.

        The Broadlink integration registers ``send_packet`` with the
        same raw-timings contract HA's native helper uses.
        """
        # Broadlink registers the service under its own domain — we
        # don't import the broadlink package directly (HA may not have
        # the dependency); the service is the public API.
        await self._hass.services.async_call(
            "broadlink",
            "send_packet",
            {
                "entity_id": self._entity_id,
                "frequency": prepared.carrier_frequency_hz,
                "timings": prepared.raw_timings,
                "repeat": prepared.repeat_count,
            },
            blocking=True,
        )
