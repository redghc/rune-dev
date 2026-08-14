"""WebSocket API for RUNE — ``rune/*`` commands.

Every command lives under the ``rune/`` prefix (configurable via
``WS_PREFIX`` in :mod:`const`). The MVP exposes:

- ``rune/list`` — list every RuneDevice's summary.
- ``rune/device/get`` — full device detail.
- ``rune/device/create`` — mint a new RuneDevice (stub for MVP).
- ``rune/device/delete`` — remove a device by id.
- ``rune/transmitter/list`` — list emitters known to HA.
- ``rune/receiver/list`` — list receivers known to HA.

Add new commands by appending to ``_HANDLERS`` at the bottom of this
file. Each handler is a coroutine ``(ctx, msg) → payload``. HA imports
are deferred to inside the registration function so this module
imports cleanly in pure-Python environments.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from custom_components.rune.const import WS_PREFIX
from custom_components.rune.domain.errors import (
    ActionError,
    CommandNotLearnedError,
)
from custom_components.rune.domain.models import RuneDevice

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


@dataclass
class RuneWebSocketContext:
    """Per-connection state shared between WS commands."""

    hass: Any
    connection_id: Any  # opaque; resolved by HA when needed

    async def device_repository(self):
        """Return the device repository for this HA instance.

        MVP: re-uses the same store for every connection (single
        integration instance). Phase 7 makes this per-entry.

        Async because :class:`HAStoreDeviceRepository` may need to
        perform lazy initialization on first use; tests stub this
        method with their own coroutine.
        """
        from custom_components.rune.adapters.storage.ha_store import (
            HAStoreDeviceRepository,
        )

        return HAStoreDeviceRepository(self.hass)


# ---------------------------------------------------------------------------
# Command registry
# ---------------------------------------------------------------------------


type _Handler = Callable[["RuneWebSocketContext", dict[str, Any]], Awaitable[dict[str, Any]]]


_HANDLERS: dict[str, _Handler] = {}


def _register(command: str) -> Callable[[_Handler], _Handler]:
    def decorator(func: _Handler) -> _Handler:
        _HANDLERS[command] = func
        return func

    return decorator


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def async_register_websocket_commands(hass: Any) -> None:
    """Register every ``rune/*`` command with HA's WebSocket API."""
    from homeassistant.components import websocket_api

    for command, handler in _HANDLERS.items():
        full = f"{WS_PREFIX}/{command}"

        async def _callback(
            hass: Any,
            connection: Any,
            msg: dict[str, Any],
            _handler: _Handler = handler,
            _command_name: str = command,
        ) -> None:
            ctx = RuneWebSocketContext(hass=hass, connection_id=connection)
            msg_id = msg["id"]
            try:
                payload = await _handler(ctx, msg)
            except Exception as err:
                _LOGGER.exception("rune ws command %s failed", _command_name)
                connection.send_message(
                    websocket_api.error_message(
                        msg_id,
                        f"{type(err).__name__}: {err}",
                    )
                )
                return
            connection.send_message(
                websocket_api.result_message(msg_id, payload)
            )

        websocket_api.async_register_command(hass, full, _callback)


async def async_unregister_websocket_commands(hass: Any) -> None:
    """Drop every ``rune/*`` command (called on full unload)."""
    from homeassistant.components import websocket_api

    for command in _HANDLERS:
        websocket_api.async_unregister_command(hass, f"{WS_PREFIX}/{command}")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


@_register("list")
async def _ws_list(
    ctx: RuneWebSocketContext, _msg: dict[str, Any]
) -> dict[str, Any]:
    """List every RuneDevice as a summary."""
    repo = await ctx.device_repository()
    devices = await repo.load()
    return {
        "devices": [_device_summary(d) for d in devices],
    }


@_register("device/get")
async def _ws_device_get(
    ctx: RuneWebSocketContext, msg: dict[str, Any]
) -> dict[str, Any]:
    """Return the full RuneDevice record for ``device_id``."""
    device_id = msg.get("device_id")
    if not device_id:
        raise ActionError("device_id is required")
    device = await (await ctx.device_repository()).get(device_id)
    if device is None:
        raise CommandNotLearnedError(f"Device {device_id!r} not found")
    return {"device": device.to_dict()}


@_register("device/create")
async def _ws_device_create(
    ctx: RuneWebSocketContext, msg: dict[str, Any]
) -> dict[str, Any]:
    """Create a new RuneDevice from a payload.

    Required fields:

    - ``name`` — display name for the device.
    - ``category`` — one of :class:`EntityCategory`.
    - ``transmitter`` — entity_id of the IR/RF emitter.

    Optional fields:

    - ``manufacturer`` — manufacturer string (default: ``None``).
    - ``model`` — model string (default: ``None``).
    - ``receiver`` — entity_id of an IR/RF receiver (default: ``None``).
    - ``discrete_speed_count`` — for fans (default: ``3``).
    - ``commands`` — dict of pre-learned commands keyed by ``key``.

    Persists the device via the device repository and returns its
    serialized record.
    """
    from uuid import uuid4

    from custom_components.rune.domain.enums import EntityCategory
    from custom_components.rune.domain.models import (
        PulseCommand,
        PulsePayload,
        RuneDevice,
    )

    name = msg.get("name")
    category_value = msg.get("category")
    transmitter = msg.get("transmitter")

    if not name or not category_value or not transmitter:
        raise ActionError("name, category, and transmitter are required")

    try:
        category = EntityCategory(category_value)
    except ValueError as err:
        raise ActionError(f"unknown category: {category_value!r}") from err

    commands: dict[str, Any] = {}
    for key, payload_dict in (msg.get("commands") or {}).items():
        commands[key] = PulseCommand(
            key=key,
            label=payload_dict.get("label", key),
            category=payload_dict.get("category", "custom"),
            signal_category=payload_dict.get("signal_category"),
            payload=PulsePayload.from_dict(payload_dict.get("payload") or {}),
        )

    device = RuneDevice(
        id=str(uuid4()),
        name=name,
        category=category,
        manufacturer=msg.get("manufacturer"),
        model=msg.get("model"),
        transmitter_entity_ids=[transmitter],
        receiver_entity_ids=[msg.get("receiver")] if msg.get("receiver") else [],
        discrete_speed_count=int(msg.get("discrete_speed_count", 3)),
        commands=commands,
    )

    repo = await ctx.device_repository()
    await repo.upsert(device)
    _LOGGER.info("rune: created device %s (%s)", device.id, device.name)

    return {"device": device.to_dict()}


@_register("device/delete")
async def _ws_device_delete(
    ctx: RuneWebSocketContext, msg: dict[str, Any]
) -> dict[str, Any]:
    """Remove a device by id."""
    device_id = msg.get("device_id")
    if not device_id:
        raise ActionError("device_id is required")
    removed = await (await ctx.device_repository()).delete(device_id)
    return {"removed": removed}


@_register("transmitter/list")
async def _ws_transmitter_list(
    ctx: RuneWebSocketContext, _msg: dict[str, Any]
) -> dict[str, Any]:
    """List every HA entity that can act as a transmitter."""
    return {"transmitters": _list_transmitter_entities(ctx.hass)}


@_register("receiver/list")
async def _ws_receiver_list(
    ctx: RuneWebSocketContext, _msg: dict[str, Any]
) -> dict[str, Any]:
    """List every HA entity that can act as a receiver."""
    return {"receivers": _list_receiver_entities(ctx.hass)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _device_summary(device: RuneDevice) -> dict[str, Any]:
    """Compact summary used by ``rune/list``."""
    return {
        "id": device.id,
        "name": device.name,
        "category": device.category.value,
        "transmitter_entity_ids": list(device.transmitter_entity_ids),
        "receiver_entity_ids": list(device.receiver_entity_ids),
        "command_count": len(device.commands),
    }


def _list_transmitter_entities(hass: Any) -> list[dict[str, str]]:
    """Return entity_id + state for every known emitter domain."""
    return _list_entities_for_domains(hass, ("infrared", "remote", "esphome"))


def _list_receiver_entities(hass: Any) -> list[dict[str, str]]:
    """Return entity_id + state for every known receiver domain."""
    return _list_entities_for_domains(hass, ("infrared", "esphome"))


def _list_entities_for_domains(
    hass: Any, domains: tuple[str, ...]
) -> list[dict[str, str]]:
    """Return ``[{entity_id, state}]`` for every state matching the domains."""
    entities: list[dict[str, str]] = []
    for state in hass.states.async_all():
        domain = state.entity_id.split(".", 1)[0] if "." in state.entity_id else ""
        if domain in domains:
            entities.append(
                {
                    "entity_id": state.entity_id,
                    "state": state.state,
                }
            )
    return entities


__all__ = [
    "async_register_websocket_commands",
    "async_unregister_websocket_commands",
]
