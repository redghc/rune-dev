"""Tests for the WebSocket API command handlers.

The WS API has a thin decorator-based registry. Each handler is a
pure function from ``(ctx, msg) → payload``. These tests exercise the
handlers directly with a fake ``RuneWebSocketContext`` and an
in-memory repository.
"""
from __future__ import annotations

import pytest

from custom_components.rune.adapters.storage.memory import InMemoryDeviceRepository
from custom_components.rune.domain.enums import (
    CommandCategory,
    EntityCategory,
    SignalCategory,
)
from custom_components.rune.domain.errors import (
    ActionError,
    CommandNotLearnedError,
    UnsupportedHardwareError,
)
from custom_components.rune.domain.models import (
    PulseCommand,
    PulsePayload,
    RuneDevice,
)
from custom_components.rune.websocket_api import RuneWebSocketContext


class FakeHass:
    """Stand-in hass with a state registry."""

    def __init__(self, states: list[tuple[str, str]] | None = None) -> None:
        self._states = states or []

        class _States:
            def __init__(self, outer: FakeHass) -> None:
                self._outer = outer

            def async_all(self):
                return [
                    _FakeState(eid, st) for (eid, st) in self._outer._states
                ]

        self.states = _States(self)


class _FakeState:
    def __init__(self, entity_id: str, state: str) -> None:
        self.entity_id = entity_id
        self.state = state


def _ctx(states: list[tuple[str, str]] | None = None) -> RuneWebSocketContext:
    return RuneWebSocketContext(hass=FakeHass(states), connection_id=None)


def _device(
    *, device_id: str = "dev-1", name: str = "Bedroom fan"
) -> RuneDevice:
    return RuneDevice(
        id=device_id,
        name=name,
        category=EntityCategory.FAN,
        commands={
            "power_on": PulseCommand(
                key="power_on",
                label="Power On",
                category=CommandCategory.POWER,
                signal_category=SignalCategory.default_ir(),
                payload=PulsePayload(raw_timings=(9000, -4500)),
            ),
        },
    )


@pytest.mark.asyncio
class TestWsList:
    async def test_empty(self) -> None:
        from custom_components.rune.websocket_api import _ws_list

        repo = InMemoryDeviceRepository()

        async def _list_repo(self) -> InMemoryDeviceRepository:  # type: ignore[no-untyped-def]
            return repo

        original = RuneWebSocketContext.device_repository
        RuneWebSocketContext.device_repository = _list_repo  # type: ignore[method-assign]
        try:
            result = await _ws_list(_ctx(), {})
        finally:
            RuneWebSocketContext.device_repository = original  # type: ignore[method-assign]
        assert result == {"devices": []}

    async def test_with_devices(self) -> None:
        from custom_components.rune.websocket_api import _ws_list

        repo = InMemoryDeviceRepository()
        await repo.upsert(_device(device_id="d1", name="Fan 1"))
        await repo.upsert(_device(device_id="d2", name="Fan 2"))

        async def _list_repo(self) -> InMemoryDeviceRepository:  # type: ignore[no-untyped-def]
            return repo

        original = RuneWebSocketContext.device_repository
        RuneWebSocketContext.device_repository = _list_repo  # type: ignore[method-assign]
        try:
            result = await _ws_list(_ctx(), {})
        finally:
            RuneWebSocketContext.device_repository = original  # type: ignore[method-assign]
        assert len(result["devices"]) == 2
        assert {d["id"] for d in result["devices"]} == {"d1", "d2"}


@pytest.mark.asyncio
class TestWsDeviceGet:
    async def test_missing_id_raises(self) -> None:
        from custom_components.rune.websocket_api import _ws_device_get

        with pytest.raises(ActionError):
            await _ws_device_get(_ctx(), {})

    async def test_unknown_device_raises(self) -> None:
        from custom_components.rune.websocket_api import _ws_device_get

        repo = InMemoryDeviceRepository()

        async def _list_repo(self) -> InMemoryDeviceRepository:  # type: ignore[no-untyped-def]
            return repo

        original = RuneWebSocketContext.device_repository
        RuneWebSocketContext.device_repository = _list_repo  # type: ignore[method-assign]
        try:
            with pytest.raises(CommandNotLearnedError):
                await _ws_device_get(_ctx(), {"device_id": "missing"})
        finally:
            RuneWebSocketContext.device_repository = original  # type: ignore[method-assign]

    async def test_existing_device_returns_dict(self) -> None:
        from custom_components.rune.websocket_api import _ws_device_get

        repo = InMemoryDeviceRepository()
        await repo.upsert(_device(device_id="d1", name="Fan"))

        async def _list_repo(self) -> InMemoryDeviceRepository:  # type: ignore[no-untyped-def]
            return repo

        original = RuneWebSocketContext.device_repository
        RuneWebSocketContext.device_repository = _list_repo  # type: ignore[method-assign]
        try:
            result = await _ws_device_get(_ctx(), {"device_id": "d1"})
        finally:
            RuneWebSocketContext.device_repository = original  # type: ignore[method-assign]
        assert result["device"]["id"] == "d1"
        assert "power_on" in result["device"]["commands"]


