"""Native RF transmitter — uses HA's ``radio_frequency.async_send_command``.

For any entity that implements
:class:`homeassistant.components.radio_frequency.RadioFrequencyTransmitterEntity`
(ESPHome RF, Broadlink RF in 2026.5+, etc.), this adapter converts a
:class:`PulseCommand` into a :class:`RadioFrequencyCommand` and dispatches
via the helper.

We construct the command object directly — no library conversion is
needed because RUNE already stores ``raw_timings`` in the format HA's
helpers expect (signed alternating microseconds, positive mark /
negative space).
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


class NativeRFTransmitter(TransmitterPort):
    """Sends RF via ``radio_frequency.async_send_command``."""

    transport = SignalTransport.RF
    source_kind = TransmitterSourceKind.NATIVE_RADIO_FREQUENCY

    def __init__(self, hass: Any, transmitter_entity_id: str) -> None:
        self._hass = hass
        self._transmitter_entity_id = transmitter_entity_id

    @property
    def transmitter_entity_id(self) -> str:
        return self._transmitter_entity_id

    @property
    def is_available(self) -> bool:
        state = self._hass.states.get(self._transmitter_entity_id)
        return state is not None and state.state != "unavailable"

    async def send(self, command: PulseCommand) -> None:
        prepared = prepare_timings(command)
        if prepared is None:
            raise CommandNotLearnedError(
                f"Command {command.key!r} has no raw timings to send"
            )

        try:
            from rf_protocols import ModulationType, RadioFrequencyCommand
        except ImportError as err:
            raise UnsupportedHardwareError(
                "rf_protocols library is unavailable on this HA version"
            ) from err

        rf_command = RadioFrequencyCommand(
            frequency=prepared.carrier_frequency_hz,
            modulation=ModulationType.OOK,
            timings=prepared.raw_timings,
            repeat_count=prepared.repeat_count,
        )

        try:
            from homeassistant.components import radio_frequency
        except ImportError as err:
            raise UnsupportedHardwareError(
                "homeassistant.components.radio_frequency is unavailable on this HA version"
            ) from err

        try:
            await radio_frequency.async_send_command(
                self._hass,
                self._transmitter_entity_id,
                rf_command,
            )
        except Exception as err:
            _LOGGER.error(
                "rune: native RF send to %s failed: %s",
                self._transmitter_entity_id,
                err,
            )
            raise
