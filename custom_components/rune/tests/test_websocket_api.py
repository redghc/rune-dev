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
)
from custom_components.rune.domain.models import (
    PulseCommand,
    PulsePayload,
    RuneDevice,
)
from custom_components.rune.websocket_api import RuneWebSocketContext


class FakeHass:
    """Stand-in hass with a state registry."""

    def __init__(
        self,
        states: list[tuple[str, str] | tuple[str, str, str]] | None = None,
    ) -> None:
        self._states = states or []

        class _States:
            def __init__(self, outer: FakeHass) -> None:
                self._outer = outer

            def async_all(self):
                res = []
                for item in self._outer._states:
                    if len(item) == 3:
                        res.append(_FakeState(item[0], item[1], item[2]))  # type: ignore[arg-type]
                    else:
                        res.append(_FakeState(item[0], item[1]))
                return res

        self.states = _States(self)


class _FakeState:
    def __init__(
        self, entity_id: str, state: str, name: str | None = None
    ) -> None:
        self.entity_id = entity_id
        self.state = state
        self.name = name or entity_id


class _FakeRegEntry:
    def __init__(
        self,
        entity_id: str,
        area_id: str | None = None,
        device_id: str | None = None,
    ) -> None:
        self.entity_id = entity_id
        self.area_id = area_id
        self.device_id = device_id


class _FakeDeviceEntry:
    def __init__(
        self,
        device_id: str,
        name: str | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        area_id: str | None = None,
    ) -> None:
        self.id = device_id
        self.name = name
        self.manufacturer = manufacturer
        self.model = model
        self.area_id = area_id


class _FakeAreaEntry:
    def __init__(self, area_id: str, name: str) -> None:
        self.id = area_id
        self.name = name


class FakeHassWithRegistries(FakeHass):
    """Fake hass that also exposes entity/area/device registries."""

    def __init__(
        self,
        states: list[tuple[str, str] | tuple[str, str, str]],
        entities: list[_FakeRegEntry] | None = None,
        areas: list[_FakeAreaEntry] | None = None,
        devices: list[_FakeDeviceEntry] | None = None,
    ) -> None:
        super().__init__(states)
        import types as _types

        entity_map = {e.entity_id: e for e in (entities or [])}
        area_map = {a.id: a for a in (areas or [])}
        device_map = {d.id: d for d in (devices or [])}
        self.helpers = _types.SimpleNamespace(
            entity_registry=_types.SimpleNamespace(
                async_get=lambda _h, m=entity_map: _types.SimpleNamespace(entities=m)
            ),
            area_registry=_types.SimpleNamespace(
                async_get=lambda _h, m=area_map: _types.SimpleNamespace(areas=m)
            ),
            device_registry=_types.SimpleNamespace(
                async_get=lambda _h, m=device_map: _types.SimpleNamespace(devices=m)
            ),
        )


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
    async def test_creates_device(self) -> None:
        from custom_components.rune.websocket_api import _ws_device_create

        repo = InMemoryDeviceRepository()

        async def _list_repo(self) -> InMemoryDeviceRepository:  # type: ignore[no-untyped-def]
            return repo

        original = RuneWebSocketContext.device_repository
        RuneWebSocketContext.device_repository = _list_repo  # type: ignore[method-assign]
        try:
            result = await _ws_device_create(
                _ctx(),
                {
                    "name": "Bedroom fan",
                    "category": "fan",
                    "transmitter": "infrared.bedroom",
                },
            )
        finally:
            RuneWebSocketContext.device_repository = original  # type: ignore[method-assign]
        assert "device" in result
        assert result["device"]["name"] == "Bedroom fan"
        assert result["device"]["category"] == "fan"
        devices = await repo.load()
        assert len(devices) == 1
        assert devices[0].transmitter_entity_ids == ["infrared.bedroom"]

    async def test_creates_device_with_ir_and_rf_transmitters_and_receivers(self) -> None:
        from custom_components.rune.websocket_api import _ws_device_create

        repo = InMemoryDeviceRepository()

        async def _list_repo(self) -> InMemoryDeviceRepository:  # type: ignore[no-untyped-def]
            return repo

        original = RuneWebSocketContext.device_repository
        RuneWebSocketContext.device_repository = _list_repo  # type: ignore[method-assign]
        try:
            result = await _ws_device_create(
                _ctx(),
                {
                    "name": "Combo Device",
                    "category": "remote",
                    "ir_transmitter": "infrared.blaster",
                    "rf_transmitter": "remote.broadlink_rf",
                    "ir_receiver": "infrared.receiver",
                    "rf_receiver": "remote.broadlink_rf",
                },
            )
        finally:
            RuneWebSocketContext.device_repository = original  # type: ignore[method-assign]
        assert "device" in result
        devices = await repo.load()
        assert len(devices) == 1
        assert devices[0].transmitter_entity_ids == ["infrared.blaster", "remote.broadlink_rf"]
        assert devices[0].receiver_entity_ids == ["infrared.receiver", "remote.broadlink_rf"]

    async def test_missing_required_fields_raises(self) -> None:
        from custom_components.rune.websocket_api import _ws_device_create

        with pytest.raises(ActionError):
            await _ws_device_create(_ctx(), {})


