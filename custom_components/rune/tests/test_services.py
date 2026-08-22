"""Tests for the ``rune.send_command`` and ``rune.learn_command`` services.

The two services share a single HA ``device_id`` translator
(``_resolve_rune_device_id``). We exercise that helper directly and
then assert the high-level service call paths raise the expected
``ServiceValidationError`` for missing / unknown input.

``homeassistant`` is not installed in the test environment — we
inject a ``sys.modules`` stub for ``homeassistant.helpers.device_registry``
and ``homeassistant.exceptions`` before importing the handlers.
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


def _install_ha_stubs() -> None:
    """Inject minimal ``homeassistant.*`` modules so the handlers can
    import them lazily. Idempotent."""
    if "homeassistant" in sys.modules:
        return

    ha = types.ModuleType("homeassistant")
    helpers = types.ModuleType("homeassistant.helpers")
    dr_mod = types.ModuleType("homeassistant.helpers.device_registry")
    exc_mod = types.ModuleType("homeassistant.exceptions")

    class ServiceValidationError(Exception):  # type: ignore[no-redef]
        pass

    exc_mod.ServiceValidationError = ServiceValidationError
    # device_registry exposes ``async_get`` lazily; the handler calls it
    # via the imported reference, so any attribute access on the module
    # succeeds. We patch the specific ``async_get`` symbol via setattr.
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.device_registry"] = dr_mod
    sys.modules["homeassistant.exceptions"] = exc_mod


class _FakeCall:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data


def _patch_device_registry(reg: Any) -> None:
    """Make ``homeassistant.helpers.device_registry.async_get(hass)``
    return the supplied registry stub."""
    import homeassistant.helpers.device_registry as dr

    dr.async_get = lambda hass: reg  # type: ignore[assignment]


def _make_hass_with_device(ha_id: str, rune_uuid: str) -> MagicMock:
    fake_entry = MagicMock()
    fake_entry.identifiers = {("rune", rune_uuid)}
    registry = MagicMock()
    registry.async_get.return_value = fake_entry
    _patch_device_registry(registry)
    return MagicMock()


def _make_hass_unknown() -> MagicMock:
    registry = MagicMock()
    registry.async_get.return_value = None
    _patch_device_registry(registry)
    return MagicMock()


def _make_coordinator(_rune_uuid: str, has_command: bool = True) -> MagicMock:
    coord = MagicMock()
    device = MagicMock()
    device.name = "Bedroom fan"
    device.commands = {"off": MagicMock()} if has_command else {}
    coord._devices = MagicMock()
    coord._devices.get = AsyncMock(return_value=device)
    coord.async_send_command = AsyncMock()
    return coord


_install_ha_stubs()


# ---------------------------------------------------------------------------
# Translator
# ---------------------------------------------------------------------------


def test_resolve_rune_device_id_translates_ha_id() -> None:
    from custom_components.rune import _resolve_rune_device_id

    hass = _make_hass_with_device("ha-1", "rune-uuid-1")
    assert _resolve_rune_device_id(hass, "ha-1") == "rune-uuid-1"


def test_resolve_rune_device_id_returns_none_when_unknown() -> None:
    from custom_components.rune import _resolve_rune_device_id

    hass = _make_hass_unknown()
    assert _resolve_rune_device_id(hass, "missing") is None


def test_resolve_rune_device_id_returns_none_for_other_domain() -> None:
    from custom_components.rune import _resolve_rune_device_id

    fake_entry = MagicMock()
    fake_entry.identifiers = {("other", "x")}
    registry = MagicMock()
    registry.async_get.return_value = fake_entry
    _patch_device_registry(registry)
    hass = MagicMock()

    assert _resolve_rune_device_id(hass, "ha-1") is None


# ---------------------------------------------------------------------------
# send_command
# ---------------------------------------------------------------------------


async def test_send_command_happy_path() -> None:
    from custom_components.rune import _async_handle_send_command

    hass = _make_hass_with_device("ha-1", "rune-uuid-1")
    coord = _make_coordinator("rune-uuid-1", has_command=True)

    await _async_handle_send_command(
        hass, coord, _FakeCall({"device_id": "ha-1", "command_key": "off"})
    )
    coord.async_send_command.assert_awaited_once()


async def test_send_command_rejects_missing_device_id() -> None:
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.rune import _async_handle_send_command

    hass = _make_hass_with_device("ha-1", "rune-uuid-1")
    coord = _make_coordinator("rune-uuid-1")

    with pytest.raises(ServiceValidationError) as exc_info:
        await _async_handle_send_command(
            hass, coord, _FakeCall({"command_key": "off"})
        )
    assert "device_id" in str(exc_info.value).lower()


async def test_send_command_rejects_missing_command_key() -> None:
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.rune import _async_handle_send_command

    hass = _make_hass_with_device("ha-1", "rune-uuid-1")
    coord = _make_coordinator("rune-uuid-1")

    with pytest.raises(ServiceValidationError) as exc_info:
        await _async_handle_send_command(
            hass, coord, _FakeCall({"device_id": "ha-1"})
        )
    assert "command_key" in str(exc_info.value).lower()


async def test_send_command_rejects_unknown_ha_device() -> None:
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.rune import _async_handle_send_command

    hass = _make_hass_unknown()
    coord = _make_coordinator("rune-uuid-1")

    with pytest.raises(ServiceValidationError) as exc_info:
        await _async_handle_send_command(
            hass, coord, _FakeCall({"device_id": "ha-missing", "command_key": "off"})
        )
    assert "unknown" in str(exc_info.value).lower()


async def test_send_command_rejects_unknown_command() -> None:
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.rune import _async_handle_send_command

    hass = _make_hass_with_device("ha-1", "rune-uuid-1")
    coord = _make_coordinator("rune-uuid-1", has_command=False)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _async_handle_send_command(
            hass, coord, _FakeCall({"device_id": "ha-1", "command_key": "nope"})
        )
    assert "no learned command" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# learn_command
# ---------------------------------------------------------------------------


async def test_learn_command_validates_inputs() -> None:
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.rune import _async_handle_learn_command

    hass = _make_hass_with_device("ha-1", "rune-uuid-1")
    coord = MagicMock()

    with pytest.raises(ServiceValidationError) as exc_info:
        await _async_handle_learn_command(
            hass, coord, _FakeCall({"command_key": "off"})
        )
    assert "device_id" in str(exc_info.value).lower()

    with pytest.raises(ServiceValidationError) as exc_info:
        await _async_handle_learn_command(
            hass, coord, _FakeCall({"device_id": "ha-1"})
        )
    assert "command_key" in str(exc_info.value).lower()


async def test_learn_command_rejects_unknown_device() -> None:
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.rune import _async_handle_learn_command

    hass = _make_hass_unknown()
    coord = MagicMock()

    with pytest.raises(ServiceValidationError) as exc_info:
        await _async_handle_learn_command(
            hass,
            coord,
            _FakeCall({"device_id": "ha-missing", "command_key": "off"}),
        )
    assert "unknown" in str(exc_info.value).lower()


async def test_learn_command_resolves_and_accepts() -> None:
    from custom_components.rune import _async_handle_learn_command

    hass = _make_hass_with_device("ha-1", "rune-uuid-1")
    coord = MagicMock()

    # Must not raise — the handler only logs in MVP.
    await _async_handle_learn_command(
        hass,
        coord,
        _FakeCall({"device_id": "ha-1", "command_key": "off", "timeout_s": 5}),
    )
