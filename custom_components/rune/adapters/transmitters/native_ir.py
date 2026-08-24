"""Native IR transmitter — uses HA's ``infrared.async_send_command``.

For any entity that implements :class:`homeassistant.components.infrared.InfraredEntity`
(ESPHome IR blasters, Tuya Local blasters, Broadlink in 2026.5+,
SMLIGHT, etc.), this adapter converts a :class:`PulseCommand` into an
``InfraredCommand`` and dispatches via the helper.

The actual command class depends on what's available:

- A captured Pronto hex string → wrapped in :class:`ProntoIRCommand`.
- Raw timings → wrapped in :class:`RawTimingIRCommand`.

Both shims live in :mod:`custom_components.rune.domain.encoding.commands`
and intentionally do NOT depend on the optional ``infrared_protocols``
library. HA's IR emitters only call ``command.get_raw_timings()`` (and
the ESPHome emitter additionally reads ``command.modulation``), so a
duck-typed object with those two attributes works regardless of whether
the third-party library is installed on the host.
"""
from __future__ import annotations

import logging
from typing import Any

from custom_components.rune.adapters.transmitters.base import prepare_timings
from custom_components.rune.domain.encoding.commands import (
    ProntoIRCommand,
    RawTimingIRCommand,
)
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
            # Reachable only if every encoder path failed — shouldn't
            # happen in practice (we no longer depend on the optional
            # ``infrared_protocols`` library), but keep the guard so a
            # regression still surfaces a useful hint instead of a
            # bare ``None`` crash deep in the helper.
            raise UnsupportedHardwareError(
                f"Cannot encode command {command.key!r} for native IR — "
                "no encoder path produced a usable command object."
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
        3. Raw timings via :class:`RawTimingIRCommand`.

        All three branches use :mod:`custom_components.rune.domain.encoding.commands`
        shims — no third-party ``infrared_protocols`` import required.
        """
        # 1. Decoded identity → Pronto wrapper.
        decoded = command.payload.decoded_hex
        if decoded:
            return ProntoIRCommand(
                pronto_hex=decoded,
                modulation=prepared.carrier_frequency_hz,
            )

        # 2. Base64 packet (Broadlink format) → Pronto wrapper.
        # ``b64:...`` Pronto hex is what Broadlink's native-IR entity
        # consumes; emitters decode it back to raw timings on the fly.
        if command.payload.base64_packet:
            return ProntoIRCommand(
                pronto_hex=f"b64:{command.payload.base64_packet}",
                modulation=prepared.carrier_frequency_hz,
            )

        # 3. Raw timings.
        return RawTimingIRCommand(
            timings=prepared.raw_timings,
            modulation=prepared.carrier_frequency_hz,
            repeat_count=prepared.repeat_count,
        )
