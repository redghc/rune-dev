"""ESPHome RF transmitter.

ESPHome RF blasters have a YAML configuration like:

    remote_receiver:
      pin:
        number: GPIO5
      tolerance: 25%

And a corresponding transmitter. HA exposes them as
``RadioFrequencyTransmitterEntity`` (since 2026.4 for ESPHome RF).
This adapter is the path for the *older* ESPHome integration that
used the ``esphome.<entity_id>_rf_transmit`` service with raw
timings.
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


class ESPHomeRFTransmitter(TransmitterPort):
    """Sends RF via the ESPHome legacy service or the native helper."""

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
            from rf_protocols import ModulationType, RadioFrequencyCommand
        except ImportError as err:
            raise UnsupportedHardwareError(
                "Native RF stack unavailable on this HA version"
            ) from err

        rf_command = RadioFrequencyCommand(
            frequency=prepared.carrier_frequency_hz,
            modulation=ModulationType.OOK,
            timings=prepared.raw_timings,
            repeat_count=prepared.repeat_count,
        )
        await radio_frequency.async_send_command(self._hass, self._entity_id, rf_command)

    async def _send_via_legacy_service(self, prepared: Any) -> None:
        """ESPHome legacy service: ``esphome.<entity_id>_rf_transmit``."""
        domain = "esphome"
        service = f"{self._entity_id.replace('.', '_')}_rf_transmit"
        await self._hass.services.async_call(
            domain,
            service,
            {
                "frequency": prepared.carrier_frequency_hz,
                "timings": prepared.raw_timings,
                "repeat": prepared.repeat_count,
            },
            blocking=True,
        )
