"""Native IR transmitter — uses HA's ``infrared.async_send_command``.

For any entity that implements :class:`homeassistant.components.infrared.InfraredEntity`
(ESPHome IR blasters, Tuya Local blasters, Broadlink in 2026.5+,
SMLIGHT, etc.), this adapter converts a :class:`PulseCommand` into an
``InfraredCommand`` and dispatches via the helper.

The actual command class depends on what's available:

- A captured Pronto hex string → wrapped in a learned-format command.
- Raw timings → wrapped via the infrared_protocols library's raw
  timing class when available.
- Decoded identity (NEC/RC5/Samsung/Sony/Panasonic) → the matching
  ``<Protocol>Command`` class.

We keep things simple: for raw timings we build a generic
``RawTimingCommand`` (or fall back to a Pronto conversion if the raw
class isn't available). Decoded identities are handled by
:mod:`custom_components.rune.domain.encoding` in later phases.
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


class NativeIRTransmitter(TransmitterPort):
    """Sends IR via ``infrared.async_send_command``."""

    transport = SignalTransport.IR
    source_kind = TransmitterSourceKind.NATIVE_INFRARED

    def __init__(self, hass: Any, emitter_entity_id: str) -> None:
        self._hass = hass
        self._emitter_entity_id = emitter_entity_id

    @property
    def emitter_entity_id(self) -> str:
        return self._emitter_entity_id

    @property
    def is_available(self) -> bool:
        state = self._hass.states.get(self._emitter_entity_id)
        return state is not None and state.state != "unavailable"

    async def send(self, command: PulseCommand) -> None:
        prepared = prepare_timings(command)
        if prepared is None:
            raise CommandNotLearnedError(
                f"Command {command.key!r} has no raw timings to send"
            )

        infrared_command = self._build_command(command, prepared)
        if infrared_command is None:
            raise UnsupportedHardwareError(
                f"Cannot encode command {command.key!r} for native IR"
            )

        try:
            from homeassistant.components import infrared
        except ImportError as err:
            raise UnsupportedHardwareError(
                "homeassistant.components.infrared is unavailable on this HA version"
            ) from err

        try:
            await infrared.async_send_command(
                self._hass,
                self._emitter_entity_id,
                infrared_command,
            )
        except Exception as err:
            _LOGGER.error(
                "rune: native IR send to %s failed: %s",
                self._emitter_entity_id,
                err,
            )
            raise

    def _build_command(self, command: PulseCommand, prepared: Any) -> Any:
        """Return an ``InfraredCommand`` for the helper.

        Tries (in order):

        1. The decoded identity (NEC:0xABCD:0xEF) — strongest identity,
           lets the emitter re-encode canonical timings.
        2. A Pronto hex string (decoded_hex or base64_packet).
        3. Raw timings via ``RawTimingCommand``.
        """
        # 1. Decoded identity → protocol-specific command.
        decoded = command.payload.decoded_hex
        if decoded:
            infrared_command = _pronto_to_command(decoded, prepared)
            if infrared_command is not None:
                return infrared_command

        # 2. Base64 packet (Broadlink format) → raw Pronto wrapper.
        if command.payload.base64_packet:
            return _broadlink_base64_to_command(command.payload.base64_packet, prepared)

        # 3. Raw timings.
        return _raw_to_command(prepared.raw_timings, prepared.carrier_frequency_hz)


def _pronto_to_command(pronto_hex: str, prepared: Any) -> Any:
    """Wrap a Pronto hex in a ``RawTimingCommand`` or return None."""
    try:
        from infrared_protocols.commands.pronto import ProntoCommand
    except ImportError:
        return None
    return ProntoCommand(code=pronto_hex, modulation=prepared.carrier_frequency_hz)


def _broadlink_base64_to_command(base64_packet: str, prepared: Any) -> Any:
    """Wrap a Broadlink base64 packet in a raw command.

    Some HA platforms accept ``b64:...`` Pronto hex strings and decode
    them in hardware. We unwrap and rewrap.
    """
    return _pronto_to_command(f"b64:{base64_packet}", prepared)


def _raw_to_command(timings: list[int], carrier_frequency_hz: int) -> Any:
    """Wrap raw timings in the appropriate InfraredCommand subclass."""
    try:
        from infrared_protocols.commands.raw import RawTimingCommand
    except ImportError:
        return None
    return RawTimingCommand(
        timings=timings,
        modulation=carrier_frequency_hz,
    )