class TestWsEntityListers:
    @pytest.mark.asyncio
    async def test_transmitter_list_filters_domains(self) -> None:
        from custom_components.rune.websocket_api import _ws_transmitter_list

        hass = FakeHass(
            states=[
                ("infrared.bedroom", "idle", "Bedroom IR Blaster"),
                ("remote.broadlink", "idle", "Broadlink RM4 Pro"),
                ("light.kitchen", "on", "Kitchen Light"),  # not an emitter
                ("esphome.living_room", "off", "Living Room Node"),
            ]
        )
        ctx = RuneWebSocketContext(hass=hass, connection_id=None)
        result = await _ws_transmitter_list(ctx, {})
        ids = {entry["entity_id"] for entry in result["transmitters"]}
        names = {entry["name"] for entry in result["transmitters"]}
        assert ids == {"infrared.bedroom", "remote.broadlink", "esphome.living_room"}
        assert names == {"Bedroom IR Blaster", "Broadlink RM4 Pro", "Living Room Node"}

    @pytest.mark.asyncio
    async def test_receiver_list_filters_domains(self) -> None:
        from custom_components.rune.websocket_api import _ws_receiver_list

        hass = FakeHass(
            states=[
                ("infrared.bedroom_rx", "idle", "Bedroom IR Receiver"),
                ("remote.broadlink_rf_rx", "idle", "Broadlink RF Receiver"),
                ("light.kitchen", "on", "Kitchen Light"),
                ("esphome.living_room_rx", "off", "Living Room RX"),
            ]
        )
        ctx = RuneWebSocketContext(hass=hass, connection_id=None)
        result = await _ws_receiver_list(ctx, {})
        ids = {entry["entity_id"] for entry in result["receivers"]}
        names = {entry["name"] for entry in result["receivers"]}
        assert ids == {"infrared.bedroom_rx", "remote.broadlink_rf_rx", "esphome.living_room_rx"}
        assert names == {"Bedroom IR Receiver", "Broadlink RF Receiver", "Living Room RX"}

    @pytest.mark.asyncio
    async def test_transmitter_list_resolves_area_and_device_name(self) -> None:
        """Each transmitter row should carry the entity's area name
        (from the HA area registry) and the parent device's friendly
        name (from the HA device registry).

        Area resolution mirrors the HA UI: an entity's own ``area_id``
        wins; otherwise the entity inherits the area from the device
        it belongs to. Missing links surface as empty strings — never
        as fabricated values.
        """
        from custom_components.rune.websocket_api import _ws_transmitter_list

        hass = FakeHassWithRegistries(
            states=[
                ("remote.salon_tv", "idle", "Salon TV"),
                ("remote.bedroom_tv", "idle", "Bedroom TV"),
                ("remote.inherited", "idle", "Inherited Area"),
                ("remote.loose", "idle", "Loose Entity"),
            ],
            entities=[
                _FakeRegEntry("remote.salon_tv", area_id="a-salon", device_id="d-rm4"),
                _FakeRegEntry("remote.bedroom_tv", area_id=None, device_id="d-bed-tv"),
                _FakeRegEntry("remote.inherited", area_id=None, device_id="d-rm4"),
                _FakeRegEntry("remote.loose", area_id=None, device_id="d-loose"),
            ],
            areas=[
                _FakeAreaEntry("a-salon", "Salon"),
                _FakeAreaEntry("a-bed", "Bedroom"),
            ],
            devices=[
                _FakeDeviceEntry("d-rm4", name="RM4 Pro", area_id="a-salon"),
                _FakeDeviceEntry("d-bed-tv", name="Bedroom TV", area_id="a-bed"),
                _FakeDeviceEntry("d-loose", name="Loose Device"),
            ],
        )
        ctx = RuneWebSocketContext(hass=hass, connection_id=None)
        result = await _ws_transmitter_list(ctx, {})
        by_id = {e["entity_id"]: e for e in result["transmitters"]}

        assert by_id["remote.salon_tv"]["area"] == "Salon"
        assert by_id["remote.salon_tv"]["device_name"] == "RM4 Pro"

        assert by_id["remote.bedroom_tv"]["area"] == "Bedroom"
        assert by_id["remote.bedroom_tv"]["device_name"] == "Bedroom TV"

        assert by_id["remote.inherited"]["area"] == "Salon"
        assert by_id["remote.inherited"]["device_name"] == "RM4 Pro"

        assert by_id["remote.loose"]["area"] == ""
        assert by_id["remote.loose"]["device_name"] == "Loose Device"


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
            "device/update",
            "device/delete",
            "command/learn",
            "sniffer/list",
            "sniffer/dismiss",
            "action/list",
            "transmitter/list",
            "receiver/list",
        }
        assert set(_HANDLERS.keys()) == expected
