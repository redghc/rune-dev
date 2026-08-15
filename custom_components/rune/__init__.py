"""RUNE — Remote Universal Network Engine.

A Home Assistant custom integration for IR/RF remote control. This
package is loaded by HA via the standard ``async_setup_entry`` flow
declared in :func:`async_setup_entry` below.

Lifecycle:

- :func:`async_setup_entry` — called by HA when a user adds the
  integration via the config flow. Wires the device + action
  repositories, builds the coordinator, forwards the entry to each
  platform, and registers the public services.
- :func:`async_unload_entry` — reverses setup on user removal or
  options change.
- :func:`async_remove_entry` — runs when the user removes the
  integration. RUNE leaves the data in place by default so
  re-installing preserves the setup.

The coordinator lives in :mod:`custom_components.rune.platforms._coordinator`.
Every platform shell (:mod:`platforms.fan`, :mod:`platforms.button`, …)
delegates TX and action dispatch through it.

HA imports are deferred to inside the lifecycle functions so this
module imports cleanly in pure-Python environments (CI, tests, dev).
The HA core is only required when ``async_setup_entry`` runs.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.rune._platform_support._coordinator import (
    DevicePlatformCoordinator,
)
from custom_components.rune.adapters.transmitters.factory import select_transmitter
from custom_components.rune.adapters.tx_gate import TxGate
from custom_components.rune.const import (
    DOMAIN,
    MANUFACTURER,
)
from custom_components.rune.migrations import (
    LATEST_ACTION_VERSION,
    LATEST_DEVICE_VERSION,
    LATEST_SIGNAL_VERSION,
    migrate_actions,
    migrate_devices,
    migrate_signals,
)


def _build_repositories(hass: Any) -> tuple[Any, Any, Any]:
    """Construct the three HA-Store-backed repositories.

    Deferred import: the HA Store adapter is only needed at integration
    setup time, never at module import. Keeping the import here lets
    the rest of the package stay importable in pure-Python environments.
    """
    from custom_components.rune.adapters.storage.ha_store import (
        HAStoreActionRepository,
        HAStoreDeviceRepository,
        HAStoreSignalRepository,
    )

    return (
        HAStoreDeviceRepository(hass),
        HAStoreActionRepository(hass),
        HAStoreSignalRepository(hass),
    )

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)

__version__ = "0.2.9"


# ---------------------------------------------------------------------------
# Integration setup
# ---------------------------------------------------------------------------


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    """Set up RUNE from a config entry.

    Steps:

    1. Load (and migrate) the three persisted stores.
    2. Build the TX gate + coordinator.
    3. Forward the entry to every platform so each platform file can
       enumerate devices and add its entities.
    4. Register the integration's public services
       (``rune.send_command``, ``rune.learn_command``).
    5. Register the WebSocket command handlers.

    On success, the coordinator lives in ``hass.data[DOMAIN][entry_id]``.
    """
    hass.data.setdefault(DOMAIN, {})

    # 1. Repositories with on-disk migration.
    device_repo, action_repo, signal_repo = _build_repositories(hass)

    await _migrate_all(hass, device_repo, action_repo, signal_repo)

    # 2. Coordinator.
    tx_gate = TxGate(mirror=_mirror_for_entry(hass, entry))
    coordinator = DevicePlatformCoordinator(
        hass=hass,
        device_repository=device_repo,
        action_repository=action_repo,
        tx_gate=tx_gate,
        transmitter_factory=select_transmitter,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "device_repository": device_repo,
        "action_repository": action_repo,
        "signal_repository": signal_repo,
        # A flat cache the config flow reads so the "Manage devices"
        # menu stays in sync with whatever the coordinator surfaces.
        # Refreshed on every entry reload and on every successful
        # ``rune.device/create`` call.
        "_flow_devices_cache": [],
    }

    # 3. Forward to each platform. HA instantiates the platform module
    #    on demand; the module's ``async_setup_entry`` builds entities.
    from homeassistant.const import Platform

    platforms_list = [
        Platform.FAN,
        Platform.CLIMATE,
        Platform.LIGHT,
        Platform.COVER,
        Platform.MEDIA_PLAYER,
        Platform.SWITCH,
        Platform.BUTTON,
        Platform.REMOTE,
    ]
    await hass.config_entries.async_forward_entry_setups(entry, platforms_list)

    # 4. Services.
    _register_services(hass, coordinator)

    # 5. WebSocket commands.
    from custom_components.rune.websocket_api import async_register_websocket_commands

    async_register_websocket_commands(hass)

    # 6. Sidebar panel — the user-visible front-end. The HTML lives at
    #    ``frontend/dist/rune-panel.html``; HA serves it from the
    #    static path registered here. The panel's JS talks to the WS
    #    API registered above, so it shares the same handlers as
    #    every other client (services, options flow, custom SPA).
    await _register_panel(hass, entry)

    return True


async def _register_panel(hass: Any, entry: Any) -> None:
    """Register the RUNE sidebar panel and its static asset path.

    The panel HTML is served from the ``frontend/dist/`` directory of
    the integration. We register a static path so HA can load the
    file, then call ``panel_custom.async_register_panel`` to add the
    sidebar entry.

    Errors during panel registration are logged but do not fail the
    setup — the integration remains usable via the options flow even
    if the panel can't be mounted.
    """
    try:
        from pathlib import Path

        from homeassistant.components import panel_custom
        from homeassistant.components.http import StaticPathConfig

        from custom_components.rune.const import (
            PANEL_HTML_FILENAME,
            PANEL_ICON,
            PANEL_JS_FILENAME,
            PANEL_STATIC_PATH,
            PANEL_TITLE,
            PANEL_URL,
        )
    except Exception as err:
        _LOGGER.error(
            "rune: failed to import HA panel dependencies: %s", err
        )
        return

    # Resolve asset paths relative to THIS package. Using
    # ``Path(__file__).parent`` is more reliable than
    # ``async_get_integration(hass, DOMAIN).file_path`` because it
    # doesn't depend on the integration loader having populated the
    # registry yet when ``async_setup_entry`` runs.
    package_root = Path(__file__).parent
    js_path = package_root / "frontend" / "dist" / PANEL_JS_FILENAME
    html_path = package_root / "frontend" / "dist" / PANEL_HTML_FILENAME

    # Refuse to register if the asset files don't exist on disk.
    if not js_path.is_file():
        _LOGGER.error(
            "rune: cannot register sidebar panel — JS shim not found at %s",
            js_path,
        )
        return
    if not html_path.is_file():
        _LOGGER.error(
            "rune: cannot register sidebar panel — HTML not found at %s",
            html_path,
        )
        return

    js_url = f"{PANEL_STATIC_PATH}/{PANEL_JS_FILENAME}"
    html_url = f"{PANEL_STATIC_PATH}/{PANEL_HTML_FILENAME}"

    # Static path registration is **stateful** — HA keeps the path
    # across reloads and rejects duplicates with ``ValueError``.
    # Make it idempotent: skip paths that are already registered.
    existing_paths = set(hass.http._static_paths) if hasattr(hass.http, "_static_paths") else set()
    new_static_paths = []
    for url, fs_path in (
        (js_url, js_path),
        (html_url, html_path),
    ):
        if url in existing_paths:
            _LOGGER.debug("rune: static path %s already registered; skipping", url)
            continue
        new_static_paths.append(StaticPathConfig(url, str(fs_path)))

    if new_static_paths:
        try:
            await hass.http.async_register_static_paths(new_static_paths)
            _LOGGER.info(
                "rune: registered static paths: %s",
                [c.url_path for c in new_static_paths],
            )
        except Exception as err:
            _LOGGER.error("rune: failed to register static paths: %s", err)
            return

    # Panel registration is also stateful — HA keeps the panel
    # across reloads. Remove + re-register so an updated module_url
    # (different cache-buster) actually replaces the old one.
    from custom_components.rune import __version__

    module_url = f"{js_url}?v={__version__}"

    try:
        await panel_custom.async_remove_panel(hass, PANEL_URL)
    except Exception as err:
        _LOGGER.debug("rune: no prior panel to remove: %s", err)

    try:
        await panel_custom.async_register_panel(
            hass,
            webcomponent_name="rune-panel",
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            frontend_url_path=PANEL_URL,
            config={"entry_id": entry.entry_id},
            require_admin=False,  # MVP: every user can manage devices
            embed_iframe=False,
            trust_external=False,
            module_url=module_url,
        )
        _LOGGER.info(
            "rune: sidebar panel registered at %s (module_url=%s)",
            PANEL_URL,
            module_url,
        )
    except Exception as err:
        _LOGGER.error("rune: failed to register sidebar panel: %s", err)


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    """Tear down a RUNE entry."""
    from homeassistant.const import Platform

    platforms_list = [
        Platform.FAN,
        Platform.CLIMATE,
        Platform.LIGHT,
        Platform.COVER,
        Platform.MEDIA_PLAYER,
        Platform.SWITCH,
        Platform.BUTTON,
        Platform.REMOTE,
    ]
    unloaded = await hass.config_entries.async_unload_platforms(entry, platforms_list)
    if not unloaded:
        return False

    # Remove the entry's data.
    hass.data[DOMAIN].pop(entry.entry_id, None)

    # Drop the service registrations if no other entries remain.
    if not hass.data[DOMAIN]:
        _unregister_services(hass)
        from custom_components.rune.websocket_api import async_unregister_websocket_commands

        async_unregister_websocket_commands(hass)

    return True


async def async_remove_entry(hass: Any, entry: Any) -> None:
    """Drop the on-disk store when the user removes the integration.

    Unlike HAIR, RUNE's user-facing catalog lives in separate stores
    for devices / actions / unknown signals. The ``async_remove_entry``
    hook only fires when the user explicitly deletes the entry, so
    we leave the data in place by default — the user can re-install
    without losing their setup.
    """
    # No-op by design. Override here when a destructive removal is wanted.


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------


async def _migrate_all(
    hass: Any,
    device_repo: Any,
    action_repo: Any,
    signal_repo: Any,
) -> None:
    """Run the migration chain on each store and persist the result.

    Each migration is pure (list[dict] → list[dict]); the adapter
    loads the records, the chain runs, and we save the migrated
    records back. Errors are logged but don't fail setup — the
    data is preserved either way.
    """

    for label, repo, migrate_fn, target_version in (
        ("rune.devices", device_repo, migrate_devices, LATEST_DEVICE_VERSION),
        ("rune.actions", action_repo, migrate_actions, LATEST_ACTION_VERSION),
        ("rune.unknown_signals", signal_repo, migrate_signals, LATEST_SIGNAL_VERSION),
    ):
        try:
            records = await _read_raw_records(repo)
            migrated, final_version = migrate_fn(records, from_version=0)
            if final_version != target_version:
                _LOGGER.warning(
                    "rune: %s migration stopped at v%d (expected v%d); "
                    "current build may need an upgrade",
                    label,
                    final_version,
                    target_version,
                )
            await _write_raw_records(repo, migrated)
        except Exception as err:
            _LOGGER.warning("rune: migration of %s failed: %s", label, err)


async def _read_raw_records(repo: Any) -> list[dict]:
    """Read raw dict records from the underlying Store."""
    if hasattr(repo, "_store"):
        return list(await repo._store.async_load() or [])
    if hasattr(repo, "load"):
        return [d.to_dict() for d in await repo.load()]
    return []


async def _write_raw_records(repo: Any, records: list[dict]) -> None:
    """Write raw dict records through the underlying Store."""
    if hasattr(repo, "_store"):
        await repo._store.async_save(records)


def _mirror_for_entry(hass: Any, entry: Any) -> Any:
    """Construct the MirrorLog used by the TX gate.

    Returns a fresh in-process mirror for now; Phase 7 will wire it
    to a HA-store-backed mirror for cross-restart continuity.
    """
    from custom_components.rune.sniffer.mirror import MirrorLog

    return MirrorLog()


# ---------------------------------------------------------------------------
# Service handlers
# ---------------------------------------------------------------------------


def _register_services(hass: Any, coordinator: DevicePlatformCoordinator) -> None:
    """Register the integration's public services."""
    if not hass.services.has_service(DOMAIN, "send_command"):
        hass.services.async_register(
            DOMAIN,
            "send_command",
            lambda call: _async_handle_send_command(coordinator, call),
        )

    if not hass.services.has_service(DOMAIN, "learn_command"):
        hass.services.async_register(
            DOMAIN,
            "learn_command",
            lambda call: _async_handle_learn_command(coordinator, call),
        )


