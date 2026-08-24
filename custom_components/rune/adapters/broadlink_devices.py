"""Broadlink device registry helpers — resolve ``entity_id`` to a device.

The Broadlink integration stores every discovered device under
``hass.data[BROADLINK_DOMAIN].devices`` keyed by config entry ID.
We need to reach the ``BroadlinkDevice`` wrapper (not just the bare
API) so the RF capture adapter can drive ``device.async_request(api.method)``
— the coroutine wrapper that handles the integration's locking and
async dispatch. Calling the synchronous API directly can deadlock
or race with concurrent sends.

Resolving ``entity_id`` → ``BroadlinkDevice`` is non-obvious: the
Broadlink integration manages entities via the HA ``infrared`` /
``radio_frequency`` / ``remote`` platforms, not via an
``entities`` list on the device wrapper. We bridge that gap by
walking HA's ``entity_registry`` — every Broadlink-owned entity
has its ``config_entry_id`` pointing at the Broadlink config entry,
which is the same key we use in ``hass.data[BROADLINK_DOMAIN].devices``.

This module is the only place that imports Broadlink symbols
(``hass.data[BROADLINK_DOMAIN]``); everything downstream takes the
resolved ``BroadlinkDevice`` and never touches the registry again.
That keeps the dependency surface small and the integration usable
in tests without HA installed.
"""
from __future__ import annotations

from typing import Any

from custom_components.rune.const import BROADLINK_DOMAIN

# Domains whose entities may belong to a Broadlink. ``infrared.*``
# covers the IR blaster + receiver entities the modern integration
# creates; ``radio_frequency.*`` is the 2026+ RF platform; the older
# ``remote.*`` covers pre-2026 setups.
_BROADLINK_DOMAIN_PREFIXES: tuple[str, ...] = (
    "infrared.",
    "radio_frequency.",
    "remote.",
)


def find_rf_devices(hass: Any) -> dict[str, Any]:
    """Return ``{entity_id: BroadlinkDevice}`` for every entity that
    belongs to an RF-capable Broadlink.

    Walks HA's entity registry to find entities whose
    ``config_entry_id`` matches a Broadlink entry (the same key used
    in ``hass.data[BROADLINK_DOMAIN].devices``). Filters by the
    ``sweep_frequency`` API method so IR-only Broadlinks are excluded.

    The entity → Broadlink mapping lets the WS handler resolve any
    IR/RF entity belonging to a Broadlink — modern Broadlink
    integrations register their IR emitter under ``infrared.*`` and
    their RF transmitter under ``radio_frequency.*``, so the
    capture flow has to be domain-agnostic.
    """
    return _find_broadlink_devices(hass, "sweep_frequency")


def find_ir_learn_devices(hass: Any) -> dict[str, Any]:
    """Return ``{entity_id: BroadlinkDevice}`` for every entity that
    belongs to a Broadlink capable of learning IR.

    Filters on the ``enter_learning`` API method — the classic
    Broadlink IR learn entry point. This includes IR-only units
    (RM Mini) as well as the RF-capable RM Pro / RM4 Pro. The HA
    Broadlink integration never exposes the hardware's IR receiver
    as an ``InfraredReceiverEntity``, so learning IR on a Broadlink
    ALWAYS goes through this SDK path.
    """
    return _find_broadlink_devices(hass, "enter_learning")


def _find_broadlink_devices(hass: Any, required_api_method: str) -> dict[str, Any]:
    """Shared entity_registry walk behind both public lookups."""
    devices_data = hass.data.get(BROADLINK_DOMAIN)
    if devices_data is None:
        return {}
    devices_obj = getattr(devices_data, "devices", None)
    if not devices_obj:
        return {}

    broadlink_entry_ids = set(devices_obj.keys())

    try:
        from homeassistant.helpers import entity_registry as er
    except ImportError:
        # No HA installed — fall back to the ``device.entities`` walk
        # used by older Broadlink integration shapes. Keeps the
        # function usable from pure-Python tests.
        return _find_via_device_entities(devices_obj, required_api_method)

    entity_registry = er.async_get(hass)
    out: dict[str, Any] = {}
    for entity_id, entry in entity_registry.entities.items():
        if not entity_id.startswith(_BROADLINK_DOMAIN_PREFIXES):
            continue
        config_entry_id = getattr(entry, "config_entry_id", None)
        if config_entry_id not in broadlink_entry_ids:
            continue
        device = devices_obj.get(config_entry_id)
        if device is None:
            continue
        api = getattr(device, "api", None)
        if not hasattr(api, required_api_method):
            continue
        out[entity_id] = device
    return out


def _find_via_device_entities(
    devices_obj: Any, required_api_method: str
) -> dict[str, Any]:
    """Fallback for environments without HA installed (tests).

    Walks ``device.entities`` if it exists — older Broadlink integration
    shapes populated this attribute. Modern shapes don't, which is
    exactly the gap the entity-registry walk closes in production.
    """
    out: dict[str, Any] = {}
    for device in devices_obj.values():
        api = getattr(device, "api", None)
        if not hasattr(api, required_api_method):
            continue
        for entity in getattr(device, "entities", []):
            entity_id = getattr(entity, "entity_id", None)
            if entity_id:
                out[entity_id] = device
        direct = getattr(device, "entity_id", None)
        if direct and direct not in out:
            out[direct] = device
    return out


def find_rf_device_for_entity(hass: Any, entity_id: str) -> Any | None:
    """Single-entity convenience over :func:`find_rf_devices`."""
    if not entity_id:
        return None
    return find_rf_devices(hass).get(entity_id)


def find_ir_learn_device_for_entity(hass: Any, entity_id: str) -> Any | None:
    """Single-entity convenience over :func:`find_ir_learn_devices`."""
    if not entity_id:
        return None
    return find_ir_learn_devices(hass).get(entity_id)


__all__ = [
    "find_rf_devices",
    "find_rf_device_for_entity",
    "find_ir_learn_devices",
    "find_ir_learn_device_for_entity",
]
