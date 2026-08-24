"""Receiver factory — picks the right adapter from an ``entity_id``.

The factory is intentionally simple: a domain → adapter mapping.
Future additions (Tuya IR, SMLIGHT) just extend ``_REGISTRY``.

For RF receivers (Broadlink-only today), the factory takes a
``device`` argument — the full ``BroadlinkDevice`` wrapper, not just
the API object. The wrapper owns the ``async_request`` coroutine we
need for safe concurrent access. Pass ``None`` to defer device
resolution to the caller (the WS handler does this when the
broadlink integration isn't loaded yet).
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
    transport: SignalTransport | None,
    *,
    device: Any = None,
) -> ReceiverPort:
    """Return the receiver adapter for ``entity_id``.

    ``device`` is required for Broadlink RF receivers (passed straight
    through to :class:`BroadlinkRFReceiver`). For IR receivers it's
    ignored.

    ``transport`` is optional for the IR / RF auto-detection that the
    sniffer engine uses (``esphome.*`` and ``infrared.*`` are IR;
    ``remote.*`` is RF). Pass ``None`` to let the factory infer from
    the entity's domain.

    Raises :class:`UnsupportedHardwareError` when no adapter matches.
    """
    if not entity_id:
        raise UnsupportedHardwareError("Empty entity_id cannot select a receiver")

    domain = entity_id.split(".", 1)[0] if "." in entity_id else ""

    inferred = _infer_transport(domain)
    if transport is None:
        transport = inferred

    if domain == "infrared" and transport is SignalTransport.IR:
        return NativeIRReceiver(hass, entity_id)
    if domain == "esphome" and transport is SignalTransport.IR:
        return ESPHomeLegacyIRReceiver(hass, entity_id)
    if domain == "remote" and transport is SignalTransport.RF:
        if device is None:
            raise UnsupportedHardwareError(
                "Broadlink RF receivers require a pre-resolved BroadlinkDevice"
            )
        return BroadlinkRFReceiver(hass, entity_id, device)

    raise UnsupportedHardwareError(
        f"No receiver adapter for entity_id={entity_id!r} transport={transport!r}"
    )


def _infer_transport(domain: str) -> SignalTransport | None:
    """Best-effort transport guess from the entity domain.

    IR is the default for ``infrared.*`` and ``esphome.*``; RF for
    ``remote.*``. Unknown domains return ``None`` so the caller
    surfaces a real error.
    """
    if domain in {"infrared", "esphome"}:
        return SignalTransport.IR
    if domain == "remote":
        return SignalTransport.RF
    return None


__all__ = ["select_receiver"]
