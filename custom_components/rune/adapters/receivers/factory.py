"""Receiver factory — picks the right adapter from an ``entity_id``.

The factory is intentionally simple: a domain → adapter mapping.
Future additions (Tuya IR, SMLIGHT) just extend ``_REGISTRY``.

For RF receivers (Broadlink-only today), the factory takes a
``device_api`` argument because there's no way to discover the
underlying API object from the ``entity_id`` alone.
"""
from __future__ import annotations

from typing import Any

from custom_components.rune.adapters.receivers.broadlink_rf import (
    BroadlinkRFReceiver,
)
from custom_components.rune.adapters.receivers.esphome_legacy_ir import (
    ESPHomeLegacyIRReceiver,
)
from custom_components.rune.adapters.receivers.native_ir import (
    NativeIRReceiver,
)
from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.domain.errors import UnsupportedHardwareError
from custom_components.rune.ports.receiver import ReceiverPort


def select_receiver(
    hass: Any,
    entity_id: str,
    transport: SignalTransport,
    *,
    device_api: Any = None,
) -> ReceiverPort:
    """Return the receiver adapter for ``entity_id``.

    ``device_api`` is required for Broadlink RF receivers (passed
    straight through). For IR receivers it's ignored.

    Raises :class:`UnsupportedHardwareError` when no adapter matches.
    """
    if not entity_id:
        raise UnsupportedHardwareError("Empty entity_id cannot select a receiver")

    domain = entity_id.split(".", 1)[0] if "." in entity_id else ""

    if domain == "infrared" and transport == SignalTransport.IR:
        return NativeIRReceiver(hass, entity_id)
    if domain == "esphome" and transport == SignalTransport.IR:
        return ESPHomeLegacyIRReceiver(hass, entity_id)
    if domain == "remote" and transport == SignalTransport.RF:
        if device_api is None:
            raise UnsupportedHardwareError(
                "Broadlink RF receivers require a pre-resolved device API"
            )
        return BroadlinkRFReceiver(hass, entity_id, device_api)

    raise UnsupportedHardwareError(
        f"No receiver adapter for entity_id={entity_id!r} transport={transport!r}"
    )


__all__ = ["select_receiver"]