@pytest.mark.asyncio
class TestWsDeviceDelete:
    async def test_missing_id_raises(self) -> None:
        from custom_components.rune.websocket_api import _ws_device_delete

        with pytest.raises(ActionError):
            await _ws_device_delete(_ctx(), {})

    async def test_removes_existing(self) -> None:
        from custom_components.rune.websocket_api import _ws_device_delete

        repo = InMemoryDeviceRepository()
        await repo.upsert(_device(device_id="d1"))

        async def _list_repo(self) -> InMemoryDeviceRepository:  # type: ignore[no-untyped-def]
            return repo

        original = RuneWebSocketContext.device_repository
        RuneWebSocketContext.device_repository = _list_repo  # type: ignore[method-assign]
        try:
            result = await _ws_device_delete(_ctx(), {"device_id": "d1"})
        finally:
            RuneWebSocketContext.device_repository = original  # type: ignore[method-assign]
        assert result == {"removed": True}
        assert await repo.get("d1") is None


@pytest.mark.asyncio
class TestWsDeviceCreate:
    async def test_not_implemented_in_mvp(self) -> None:
        from custom_components.rune.websocket_api import _ws_device_create

        with pytest.raises(UnsupportedHardwareError):
            await _ws_device_create(_ctx(), {})


class TestWsEntityListers:
    @pytest.mark.asyncio
    async def test_transmitter_list_filters_domains(self) -> None:
        from custom_components.rune.websocket_api import _ws_transmitter_list

        hass = FakeHass(
            states=[
                ("infrared.bedroom", "idle"),
                ("remote.broadlink", "idle"),
                ("light.kitchen", "on"),  # not an emitter
                ("esphome.living_room", "off"),
            ]
        )
        ctx = RuneWebSocketContext(hass=hass, connection_id=None)
        result = await _ws_transmitter_list(ctx, {})
        ids = {entry["entity_id"] for entry in result["transmitters"]}
        assert ids == {"infrared.bedroom", "remote.broadlink", "esphome.living_room"}

    @pytest.mark.asyncio
    async def test_receiver_list_filters_domains(self) -> None:
        from custom_components.rune.websocket_api import _ws_receiver_list

        hass = FakeHass(
            states=[
                ("infrared.bedroom_rx", "idle"),
                ("light.kitchen", "on"),
                ("esphome.living_room_rx", "off"),
            ]
        )
        ctx = RuneWebSocketContext(hass=hass, connection_id=None)
        result = await _ws_receiver_list(ctx, {})
        ids = {entry["entity_id"] for entry in result["receivers"]}
        assert ids == {"infrared.bedroom_rx", "esphome.living_room_rx"}


class TestDeviceSummary:
    def test_returns_compact_shape(self) -> None:
        from custom_components.rune.websocket_api import _device_summary

        device = _device(device_id="d1", name="My fan")
        device.transmitter_entity_ids = ["infrared.bedroom"]
        summary = _device_summary(device)
        assert summary == {
            "id": "d1",
            "name": "My fan",
            "category": "fan",
            "transmitter_entity_ids": ["infrared.bedroom"],
            "receiver_entity_ids": [],
            "command_count": 1,
        }


class TestRegistryShape:
    def test_every_handler_is_registered(self) -> None:
        from custom_components.rune.websocket_api import _HANDLERS

        expected = {
            "list",
            "device/get",
            "device/create",
            "device/delete",
            "transmitter/list",
            "receiver/list",
        }
        assert set(_HANDLERS.keys()) == expected
