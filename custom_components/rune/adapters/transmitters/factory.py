"""Transmitter factory — picks the right adapter from an ``entity_id``.

The factory is intentionally dumb: it inspects the entity_id domain
(``infrared.``, ``radio_frequency.``, ``remote.``, ``esphome.``) and
returns the matching adapter. The factory does NOT inspect the
device's capabilities (e.g. whether Broadlink is exposing the native
InfraredEmitterEntity vs. only the legacy service) — that's a runtime
decision the adapter makes on each ``send()`` call.

Adding a new hardware family: subclass or instantiate
:class:`~custom_components.rune.ports.transmitter.TransmitterPort`
and add a branch in :func:`select_transmitter` below.
"""
from __future__ import annotations

from typing import Any

from custom_components.rune.adapters.transmitters.broadlink_ir import (
    BroadlinkIRTransmitter,
)
from custom_components.rune.adapters.transmitters.broadlink_rf import (
    BroadlinkRFTransmitter,
)
from custom_components.rune.adapters.transmitters.esphome_ir import (
    ESPHomeIRTransmitter,
)
from custom_components.rune.adapters.transmitters.esphome_rf import (
    ESPHomeRFTransmitter,
)
from custom_components.rune.adapters.transmitters.native_ir import (
    NativeIRTransmitter,
)
from custom_components.rune.adapters.transmitters.native_rf import (
    NativeRFTransmitter,
)
from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.domain.errors import UnsupportedHardwareError
from custom_components.rune.ports.transmitter import TransmitterPort


def _domain(entity_id: str) -> str:
    """Return the entity domain (``infrared``, ``remote``, etc.) of ``entity_id``."""
    return entity_id.split(".", 1)[0] if "." in entity_id else ""


def select_transmitter(
    hass: Any,
    entity_id: str,
    transport: SignalTransport,
) -> TransmitterPort:
    """Return the adapter matching ``entity_id`` and ``transport``.

    The transport argument disambiguates the cases where the same
    entity domain can carry either IR or RF (e.g. ``remote.`` for
    Broadlink IR; ``esphome.`` for either). Raises
    :class:`UnsupportedHardwareError` when no adapter matches.
    """
    if not entity_id:
        raise UnsupportedHardwareError("Empty entity_id cannot select a transmitter")

    domain = _domain(entity_id)

    if domain == "infrared" and transport == SignalTransport.IR:
        return NativeIRTransmitter(hass, entity_id)
    if domain == "radio_frequency" and transport == SignalTransport.RF:
        return NativeRFTransmitter(hass, entity_id)
    if domain == "remote" and transport == SignalTransport.IR:
        return BroadlinkIRTransmitter(hass, entity_id)
    if domain == "remote" and transport == SignalTransport.RF:
        return BroadlinkRFTransmitter(hass, entity_id)
    if domain == "esphome" and transport == SignalTransport.IR:
        return ESPHomeIRTransmitter(hass, entity_id)
    if domain == "esphome" and transport == SignalTransport.RF:
        return ESPHomeRFTransmitter(hass, entity_id)

    raise UnsupportedHardwareError(
        f"No transmitter adapter for entity_id={entity_id!r} transport={transport!r}"
    )


__all__ = [
    "BroadlinkIRTransmitter",
    "BroadlinkRFTransmitter",
    "ESPHomeIRTransmitter",
    "ESPHomeRFTransmitter",
    "NativeIRTransmitter",
    "NativeRFTransmitter",
    "select_transmitter",
]
