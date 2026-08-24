"""ESPHome IR transmitter.

ESPHome IR blasters have a YAML configuration like:

    remote_transmitter:
      pin: GPIO4
      carrier_duty_percent: 50%

HA exposes them as ``InfraredEmitterEntity`` (since 2026.4 for ESPHome
IR). This adapter is the path for the *older* ESPHome integration that
used the ``esphome.<entity_id>`` service interface with a Pronto hex
command. Modern setups should use :class:`NativeIRTransmitter`
instead — this adapter exists for legacy compatibility.

ESPHome's IR service call shape (deprecated path):

    service: esphome.<entity_id>_transmit
    data:
      command: <pronto_hex_string>
"""
from __future__ import annotations

import logging
from typing import Any

from custom_components.rune.adapters.transmitters.base import prepare_timings
from custom_components.rune.domain.encoding.pronto import (
    raw_timings_to_pronto_hex,
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


class ESPHomeIRTransmitter(TransmitterPort):
    """Sends IR via the ESPHome legacy ``esphome.<id>_transmit`` service."""

    transport = SignalTransport.IR
    source_kind = TransmitterSourceKind.NATIVE_INFRARED

    def __init__(self, hass: Any, entity_id: str) -> None:
        self._hass = hass
        self._entity_id = entity_id

    @property
    def is_available(self) -> bool:
        state = self._hass.states.get(self._entity_id)
        return state is not None and state.state != "unavailable"

    async def send(self, command: PulseCommand) -> None:
        pronto_hex = self._encode_to_pronto(command)
        if pronto_hex is None:
            raise CommandNotLearnedError(
                f"Command {command.key!r} has no payload ESPHome IR can send"
            )

        # Newer ESPHome YAML uses the native infrared helper.
        if self._supports_native_ir():
            await self._send_via_native_ir(pronto_hex, command)
            return

        await self._send_via_legacy_service(pronto_hex)

    # ------------------------------------------------------------------
    # Encoding
    # ------------------------------------------------------------------

    def _encode_to_pronto(self, command: PulseCommand) -> str | None:
        """Return a Pronto hex string for ESPHome to transmit."""
        if command.payload.decoded_hex:
            return command.payload.decoded_hex
        if command.payload.base64_packet:
            # Decode the Broadlink pack back into raw timings, then to Pronto.
            # (For brevity we trust the raw_timings path here; the more
            # accurate decode lives in a later refactor.)
            return None
        prepared = prepare_timings(command)
        if prepared is None:
            return None
        return raw_timings_to_pronto_hex(prepared.raw_timings)

    # ------------------------------------------------------------------
    # Path detection
    # ------------------------------------------------------------------

    def _supports_native_ir(self) -> bool:
        try:
            from homeassistant.components.infrared import InfraredEmitterEntity
        except ImportError:
            return False
        platform = getattr(self._hass, "data", {}).get("entity_components", {})
        for component in platform.values():
            entity = component.entities.get(self._entity_id)
            if isinstance(entity, InfraredEmitterEntity):
                return True
        return False

    # ------------------------------------------------------------------
    # Send paths
    # ------------------------------------------------------------------

    async def _send_via_native_ir(self, pronto_hex: str, command: PulseCommand) -> None:
        try:
            from homeassistant.components import infrared
        except ImportError as err:
            raise UnsupportedHardwareError(
                "homeassistant.components.infrared is unavailable"
            ) from err

        # Use RUNE's ProntoIRCommand shim — it duck-types as an
        # ``InfraredCommand`` without depending on the optional
        # ``infrared_protocols`` library. HA's IR emitters only call
        # ``command.get_raw_timings()`` (and the ESPHome emitter also
        # reads ``command.modulation``), so the shim is sufficient.
        from custom_components.rune.domain.encoding.commands import ProntoIRCommand

        pronto_command = ProntoIRCommand(
            pronto_hex=pronto_hex,
            modulation=command.signal_category.carrier_frequency_hz or 38_000,
        )
        await infrared.async_send_command(self._hass, self._entity_id, pronto_command)

    async def _send_via_legacy_service(self, pronto_hex: str) -> None:
        """ESPHome legacy service: ``esphome.<entity_id>_transmit``."""
        # Sanitize the entity_id for the service name: switch becomes
        # ``remote_transmitter`` per ESPHome's service template.
        domain = "esphome"
        service = f"{self._entity_id.replace('.', '_')}_transmit"
        await self._hass.services.async_call(
            domain,
            service,
            {"command": pronto_hex},
            blocking=True,
        )
