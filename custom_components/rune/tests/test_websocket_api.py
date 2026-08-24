"""Tests for the WebSocket API command handlers.

The WS API has a thin decorator-based registry. Each handler is a
pure function from ``(ctx, msg) → payload``. These tests exercise the
handlers directly with a fake ``RuneWebSocketContext`` and an
in-memory repository.
"""
from __future__ import annotations

import sys
from typing import Any

import pytest

from custom_components.rune.adapters.storage.memory import (
    InMemoryActionRepository,
    InMemoryDeviceRepository,
)
from custom_components.rune.const import DOMAIN
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
        # ``hass.data`` is read by several WS-layer helpers — provide
        # a real dict so tests can stash per-fixture data (e.g. the
        # ``infrared_receivers`` set the IR probe reads).
        self.data: dict[str, object] = {}

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
        # Production code imports the registry modules directly (not via
        # hass.helpers). Mirror that by also exposing a callable on the
        # module path that ``from homeassistant.helpers import X as x``
        # resolves against.
        self._inject_ha_modules(entity_map, area_map, device_map)

    @staticmethod
    def _inject_ha_modules(
        entity_map: dict, area_map: dict, device_map: dict
    ) -> None:
        import sys
        import types as _types

        if "homeassistant" not in sys.modules:
            sys.modules["homeassistant"] = _types.ModuleType("homeassistant")
        if "homeassistant.helpers" not in sys.modules:
            sys.modules["homeassistant.helpers"] = _types.ModuleType(
                "homeassistant.helpers"
            )
        er = _types.ModuleType("homeassistant.helpers.entity_registry")
        ar = _types.ModuleType("homeassistant.helpers.area_registry")
        dr = _types.ModuleType("homeassistant.helpers.device_registry")
        er.async_get = lambda _h, m=entity_map: _types.SimpleNamespace(entities=m)
        ar.async_get = lambda _h, m=area_map: _types.SimpleNamespace(areas=m)
        dr.async_get = lambda _h, m=device_map: _types.SimpleNamespace(devices=m)
        sys.modules["homeassistant.helpers.entity_registry"] = er
        sys.modules["homeassistant.helpers.area_registry"] = ar
        sys.modules["homeassistant.helpers.device_registry"] = dr


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

    async def test_create_pushes_entities_through_coordinator(self) -> None:
        """Newly created devices are pushed to live entity adders.

        The WS handler must call ``coordinator.async_add_entities_for_device``
        so platforms registered via the runtime hook see the new device
        without a full reload.
        """
        from custom_components.rune._platform_support._coordinator import (
            DevicePlatformCoordinator,
        )
        from custom_components.rune.websocket_api import _ws_device_create

        repo = InMemoryDeviceRepository()

        async def _list_repo(self) -> InMemoryDeviceRepository:  # type: ignore[no-untyped-def]
            return repo

        coord = DevicePlatformCoordinator(
            hass=FakeHass(),
            device_repository=repo,
            action_repository=InMemoryActionRepository(),
            tx_gate=type(
                "_G", (), {"send": staticmethod(lambda *_a, **_kw: None)}
            )(),
        )

        class _FakeEntity:
            def __init__(self, role: str) -> None:
                self.role = role

        seen: list[list[Any]] = []
        coord.register_entity_adder(
            "fan", lambda entities: seen.append(list(entities))
        )
        coord.register_entity_builder(
            "fan",
            lambda d: [_FakeEntity("fan:" + d.name)]
            if d.category.value == "fan"
            else [],
        )

        # Stand in for the live hass with the coordinator registered on
        # the per-entry dict the WS context walks.
        hass = FakeHass()
        hass.data = {DOMAIN: {"entry-1": {"coordinator": coord}}}

        original_repo = RuneWebSocketContext.device_repository
        RuneWebSocketContext.device_repository = _list_repo  # type: ignore[method-assign]
        try:
            result = await _ws_device_create(
                RuneWebSocketContext(hass=hass, connection_id=None),
                {
                    "name": "Bedroom fan",
                    "category": "fan",
                    "transmitter": "infrared.bedroom",
                },
            )
        finally:
            RuneWebSocketContext.device_repository = original_repo  # type: ignore[method-assign]

        assert result["device"]["name"] == "Bedroom fan"
        assert len(seen) == 1
        assert [e.role for e in seen[0]] == ["fan:Bedroom fan"]


