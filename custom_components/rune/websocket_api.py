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

import voluptuous as vol

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
_SCHEMAS: dict[str, vol.Schema] = {}


def _register(command: str) -> Callable[[_Handler], _Handler]:
    def decorator(func: _Handler) -> _Handler:
        _HANDLERS[command] = func
        return func

    return decorator


def _register_schema(command: str, schema: vol.Schema) -> None:
    """Pair a voluptuous schema with a previously-decorated command."""
    _SCHEMAS[command] = schema


def _schema_for(command: str) -> vol.Schema:
    """Return the schema for ``command``; falls back to permissive."""
    return _SCHEMAS.get(command) or vol.Schema({}, extra=vol.ALLOW_EXTRA)


# Per-command schemas. ``extra=vol.ALLOW_EXTRA`` lets HA's dispatcher accept
# every payload key the SPA sends; required fields are typed so typos surface
# as ``ERR_INVALID_FORMAT`` instead of silent ``None``.
_register_schema(
    "list",
    vol.Schema({}, extra=vol.ALLOW_EXTRA),
)
_register_schema(
    "device/get",
    vol.Schema(
        {vol.Required("device_id"): str},
        extra=vol.ALLOW_EXTRA,
    ),
)
_register_schema(
    "device/create",
    vol.Schema(
        {
            vol.Required("name"): str,
            vol.Required("category"): str,
        },
        extra=vol.ALLOW_EXTRA,
    ),
)
_register_schema(
    "device/update",
    vol.Schema(
        {vol.Required("device_id"): str},
        extra=vol.ALLOW_EXTRA,
    ),
)
_register_schema(
    "device/delete",
    vol.Schema(
        {vol.Required("device_id"): str},
        extra=vol.ALLOW_EXTRA,
    ),
)
_register_schema(
    "command/learn",
    vol.Schema(
        {
            vol.Required("device_id"): str,
            vol.Required("command_key"): str,
            vol.Optional("timeout_s"): vol.Coerce(float),
        },
        extra=vol.ALLOW_EXTRA,
    ),
)
_register_schema(
    "sniffer/list",
    vol.Schema({}, extra=vol.ALLOW_EXTRA),
)
_register_schema(
    "sniffer/dismiss",
    vol.Schema(
        {vol.Required("remote_id"): str},
        extra=vol.ALLOW_EXTRA,
    ),
)
_register_schema(
    "action/list",
    vol.Schema({}, extra=vol.ALLOW_EXTRA),
)
_register_schema(
    "transmitter/list",
    vol.Schema({}, extra=vol.ALLOW_EXTRA),
)
_register_schema(
    "receiver/list",
    vol.Schema({}, extra=vol.ALLOW_EXTRA),
)
_register_schema(
    "debug/registry-check",
    vol.Schema({}, extra=vol.ALLOW_EXTRA),
)


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

        # HA's WS dispatcher validates ``msg`` against ``schema`` before
        # forwarding to the handler. Without a permissive schema it rejects
        # every payload carrying anything beyond ``{id, type}`` with
        # "extra keys not allowed" (voluptuous' default PREVENT_EXTRA).
        # ``schema is False`` would skip validation but force ``len(msg) <= 2``
        # -- incompatible with the bridge, which spreads the full payload
        # (``{id, type, name, category, ...}``) into the WS message.
        # Pass a per-command schema with ``extra=vol.ALLOW_EXTRA`` so HA
        # accepts every field the handler reads via ``msg.get(...)``.
        _callback._ws_command = full  # type: ignore[attr-defined]
        websocket_api.async_register_command(
            hass, full, _callback, schema=_schema_for(command)
        )


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
    ir_transmitter = msg.get("ir_transmitter")
    rf_transmitter = msg.get("rf_transmitter")
    tx_list_raw = msg.get("transmitter_entity_ids")
    if tx_list_raw and isinstance(tx_list_raw, list):
        tx_list = [str(t) for t in tx_list_raw if t]
    else:
        tx_list = [str(t) for t in (ir_transmitter, rf_transmitter, transmitter) if t]

    if not name or not category_value or not tx_list:
        raise ActionError("name, category, and at least one transmitter are required")

    receiver = msg.get("receiver")
    ir_receiver = msg.get("ir_receiver")
    rf_receiver = msg.get("rf_receiver")
    rx_list_raw = msg.get("receiver_entity_ids")
    if rx_list_raw and isinstance(rx_list_raw, list):
        rx_list = [str(r) for r in rx_list_raw if r]
    else:
        rx_list = [str(r) for r in (ir_receiver, rf_receiver, receiver) if r]

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
        transmitter_entity_ids=tx_list,
        receiver_entity_ids=rx_list,
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

    tx_list = msg.get("transmitter_entity_ids")
    if tx_list is None:
        ir_tx = msg.get("ir_transmitter")
        rf_tx = msg.get("rf_transmitter")
        legacy_tx = msg.get("transmitter")
        if ir_tx is not None or rf_tx is not None or legacy_tx is not None:
            tx_list = [str(t) for t in (ir_tx, rf_tx, legacy_tx) if t]
        else:
            tx_list = device.transmitter_entity_ids

    rx_list = msg.get("receiver_entity_ids")
    if rx_list is None:
        ir_rx = msg.get("ir_receiver")
        rf_rx = msg.get("rf_receiver")
        legacy_rx = msg.get("receiver")
        if ir_rx is not None or rf_rx is not None or legacy_rx is not None:
            rx_list = [str(r) for r in (ir_rx, rf_rx, legacy_rx) if r]
        else:
            rx_list = device.receiver_entity_ids

    updated = RuneDevice(
        id=device.id,
        name=msg.get("name", device.name),
        category=device.category,
        manufacturer=msg.get("manufacturer", device.manufacturer),
        model=msg.get("model", device.model),
        transmitter_entity_ids=tx_list,
        receiver_entity_ids=rx_list,
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


@_register("debug/registry-check")
async def _ws_debug_registry_check(
    ctx: RuneWebSocketContext, msg: dict[str, Any]
) -> dict[str, Any]:
    """Dump the raw registry view for every entity in the IR/RF/ESPHome
    domains.

    Diagnostic helper for the emitter / receiver picker: tells us
    whether each entity is registered, whether it's linked to a
    device, and what the device's area is. Empty fields explain why
    ``area`` / ``device_name`` come back blank from ``transmitter/list``.
    """
    _ = msg  # noqa: F841 — kept for handler-signature parity
    entity_payload, entity_err = _try_entity_registry(ctx.hass)
    device_payload, device_err = _try_device_registry(ctx.hass)
    area_payload, area_err = _try_area_registry(ctx.hass)
    area_by_entity, device_by_entity = entity_payload
    device_by_id = device_payload
    area_by_id = area_payload
    rows: list[dict[str, Any]] = []
    for state in ctx.hass.states.async_all():
        domain = state.entity_id.split(".", 1)[0] if "." in state.entity_id else ""
        if domain not in {"infrared", "remote", "esphome"}:
            continue
        entity_area_id = area_by_entity.get(state.entity_id, "")
        entity_device_id = device_by_entity.get(state.entity_id, "")
        device = device_by_id.get(entity_device_id, {}) if entity_device_id else {}
        device_area_id = device.get("area_id", "")
        resolved_area_id = entity_area_id or device_area_id
        attrs = getattr(state, "attributes", {}) or {}
        rows.append(
            {
                "entity_id": state.entity_id,
                "friendly_name": state.name,
                "in_entity_registry": state.entity_id in area_by_entity
                or state.entity_id in device_by_entity,
                "entity_area_id": entity_area_id or None,
                "entity_device_id": entity_device_id or None,
                "device_name": device.get("name", "") or None,
                "device_area_id": device_area_id or None,
                "resolved_area_id": resolved_area_id or None,
                "resolved_area_name": area_by_id.get(resolved_area_id, "") or None,
                "device_area_name": area_by_id.get(device_area_id, "") or None,
                "entity_area_name": area_by_id.get(entity_area_id, "") or None,
                "state_attributes_area": attrs.get("area_id"),
                "state_attributes_device": attrs.get("device_id"),
                "entity_platform": attrs.get("entity_platform") or attrs.get("platform"),
            }
        )
    return {
        "registries": {
            "code_marker": "rune-registry-debug-v2-2026-08-23",
            "entity_registry_ok": entity_err is None,
            "entity_count": len(area_by_entity) + len(device_by_entity) // 2,
            "entity_error": entity_err,
            "device_registry_ok": device_err is None,
            "device_count": len(device_by_id),
            "device_error": device_err,
            "area_registry_ok": area_err is None,
            "area_count": len(area_by_id),
            "area_error": area_err,
            "hass_type": type(ctx.hass).__name__,
            "has_helpers": hasattr(ctx.hass, "helpers"),
            "helpers_type": type(getattr(ctx.hass, "helpers", None)).__name__,
        },
        "rows": rows,
    }


def _try_entity_registry(hass: Any) -> tuple[tuple[dict[str, str], dict[str, str]], str | None]:
    """Return ``(({entity_id: area_id}, {entity_id: device_id}), error)``.
    ``error`` is ``None`` when the registry was reached successfully."""
    try:
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(hass)
        area: dict[str, str] = {}
        device: dict[str, str] = {}
        for entry in registry.entities.values():
            area_id = getattr(entry, "area_id", None)
            device_id = getattr(entry, "device_id", None)
            if area_id:
                area[entry.entity_id] = area_id
            if device_id:
                device[entry.entity_id] = device_id
        return (area, device), None
    except Exception as exc:
        return ({}, {}), f"{type(exc).__name__}: {exc}"


def _try_device_registry(hass: Any) -> tuple[dict[str, dict[str, str]], str | None]:
    try:
        from homeassistant.helpers import device_registry as dr

        registry = dr.async_get(hass)
        out: dict[str, dict[str, str]] = {}
        for entry in registry.devices.values():
            name = (
                getattr(entry, "name", None)
                or " ".join(
                    part
                    for part in (
                        getattr(entry, "manufacturer", None),
                        getattr(entry, "model", None),
                    )
                    if part
                )
                or getattr(entry, "id", "")
            )
            out[entry.id] = {
                "name": str(name) if name else "",
                "area_id": str(getattr(entry, "area_id", None) or ""),
            }
        return out, None
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def _try_area_registry(hass: Any) -> tuple[dict[str, str], str | None]:
    try:
        from homeassistant.helpers import area_registry as ar

        registry = ar.async_get(hass)
        out: dict[str, str] = {}
        for entry in registry.areas.values():
            name = getattr(entry, "name", None) or getattr(entry, "id", "")
            if name:
                out[entry.id] = str(name)
        return out, None
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


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
    return _list_entities_for_domains(hass, ("infrared", "esphome", "remote"))


def _list_entities_for_domains(
    hass: Any, domains: tuple[str, ...]
) -> list[dict[str, str]]:
    """Return ``[{entity_id, name, state, area, device_name}]`` for
    every state matching the domains.

    Area resolution order: ``entity.area_id`` → ``entity.device.area_id``.
    Device names resolve to the friendly name of the device that owns
    the entity (via ``entity.device_id``); missing links surface as an
    empty string so the frontend can render an honest placeholder
    instead of fabricated data.
    """
    area_by_id = _area_index(hass)
    area_by_entity, device_by_entity = _entity_indexes(hass)
    device_by_id = _device_index(hass)
    entities: list[dict[str, str]] = []
    for state in hass.states.async_all():
        domain = state.entity_id.split(".", 1)[0] if "." in state.entity_id else ""
        if domain in domains:
            friendly_name = (
                getattr(state, "name", None)
                or (getattr(state, "attributes", {}) or {}).get("friendly_name")
                or state.entity_id
            )
            area_name = _resolve_area(state.entity_id, area_by_entity, device_by_entity, device_by_id, area_by_id)
            device_name = _resolve_device_name(
                state.entity_id, device_by_entity, device_by_id
            )
            entities.append(
                {
                    "entity_id": state.entity_id,
                    "name": str(friendly_name),
                    "state": state.state,
                    "area": area_name,
                    "device_name": device_name,
                }
            )
    return entities


def _resolve_area(
    entity_id: str,
    area_by_entity: dict[str, str],
    device_by_entity: dict[str, str],
    device_by_id: dict[str, dict[str, str]],
    area_by_id: dict[str, str],
) -> str:
    """Resolve the friendly area name for an entity.

    Mirrors the HA UI: an entity can have its own ``area_id`` (overrides
    everything) or inherit the area from the device it belongs to.
    Returns ``""`` when neither link points at an area.
    """
    area_id = area_by_entity.get(entity_id, "") or ""
    if not area_id:
        device_id = device_by_entity.get(entity_id, "") or ""
        if device_id:
            area_id = device_by_id.get(device_id, {}).get("area_id", "") or ""
    return area_by_id.get(area_id, "") if area_id else ""


def _resolve_device_name(
    entity_id: str,
    device_by_entity: dict[str, str],
    device_by_id: dict[str, dict[str, str]],
) -> str:
    """Friendly name of the device that owns ``entity_id``. Empty when
    the entity isn't linked to any device."""
    device_id = device_by_entity.get(entity_id, "") or ""
    if not device_id:
        return ""
    return device_by_id.get(device_id, {}).get("name", "") or ""


def _entity_indexes(hass: Any) -> tuple[dict[str, str], dict[str, str]]:
    """Return ``({entity_id: area_id}, {entity_id: device_id})`` for
    every registered entity.

    Imports the registry module directly because ``hass.helpers`` is
    not always populated on every HA core version. Empty dicts when
    the registry isn't loaded.
    """
    try:
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(hass)
    except Exception:
        return {}, {}
    area: dict[str, str] = {}
    device: dict[str, str] = {}
    for entry in registry.entities.values():
        area_id = getattr(entry, "area_id", None)
        device_id = getattr(entry, "device_id", None)
        if area_id:
            area[entry.entity_id] = area_id
        if device_id:
            device[entry.entity_id] = device_id
    return area, device


def _device_index(hass: Any) -> dict[str, dict[str, str]]:
    """Return ``{device_id: {name, area_id}}`` for every registered
    device. ``name`` falls back to ``manufacturer + model`` and then
    to the device id so the row always has a non-empty label. ``area_id``
    stays empty when the device isn't assigned to an area.

    Imports the registry module directly because ``hass.helpers`` is
    not always populated on every HA core version.
    """
    try:
        from homeassistant.helpers import device_registry as dr

        registry = dr.async_get(hass)
    except Exception:
        return {}
    out: dict[str, dict[str, str]] = {}
    for entry in registry.devices.values():
        name = (
            getattr(entry, "name", None)
            or " ".join(
                part
                for part in (getattr(entry, "manufacturer", None), getattr(entry, "model", None))
                if part
            )
            or getattr(entry, "id", "")
        )
        out[entry.id] = {
            "name": str(name) if name else "",
            "area_id": str(getattr(entry, "area_id", None) or ""),
        }
    return out


def _area_index(hass: Any) -> dict[str, str]:
    """Return ``{area_id: area_name}`` for every registered area.

    Empty dict when the area registry isn't available. Names are
    localized when possible (the registry exposes ``name`` as a
    plain string in modern cores). Imports the registry module
    directly because ``hass.helpers`` is not always populated on
    every HA core version.
    """
    try:
        from homeassistant.helpers import area_registry as ar

        registry = ar.async_get(hass)
    except Exception:
        return {}
    out: dict[str, str] = {}
    for entry in registry.areas.values():
        name = getattr(entry, "name", None) or getattr(entry, "id", "")
        if name:
            out[entry.id] = str(name)
    return out


__all__ = [
    "async_register_websocket_commands",
    "async_unregister_websocket_commands",
]
