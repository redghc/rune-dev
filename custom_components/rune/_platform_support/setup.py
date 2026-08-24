"""Shared helper that wires each Rune platform module to HA's entry setup.

HA's ``async_forward_entry_setups`` calls ``<platform>.async_setup_entry(hass,
entry, async_add_entities)``. Each Rune platform file (fan, light, climate,
cover, media_player, switch, remote, button) declares a single
``async_setup_entry`` that delegates to this helper. The helper:

- Resolves the coordinator stored on ``hass.data[DOMAIN][entry.entry_id]``.
- Registers the HA-supplied ``async_add_entities`` with the coordinator so
  ``rune/device/create`` can push the new entity without a reload.
- Hands control to the existing ``RuneXxxPlatform.async_setup_platform`` to
  enumerate devices and add the initial entity set.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from custom_components.rune.const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def setup_rune_platform(
    *,
    hass: Any,
    entry: Any,
    async_add_entities: Callable[[list[Any]], None],
    platform_name: str,
    platform_cls: type,
) -> None:
    """Standard module-level ``async_setup_entry`` body for every Rune platform.

    ``platform_name`` — HA's platform key (``"fan"``, ``"light"``, …). Matches
    the entity's domain and is the same string used to register the live
    entity adder on the coordinator.
    ``platform_cls`` — class to instantiate as ``platform_cls(hass, coordinator)``.
    The instance must expose ``async_setup_platform`` (initial enumeration) AND
    ``build_entities_for_device`` (single-device push after create).
    """
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if entry_data is None:
        _LOGGER.error(
            "rune %s: no entry data for %s; skipping platform setup",
            platform_name,
            entry.entry_id,
        )
        return

    coordinator = entry_data.get("coordinator")
    if coordinator is None:
        _LOGGER.error(
            "rune %s: no coordinator registered; skipping platform setup",
            platform_name,
        )
        return

    try:
        platform = platform_cls(hass, coordinator)
    except Exception as err:
        _LOGGER.exception(
            "rune %s: platform factory raised: %s", platform_name, err
        )
        return

    # Register the HA adder + per-device builder so rune/device/create
    # can push new entities without a reload.
    coordinator.register_entity_adder(platform_name, async_add_entities)
    if hasattr(platform, "build_entities_for_device"):
        coordinator.register_entity_builder(
            platform_name, platform.build_entities_for_device
        )

    try:
        await platform.async_setup_platform(async_add_entities)
    except Exception as err:
        # Never let a single platform crash the whole entry setup. Unwind
        # the adder/builder so reloads don't leave a dangling reference.
        coordinator.unregister_entity_adder(platform_name)
        coordinator.unregister_entity_builder(platform_name)
        _LOGGER.exception(
            "rune %s: async_setup_platform failed: %s", platform_name, err
        )
        raise


__all__ = ["setup_rune_platform"]