class TestMergeCommands:
    def test_empty_incoming_returns_existing_copy(self) -> None:
        from custom_components.rune.domain.enums import (
            CommandCategory,
            SignalCategory,
        )
        from custom_components.rune.domain.models import (
            PulseCommand,
            PulsePayload,
        )
        from custom_components.rune.websocket_api import _merge_commands

        existing = {
            "off": PulseCommand(
                key="off",
                label="Off",
                category=CommandCategory.POWER,
                signal_category=SignalCategory.default_ir(),
                payload=PulsePayload(raw_timings=(9000, -4500)),
            ),
        }
        merged = _merge_commands(existing, None)
        assert set(merged) == {"off"}
        # The original dict is left alone — we hand back a fresh copy so
        # the caller can mutate without surprising other readers.
        assert merged is not existing

    def test_incoming_overwrites_matching_keys(self) -> None:
        from custom_components.rune.domain.enums import (
            CommandCategory,
            SignalCategory,
        )
        from custom_components.rune.domain.models import (
            PulseCommand,
            PulsePayload,
        )
        from custom_components.rune.websocket_api import _merge_commands

        existing = {
            "off": PulseCommand(
                key="off",
                label="Off",
                category=CommandCategory.POWER,
                signal_category=SignalCategory.default_ir(),
                payload=PulsePayload(raw_timings=(9000, -4500)),
            ),
        }
        merged = _merge_commands(
            existing,
            {
                "off": {
                    "label": "Power Off",
                    "category": "power",
                    "payload": {"raw_timings": [1000, -500]},
                },
            },
        )
        assert set(merged) == {"off"}
        assert merged["off"].label == "Power Off"
        assert merged["off"].payload.raw_timings == (1000, -500)

    def test_incoming_adds_new_keys(self) -> None:
        from custom_components.rune.websocket_api import _merge_commands

        existing: dict[str, PulseCommand] = {}
        merged = _merge_commands(
            existing,
            {
                "speed_1": {
                    "label": "Speed 1",
                    "payload": {"raw_timings": [350, -650]},
                },
            },
        )
        assert set(merged) == {"speed_1"}
        assert merged["speed_1"].key == "speed_1"
        assert merged["speed_1"].label == "Speed 1"

    def test_non_dict_incoming_raises(self) -> None:
        from custom_components.rune.domain.errors import ActionError
        from custom_components.rune.websocket_api import _merge_commands

        with pytest.raises(ActionError):
            _merge_commands({}, ["not", "a", "dict"])

    def test_non_dict_payload_raises(self) -> None:
        from custom_components.rune.domain.errors import ActionError
        from custom_components.rune.websocket_api import _merge_commands

        with pytest.raises(ActionError):
            _merge_commands({}, {"speed_1": "raw"})


class TestWsDeviceUpdateCommands:
    """Confirm ``rune/device/update`` accepts an incoming ``commands`` map.

    The Learn dialog sends ``{device_id, commands}`` after capturing a
    pulse. Without this merge, learned commands vanish into the void
    because the handler otherwise preserves ``device.commands`` verbatim.
    """

    @pytest.mark.asyncio
    async def test_update_persists_incoming_commands(self) -> None:
        from custom_components.rune.websocket_api import _ws_device_update

        repo = InMemoryDeviceRepository()
        device = RuneDevice(
            id="d1",
            name="Bedroom fan",
            category=EntityCategory.FAN,
            transmitter_entity_ids=["infrared.bedroom"],
        )
        await repo.upsert(device)

        async def _list_repo(self) -> InMemoryDeviceRepository:  # type: ignore[no-untyped-def]
            return repo

        hass = FakeHass()
        # Pre-seed the hass.data with an entry so device_registry.upsert
        # inside the handler can resolve a config_entry_id. We don't
        # actually need the coordinator to exist here.
        hass.data = {DOMAIN: {"entry-1": {}}}

        original = RuneWebSocketContext.device_repository
        RuneWebSocketContext.device_repository = _list_repo  # type: ignore[method-assign]
        try:
            result = await _ws_device_update(
                RuneWebSocketContext(hass=hass, connection_id=None),
                {
                    "device_id": "d1",
                    "commands": {
                        "off": {
                            "label": "Off",
                            "category": "power",
                            "payload": {"raw_timings": [9000, -4500]},
                        },
                        "speed_1": {
                            "label": "Speed 1",
                            "payload": {"raw_timings": [350, -650]},
                        },
                    },
                },
            )
        finally:
            RuneWebSocketContext.device_repository = original  # type: ignore[method-assign]

        assert set(result["device"]["commands"]) == {"off", "speed_1"}
        persisted = await repo.get("d1")
        assert persisted is not None
        assert set(persisted.commands) == {"off", "speed_1"}


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
        device.manufacturer = "Vonluce"
        device.model = "CFN1318BW"
        device.discrete_speed_count = 6
        summary = _device_summary(device)
        assert summary == {
            "id": "d1",
            "name": "My fan",
            "category": "fan",
            "manufacturer": "Vonluce",
            "model": "CFN1318BW",
            "discrete_speed_count": 6,
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
            "debug/registry-check",
        }
        assert set(_HANDLERS.keys()) == expected


