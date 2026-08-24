"""Broadlink device registry helpers — resolve ``entity_id`` to a device.

The Broadlink integration stores every discovered device under
``hass.data[BROADLINK_DOMAIN].devices`` keyed by MAC address. We need
to reach the ``BroadlinkDevice`` wrapper (not just the bare API) so
the RF capture adapter can drive ``device.async_request(api.method)``
— the coroutine wrapper that handles the integration's locking and
async dispatch. Calling the synchronous API directly can deadlock
or race with concurrent sends.

This module is the only place that imports Broadlink symbols
(``hass.data[BROADLINK_DOMAIN]``); everything downstream takes the
resolved ``BroadlinkDevice`` and never touches the registry again.
That keeps the dependency surface small and the integration usable
in tests without HA installed.
"""
from __future__ import annotations

from typing import Any

from custom_components.rune.const import BROADLINK_DOMAIN


def find_rf_devices(hass: Any) -> dict[str, Any]:
    """Return ``{entity_id: BroadlinkDevice}`` for every RF-capable unit.

    Only devices whose API exposes ``sweep_frequency`` (RM Pro / RM4
    Pro and other RF-capable Broadlinks) can learn RF — older IR-only
    units are filtered out so the Learn dialog never offers them.
    """
    try:
        data = hass.data.get(BROADLINK_DOMAIN)
    except (AttributeError, KeyError):
        return {}
    if data is None:
        return {}
    devices_obj = getattr(data, "devices", None)
    if not devices_obj:
        return {}

    # The Broadlink integration exposes one ``BroadlinkDevice`` per
    # discovered MAC. Each device owns one or more entities (one
    # ``remote.*`` per appliance). We map every owned entity back to
    # the device so the WS handler can resolve an ``entity_id`` in a
    # single lookup without re-walking the registry.
    out: dict[str, Any] = {}
    for device in devices_obj.values():
        api = getattr(device, "api", None)
        if not hasattr(api, "sweep_frequency"):
            continue
        for entity in getattr(device, "entities", []):
            entity_id = getattr(entity, "entity_id", None)
            if entity_id:
                out[entity_id] = device
        # Also accept the device's own ``entity_id`` attribute as a
        # fallback for older Broadlink integration shapes that don't
        # expose ``entities`` (defensive — the modern shape covers
        # most installs).
        direct = getattr(device, "entity_id", None)
        if direct and direct not in out:
            out[direct] = device
    return out


def find_rf_device_for_entity(hass: Any, entity_id: str) -> Any | None:
    """Single-entity convenience over :func:`find_rf_devices`."""
    if not entity_id:
        return None
    return find_rf_devices(hass).get(entity_id)


__all__ = ["find_rf_devices", "find_rf_device_for_entity"]
