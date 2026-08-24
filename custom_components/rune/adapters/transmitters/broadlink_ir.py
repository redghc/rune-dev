"""Broadlink IR transmitter.

Two flavors:

1. **New style** (HA 2026.5+): Broadlink exposes an
   ``InfraredEmitterEntity`` and we can use ``infrared.async_send_command``
   exactly like :class:`NativeIRTransmitter`. This adapter covers that
   path.
2. **Legacy style** (HA ≤ 2026.4): Broadlink only exposes a
   ``remote.send_command`` service that takes ``"b64:<payload>"``
   strings. We pack Pronto timings → Broadlink packed buffer → base64
   and call the service.

The right path is chosen at runtime: if the emitter entity implements
``InfraredEmitterEntity``, use the helper; otherwise fall back to the
service call. This means a user on an older HA still works.
"""
from __future__ import annotations

import logging
from typing import Any

from custom_components.rune.adapters.transmitters.base import prepare_timings
from custom_components.rune.domain.encoding.broadlink import (
    broadlink_to_base64,
    lirc_to_broadlink,
)
from custom_components.rune.domain.encoding.pronto import (
    pronto_hex_to_raw_timings,
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

# HA's Broadlink integration domain — used to look up the underlying
# device instance from ``hass.data``.
BROADLINK_DOMAIN = "broadlink"


class BroadlinkIRTransmitter(TransmitterPort):
    """Sends IR via a Broadlink device.

    The ``entity_id`` is the ``remote.*`` (legacy) or ``infrared.*``
    (2026.5+) entity. The adapter discovers the underlying API object
    via ``hass.data[DOMAIN].devices[mac]`` for legacy calls.
    """

    transport = SignalTransport.IR
    source_kind = TransmitterSourceKind.NATIVE_INFRARED

    def __init__(self, hass: Any, entity_id: str, *, device_api: Any = None) -> None:
        self._hass = hass
        self._entity_id = entity_id
        # Optional pre-resolved device API (Broadlink python-broadlink
        # object). Production code resolves it from hass.data; tests
        # can inject a mock.
        self._device_api = device_api

    @property
    def is_available(self) -> bool:
        state = self._hass.states.get(self._entity_id)
        return state is not None and state.state != "unavailable"

    async def send(self, command: PulseCommand) -> None:
        base64_payload = self._encode_to_base64(command)
        if base64_payload is None:
            raise CommandNotLearnedError(
                f"Command {command.key!r} has no payload Broadlink can send"
            )

        # Path 1: native infrared (HA 2026.5+ Broadlink entity).
        if self._emitter_supports_native_ir():
            await self._send_via_native_ir(base64_payload, command)
            return

        # Path 2: legacy remote.send_command service.
        await self._send_via_remote_service(base64_payload)

    # ------------------------------------------------------------------
    # Encoding
    # ------------------------------------------------------------------

    def _encode_to_base64(self, command: PulseCommand) -> str | None:
        """Return a ``b64:...`` string Broadlink can replay.

        Three sources, in priority order:

        1. Pre-encoded ``base64_packet`` (captured via the Broadlink
           receiver).
        2. Pronto hex (``decoded_hex`` or raw timings → Pronto).
        3. Raw timings via the LIRC ticks path.

        Returns ``None`` when no payload exists.
        """
        if command.payload.base64_packet:
            return f"b64:{command.payload.base64_packet}"

        prepared = prepare_timings(command)
        if prepared is None:
            if command.payload.decoded_hex:
                # Already Pronto; convert to base64 Broadlink pack.
                timings = pronto_hex_to_raw_timings(command.payload.decoded_hex)
                return f"b64:{broadlink_to_base64(bytes(lirc_to_broadlink(timings)))}"
            return None

        # Raw timings → Pronto → Broadlink pack → base64.
        pronto = raw_timings_to_pronto_hex(prepared.raw_timings)
        timings = pronto_hex_to_raw_timings(pronto)
        return f"b64:{broadlink_to_base64(bytes(lirc_to_broadlink(timings)))}"

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def _emitter_supports_native_ir(self) -> bool:
        """True if the entity implements HA's ``InfraredEmitterEntity``."""
        try:
            from homeassistant.components.infrared import InfraredEmitterEntity
        except ImportError:
            return False
        registry = getattr(self._hass, "entity_registry", None)
        if registry is None:
            return False
        entry = registry.async_get(self._entity_id)
        if entry is None:
            return False
        # The actual entity object lives in the state machine; pull it
        # via the platform. The cheap path is to consult the
        # platform's ``entities`` dict.
        platform = getattr(self._hass, "data", {}).get("entity_components", {})
        for component in platform.values():
            entity = component.entities.get(self._entity_id)
            if isinstance(entity, InfraredEmitterEntity):
                return True
        return False

    async def _send_via_native_ir(self, base64_payload: str, command: PulseCommand) -> None:
        try:
            from homeassistant.components import infrared
            from infrared_protocols.commands.pronto import ProntoCommand
        except ImportError as err:
            # ``infrared_protocols`` is the encoding lib used to wrap the
            # base64 packet as an ``InfraredCommand``; if it's not
            # importable, neither is ``ProntoCommand``. Tell the user
            # exactly what's missing instead of blaming the HA helper
            # (which is unrelated).
            raise UnsupportedHardwareError(
                "Broadlink native-IR send needs the `infrared_protocols` "
                "Python library, which is not importable on this Home "
                "Assistant host. Reinstall the `homeassistant` package "
                "(or `pip install infrared_protocols`) and retry."
            ) from err

        # Convert b64 payload back into a Pronto hex by stripping the
        # prefix — HA's helper takes a ProntoCommand with the raw hex.
        pronto_hex = base64_payload.removeprefix("b64:")
        pronto_command = ProntoCommand(
            code=pronto_hex,
            modulation=command.signal_category.carrier_frequency_hz or 38_000,
        )
        await infrared.async_send_command(self._hass, self._entity_id, pronto_command)

    async def _send_via_legacy_remote_service(self, base64_payload: str) -> None:
        """Send via ``remote.send_command`` — Broadlink's legacy path.

        Kept for compatibility with HA versions where Broadlink does
        not yet implement the native ``InfraredEmitterEntity``.
        """
        await self._hass.services.async_call(
            "remote",
            "send_command",
            {
                "entity_id": self._entity_id,
                "command": base64_payload,
            },
            blocking=True,
        )

    async def _send_via_remote_service(self, base64_payload: str) -> None:
        """Alias for the legacy path — kept for naming symmetry with native_ir."""
        await self._send_via_legacy_remote_service(base64_payload)