class TestCallbackErrorEnvelope:
    """Regression: HA's ``error_message`` signature is
    ``(msg_id, code, message, ...)`` — the human text goes in
    ``message``, not ``code``. The earlier wrapper packed the
    exception text into ``code`` and left ``message`` at the HA
    default ``"Unknown error"``, so every backend failure looked
    identical in the panel."""

    @pytest.mark.asyncio
    async def test_handler_exception_surfaces_message_not_unknown_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pre-seed ``homeassistant.components.websocket_api`` so the
        # ``from homeassistant.components import websocket_api`` inside
        # ``async_register_websocket_commands`` resolves to our stub
        # without touching the real HA install.
        fake = _make_fake_websocket_api(monkeypatch)

        sent: list[dict[str, Any]] = []

        class _FakeConnection:
            def send_message(self, payload: dict[str, Any]) -> None:
                sent.append(payload)

        class _FakeHass:
            pass

        # Register a one-shot handler that raises so we can verify
        # the wrapper sends a readable ``message`` field.
        from custom_components.rune.websocket_api import (
            _HANDLERS,
            _register,
            async_register_websocket_commands,
        )

        @_register("__test_raises__")
        async def _boom(ctx: Any, msg: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("Capture failed: receiver offline")

        try:
            await async_register_websocket_commands(_FakeHass())
            callback = fake.registered["rune/__test_raises__"]["handler"]
            await callback(
                _FakeHass(),
                _FakeConnection(),
                {"id": 7, "type": "rune/__test_raises__"},
            )
        finally:
            _HANDLERS.pop("__test_raises__", None)

        assert len(sent) == 1, sent
        envelope = sent[0]
        assert envelope["success"] is False
        err = envelope["error"]
        assert err["code"] == "unknown_error", err
        assert "RuntimeError" in err["message"], err
        assert "receiver offline" in err["message"], err


def _make_fake_websocket_api(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Build a stub ``homeassistant.components.websocket_api`` that
    captures every registered callback so the test can invoke them
    directly without a real HA install."""
    import types

    # ``from homeassistant.components import websocket_api`` walks the
    # parent package first, so seed ``homeassistant`` and
    # ``homeassistant.components`` as empty modules before the target.
    for name in ("homeassistant", "homeassistant.components"):
        if name not in sys.modules:
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))

    mod = types.ModuleType("homeassistant.components.websocket_api")
    mod.registered: dict[str, dict[str, Any]] = {}

    def async_register_command(
        hass: Any, command: str, handler: Any, schema: Any = None
    ) -> None:
        mod.registered[command] = {"handler": handler, "schema": schema}

    def async_response(func: Any) -> Any:
        return func

    def error_message(
        msg_id: int,
        code: Any = "unknown_error",
        message: str | None = None,
        **kw: Any,
    ) -> dict[str, Any]:
        # Mirror HA's default: ``message`` falls back to
        # ``"Unknown error"`` when not supplied.
        return {
            "id": msg_id,
            "type": "result",
            "success": False,
            "error": {
                "code": code,
                "message": message if message is not None else "Unknown error",
                **{k: v for k, v in kw.items() if v is not None},
            },
        }

    def result_message(msg_id: int, payload: Any) -> dict[str, Any]:
        return {"id": msg_id, "type": "result", "success": True, "result": payload}

    mod.async_register_command = async_register_command
    mod.async_response = async_response
    mod.error_message = error_message
    mod.result_message = result_message
    monkeypatch.setitem(sys.modules, "homeassistant.components.websocket_api", mod)
    return mod


class TestWsCommandLearn:
    """``rune/command/learn`` now requires the SPA to pick both the
    transport (IR/RF) and the receiver entity. Each branch of the
    handler is locked in here so we don't regress the user-facing
    error messages we worked so hard to make actionable."""

    @pytest.mark.asyncio
    async def test_missing_transport_raises_action_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from custom_components.rune.domain.errors import ActionError
        from custom_components.rune.websocket_api import _ws_command_learn

        hass = FakeHass(states=[("infrared.rx", "idle")])
        ctx = RuneWebSocketContext(hass=hass, connection_id=None)
        msg = {
            "id": 1,
            "device_id": "dev-1",
            "command_key": "off",
            # transport intentionally missing
            "receiver_entity_id": "infrared.rx",
        }
        # Stub the device repo so we get past the early check.
        repo = self._stub_device_repo(monkeypatch, devices=[])
        ctx.device_repository = lambda: _async(lambda: repo)  # type: ignore[method-assign]
        with pytest.raises(ActionError, match="transport"):
            await _ws_command_learn(ctx, msg)

    @pytest.mark.asyncio
    async def test_missing_receiver_raises_action_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from custom_components.rune.domain.errors import ActionError
        from custom_components.rune.websocket_api import _ws_command_learn

        hass = FakeHass()
        ctx = RuneWebSocketContext(hass=hass, connection_id=None)
        msg = {
            "id": 1,
            "device_id": "dev-1",
            "command_key": "off",
            "transport": "ir",
            # receiver_entity_id intentionally missing
        }
        with pytest.raises(ActionError, match="receiver_entity_id"):
            await _ws_command_learn(ctx, msg)

    @pytest.mark.asyncio
    async def test_rf_receiver_must_be_remote_domain(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from custom_components.rune.domain.errors import (
            CaptureProviderUnavailableError,
        )
        from custom_components.rune.websocket_api import _ws_command_learn

        hass = FakeHass(states=[("infrared.rx", "idle")])
        # Patch the IR probe + the RF provider so the WS handler
        # exercises the domain-validation branch in isolation.
        from custom_components.rune import websocket_api as ws_api

        monkeypatch.setattr(
            ws_api,
            "_is_ir_receiver",
            lambda *_a, **_kw: True,
        )
        from custom_components.rune.adapters.capture import (
            broadlink_rf as brf_mod,
        )

        monkeypatch.setattr(
            brf_mod.BroadlinkRFCaptureProvider,
            "is_available",
            property(lambda _self: True),
        )
        ctx = RuneWebSocketContext(hass=hass, connection_id=None)
        msg = {
            "id": 1,
            "device_id": "dev-1",
            "command_key": "off",
            "transport": "rf",
            "receiver_entity_id": "infrared.rx",  # wrong domain for RF
        }
        with pytest.raises(
            CaptureProviderUnavailableError, match="not an RF receiver"
        ):
            await _ws_command_learn(ctx, msg)

    @staticmethod
    def _stub_device_repo(
        monkeypatch: pytest.MonkeyPatch, devices: list
    ) -> Any:
        """Build a fake ``device_repository`` async factory returning
        a stub repo with ``.get``/``.load`` methods."""

        class _StubRepo:
            def __init__(self, devs: list) -> None:
                self._devs = devs

            async def get(self, device_id: str) -> Any:
                for d in self._devs:
                    if d.id == device_id:
                        return d
                return None

            async def load(self) -> list:
                return list(self._devs)

        return _StubRepo(devices)


async def _async(coro):
    """Tiny helper to build a one-shot awaitable from a coroutine."""
    return await coro


@pytest.fixture
def patched_ir_probes(monkeypatch: pytest.MonkeyPatch):
    """Stub ``_is_ir_receiver`` / ``_list_ir_receivers`` so the WS
    handler's probe runs without HA installed.

    The fake reads from ``hass.data["infrared_receivers"]`` (set of
    entity IDs) — the same shape the production probe uses, so the
    tests mirror the contract faithfully.
    """

    def _is_ir(hass: Any, entity_id: str) -> bool:
        receivers = getattr(hass, "data", {}).get("infrared_receivers", set())
        return entity_id in receivers

    def _list(hass: Any) -> list[str]:
        return sorted(getattr(hass, "data", {}).get("infrared_receivers", set()))

    from custom_components.rune import websocket_api as ws_api

    monkeypatch.setattr(ws_api, "_is_ir_receiver", _is_ir)
    monkeypatch.setattr(ws_api, "_list_ir_receivers", _list)


class TestPickIrReceiver:
    """``_pick_ir_receiver`` is the gate that decides which entity the
    WS learn handler will subscribe to. The choices feed into the
    orchestrator and the SPA's user-facing error messages, so the
    ordering and fallback rules need to be locked in.

    The function now also returns ``alternatives`` — the list of
    entities HA does recognise as receivers — so the WS handler can
    point the user at real options when their configured slot is
    wrong. Tests assert both halves of the tuple."""

    def test_prefers_configured_infrared_entity(
        self, patched_ir_probes: None
    ) -> None:
        from custom_components.rune.websocket_api import _pick_ir_receiver

        # ``infrared.bedroom`` is registered with HA's infrared
        # component; ``remote.broadlink`` is just a state object.
        hass = FakeHass(
            states=[
                ("infrared.bedroom", "idle"),
                ("remote.broadlink", "idle"),
            ]
        )
        hass.data["infrared_receivers"] = {"infrared.bedroom"}
        chosen, alternatives = _pick_ir_receiver(
            hass, ["remote.broadlink", "infrared.bedroom"]
        )
        assert chosen == "infrared.bedroom"
        assert "infrared.bedroom" in alternatives

    def test_falls_back_to_infrared_from_discovery(
        self, patched_ir_probes: None
    ) -> None:
        from custom_components.rune.websocket_api import _pick_ir_receiver

        hass = FakeHass(
            states=[
                ("infrared.bedroom", "idle"),
                ("remote.broadlink", "idle"),
            ]
        )
        hass.data["infrared_receivers"] = {"infrared.bedroom"}
        # Empty ``configured_receivers`` → fall back to HA discovery.
        chosen, alternatives = _pick_ir_receiver(hass, [])
        assert chosen == "infrared.bedroom"
        assert "infrared.bedroom" in alternatives

    def test_returns_none_when_only_rf_receivers(
        self, patched_ir_probes: None
    ) -> None:
        from custom_components.rune.websocket_api import _pick_ir_receiver

        hass = FakeHass(states=[("remote.broadlink_rf_rx", "idle")])
        hass.data["infrared_receivers"] = set()
        chosen, alternatives = _pick_ir_receiver(
            hass, ["remote.broadlink_rf_rx"]
        )
        assert chosen is None
        assert alternatives == []

    def test_returns_none_when_no_receivers_anywhere(
        self, patched_ir_probes: None
    ) -> None:
        from custom_components.rune.websocket_api import _pick_ir_receiver

        hass = FakeHass(states=[("light.kitchen", "on")])
        hass.data["infrared_receivers"] = set()
        chosen, alternatives = _pick_ir_receiver(hass, [])
        assert chosen is None
        assert alternatives == []

    def test_skips_unregistered_infrared_entity(
        self, patched_ir_probes: None
    ) -> None:
        """Entity has the ``infrared.`` domain but HA doesn't list it
        as a registered receiver (e.g. emitter misconfigured in the
        slot). ``_pick_ir_receiver`` must skip it and surface the
        alternatives list so the panel can guide the user."""
        from custom_components.rune.websocket_api import _pick_ir_receiver

        hass = FakeHass(
            states=[
                ("infrared.remoto_emisor_ir", "idle"),  # the wrong one
                ("infrared.bedroom_rx", "idle"),  # the right one
            ]
        )
        hass.data["infrared_receivers"] = {"infrared.bedroom_rx"}
        chosen, alternatives = _pick_ir_receiver(
            hass, ["infrared.remoto_emisor_ir"]
        )
        # We refused the misconfigured entity but found the real one
        # via HA discovery.
        assert chosen == "infrared.bedroom_rx"
        assert "infrared.bedroom_rx" in alternatives
        assert "infrared.remoto_emisor_ir" not in alternatives

    def test_reports_alternatives_even_when_nothing_picked(
        self, patched_ir_probes: None
    ) -> None:
        """When no configured or discoverable entity is a real
        receiver, the function returns ``(None, alternatives)`` so
        the WS handler can list the entities HA does recognise in
        the error message — helping the user fix their slot without
        hunting through the entity registry."""
        from custom_components.rune.websocket_api import _pick_ir_receiver

        # Two entities in the infrared domain but HA reports zero
        # real receivers — the only path the function can take is
        # the "nothing works" branch.
        hass = FakeHass(
            states=[
                ("infrared.wrong_one", "idle"),
                ("infrared.also_wrong", "idle"),
            ]
        )
        hass.data["infrared_receivers"] = set()
        chosen, alternatives = _pick_ir_receiver(hass, ["infrared.wrong_one"])
        assert chosen is None
        assert alternatives == []
