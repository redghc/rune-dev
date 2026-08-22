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

from custom_components.rune.const import DOMAIN, WS_PREFIX
from custom_components.rune.domain.errors import (
    ActionError,
    CaptureError,
    CaptureProviderUnavailableError,
    CaptureTimeoutError,
    CommandNotLearnedError,
    UnsupportedHardwareError,
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

        @websocket_api.async_response
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

        # HA's WS dispatcher calls ``handler(hass, connection, schema(msg))``.
        # The 3-arg form of ``async_register_command`` ignores any schema we
        # pass and stores ``None``; the dispatcher then evaluates ``None(msg)``
        # -> TypeError, which its top-level catch flattens to the generic
        # "Unknown error" response -- masking the real exception. Mark the
        # callback as schema-less so the dispatcher passes ``msg`` through
        # untouched (the bridge always sends exactly ``{id, type}``).
        _callback._ws_command = full  # type: ignore[attr-defined]
        _callback._ws_schema = False  # type: ignore[attr-defined]
        websocket_api.async_register_command(hass, _callback)


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


@_register("device/update")
async def _ws_device_update(
    ctx: RuneWebSocketContext, msg: dict[str, Any]
) -> dict[str, Any]:
    """Update an existing RuneDevice.

    Fields the SPA sends as kwargs (any subset):

    - ``device_id`` (required)
    - ``name``, ``manufacturer``, ``model``
    - ``transmitter_entity_ids`` (list, replaces existing)
    - ``receiver_entity_ids`` (list, replaces existing)
    - ``discrete_speed_count`` (int)
    - ``power_sensor_entity_id``, ``power_off_below_w``, ``power_on_above_w``
    """
    from custom_components.rune.domain.models import RuneDevice

    device_id = msg.get("device_id")
    if not device_id:
        raise ActionError("device_id is required")

    repo = await ctx.device_repository()
    device = await repo.get(device_id)
    if device is None:
        raise CommandNotLearnedError(f"Device {device_id!r} not found")

    updated = RuneDevice(
        id=device.id,
        name=msg.get("name", device.name),
        category=device.category,
        manufacturer=msg.get("manufacturer", device.manufacturer),
        model=msg.get("model", device.model),
        transmitter_entity_ids=msg.get(
            "transmitter_entity_ids", device.transmitter_entity_ids
        ),
        receiver_entity_ids=msg.get(
            "receiver_entity_ids", device.receiver_entity_ids
        ),
        speed_mode=device.speed_mode,
        discrete_speed_count=int(
            msg.get("discrete_speed_count", device.discrete_speed_count)
        ),
        power_sensor_entity_id=msg.get(
            "power_sensor_entity_id", device.power_sensor_entity_id
        ),
        power_off_below_w=msg.get("power_off_below_w", device.power_off_below_w),
        power_on_above_w=msg.get("power_on_above_w", device.power_on_above_w),
        temperature_sensor_entity_id=device.temperature_sensor_entity_id,
        humidity_sensor_entity_id=device.humidity_sensor_entity_id,
        climate_matrix=device.climate_matrix,
        commands=device.commands,
        actions=device.actions,
        version=device.version,
        created_at=device.created_at,
        updated_at=device.updated_at,
    )
    await repo.upsert(updated)
    return {"device": updated.to_dict()}


@_register("command/learn")
async def _ws_command_learn(
    ctx: RuneWebSocketContext, msg: dict[str, Any]
) -> dict[str, Any]:
    """Start a learn session for a (device_id, command_key) pair.

    Blocks until the capture completes or times out. Returns the
    raw timings captured so the SPA can show them and the caller can
    persist the new PulseCommand via ``rune/device/update``.

    Required fields:

    - ``device_id`` — id of the device.
    - ``command_key`` — which command to fill in.
    - ``timeout_s`` — optional, default 15.
    """

    device_id = msg.get("device_id")
    command_key = msg.get("command_key")
    if not device_id or not command_key:
        raise ActionError("device_id and command_key are required")

    orchestrator = ctx.hass.data.get(DOMAIN, {}).get(
        next(iter(ctx.hass.data.get(DOMAIN, {})), {}), {}
    ).get("capture_orchestrator")
    if orchestrator is None:
        # Fall back: look across all entries
        for entry_data in ctx.hass.data.get(DOMAIN, {}).values():
            if isinstance(entry_data, dict) and "capture_orchestrator" in entry_data:
                orchestrator = entry_data["capture_orchestrator"]
                break

    if orchestrator is None:
        raise UnsupportedHardwareError(
            "No capture orchestrator registered; restart HA"
        )

    device = await (await ctx.device_repository()).get(device_id)
    if device is None:
        raise CommandNotLearnedError(f"Device {device_id!r} not found")

    # Pick the first RF receiver attached to the device, else any
    # known receiver from HA. Phase 7 will pick based on signal
    # transport category.
    from custom_components.rune.adapters.capture.providers import NativeIRCaptureProvider

    receiver_entity_id = (
        device.receiver_entity_ids[0]
        if device.receiver_entity_ids
        else _list_receiver_entities(ctx.hass)[0]["entity_id"]
        if _list_receiver_entities(ctx.hass)
        else None
    )
    if not receiver_entity_id:
        raise CaptureProviderUnavailableError(
            "No IR/RF receiver configured for this device"
        )

    provider = NativeIRCaptureProvider(ctx.hass, receiver_entity_id)

    timeout_s = float(msg.get("timeout_s", 15.0))
    try:
        await orchestrator.start_capture(
            provider,
            session_id=f"{device_id}.{command_key}",
            timeout_s=timeout_s,
        )
    except Exception as err:
        if isinstance(err, (CaptureError, CaptureTimeoutError)):
            raise ActionError(f"Capture failed: {err}") from err
        raise

    # Block until the result lands.
    import asyncio

    deadline = asyncio.get_event_loop().time() + timeout_s + 1
    while asyncio.get_event_loop().time() < deadline:
        result = orchestrator.get_session_result(f"{device_id}.{command_key}")
        if result is not None:
            return {
                "captured": result.to_dict(),
                "raw_timings": list(result.raw_timings),
                "carrier_frequency_hz": result.signal_category.carrier_frequency_hz,
            }
        await asyncio.sleep(0.1)
    raise ActionError("Capture timed out without a result")


@_register("sniffer/list")
async def _ws_sniffer_list(
    ctx: RuneWebSocketContext, _msg: dict[str, Any]
) -> dict[str, Any]:
    """List every unknown remote and its signals.

    Used by the SPA's Sniffer tab to show what the engine has caught.
    """
    repo = ctx.hass.data.get(DOMAIN, {})
    if not repo:
        return {"remotes": []}

    # Find the first signal repository across all entries.
    signal_repo = None
    for entry_data in repo.values():
        if isinstance(entry_data, dict):
            signal_repo = entry_data.get("signal_repository")
            if signal_repo is not None:
                break

    if signal_repo is None:
        return {"remotes": []}

    remotes = await signal_repo.load_remotes()
    return {
        "remotes": [
            {
                "id": r.id,
                "label": r.label,
                "protocol_label": r.protocol_label,
                "device_address": r.device_address,
                "dismissed": r.dismissed,
                "signal_count": len(r.signals),
                "signals": [
                    {
                        "id": s.id,
                        "fingerprint": s.fingerprint,
                        "byte_hash": s.byte_hash,
                        "decoded_fingerprint": s.decoded_fingerprint,
                        "protocol_label": s.protocol_label,
                        "code_hex": s.code_hex,
                        "hit_count": s.hit_count,
                        "first_seen": s.first_seen,
                        "last_seen": s.last_seen,
                        "alias": s.alias,
                    }
                    for s in r.signals
                ],
            }
            for r in remotes
        ]
    }


@_register("sniffer/dismiss")
async def _ws_sniffer_dismiss(
    ctx: RuneWebSocketContext, msg: dict[str, Any]
) -> dict[str, Any]:
    """Dismiss a remote so it stops appearing in the Sniffer tab."""
    remote_id = msg.get("remote_id")
    if not remote_id:
        raise ActionError("remote_id is required")

    repo = ctx.hass.data.get(DOMAIN, {})
    signal_repo = None
    for entry_data in repo.values():
        if isinstance(entry_data, dict):
            signal_repo = entry_data.get("signal_repository")
            if signal_repo is not None:
                break
    if signal_repo is None:
        raise ActionError("Sniffer not wired")

    remotes = await signal_repo.load_remotes()
    for remote in remotes:
        if remote.id == remote_id:
            from dataclasses import replace

            updated = replace(remote, dismissed=not remote.dismissed)
            await signal_repo.upsert_remote(updated)
            return {"dismissed": updated.dismissed}

    raise CommandNotLearnedError(f"Unknown remote {remote_id!r}")


@_register("action/list")
async def _ws_action_list(
    ctx: RuneWebSocketContext, _msg: dict[str, Any]
) -> dict[str, Any]:
    """List every action binding."""
    from custom_components.rune.adapters.storage.memory import (
        InMemoryActionRepository,
    )

    # The action store is built per-entry. Walk the hass.data to
    # collect every entry's actions and merge them.
    actions: list[dict[str, Any]] = []
    for entry_data in ctx.hass.data.get(DOMAIN, {}).values():
        if not isinstance(entry_data, dict):
            continue
        action_repo = entry_data.get("action_repository")
        if action_repo is None:
            continue
        loaded = await action_repo.load()
        actions.extend(a.to_dict() for a in loaded)

    # Stub an empty repo to use the to_dict path uniformly even
    # when no actions are stored (tests / first boot).
    if not actions:
        InMemoryActionRepository()

    return {"actions": actions}


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