def _unregister_services(hass: Any) -> None:
    """Drop every service the integration registered."""
    for service_name in ("send_command", "learn_command"):
        if hass.services.has_service(DOMAIN, service_name):
            hass.services.async_remove(DOMAIN, service_name)


async def _async_handle_send_command(
    coordinator: DevicePlatformCoordinator, call: Any
) -> None:
    """Handle ``rune.send_command``.

    Required service data:

    - ``device_id`` — id of the RuneDevice.
    - ``command_key`` — key of the PulseCommand to send.
    """
    device_id = call.data.get("device_id")
    command_key = call.data.get("command_key")
    if not device_id or not command_key:
        _LOGGER.warning("rune.send_command missing device_id or command_key")
        return
    device = await coordinator._devices.get(device_id)  # type: ignore[attr-defined]
    if device is None:
        _LOGGER.warning("rune.send_command: unknown device %s", device_id)
        return
    command = device.commands.get(command_key)
    if command is None:
        _LOGGER.warning(
            "rune.send_command: device %s has no command %s", device_id, command_key
        )
        return
    await coordinator.async_send_command(device=device, command=command)


async def _async_handle_learn_command(
    coordinator: DevicePlatformCoordinator, call: Any
) -> None:
    """Handle ``rune.learn_command``.

    Placeholder: real capture-orchestrator wiring lands in Phase 4's
    integration into the sniffer. For now this just logs the request
    so the service exists in the HA service panel without errors.
    """
    _LOGGER.info(
        "rune.learn_command invoked (UI capture flow not yet wired in MVP)"
    )


# ---------------------------------------------------------------------------
# Re-exports for HA discovery
# ---------------------------------------------------------------------------

__all__ = [
    "MANUFACTURER",
    "async_remove_entry",
    "async_setup_entry",
    "async_unload_entry",
]
