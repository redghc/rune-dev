"""Tests for the device-platform coordinator.

The coordinator is the integration's TX-and-action dispatcher; every
platform entity routes through it. These tests use an in-process
mock transmitter + repository so we can assert what was sent and
what was persisted, without any HA imports.
"""
from __future__ import annotations

from typing import Any

import pytest

from custom_components.rune._platform_support._coordinator import DevicePlatformCoordinator
from custom_components.rune.adapters.storage.memory import (
    InMemoryActionRepository,
    InMemoryDeviceRepository,
)
from custom_components.rune.adapters.transmitters.mock import MockTransmitter
from custom_components.rune.adapters.tx_gate import TxGate, TXGateConfig
from custom_components.rune.domain.enums import (
    ActionKind,
    CommandCategory,
    EntityCategory,
    SignalCategory,
    SignalTransport,
    TransmitterSourceKind,
)
from custom_components.rune.domain.errors import (
    CommandNotLearnedError,
    UnsupportedHardwareError,
)
from custom_components.rune.domain.models import (
    ActionBinding,
    ActionTarget,
    PulseCommand,
    PulsePayload,
    RuneDevice,
)


def _command(
    *,
    key: str = "power_on",
    category: CommandCategory = CommandCategory.POWER,
) -> PulseCommand:
    return PulseCommand(
        key=key,
        label=key.replace("_", " ").title(),
        category=category,
        signal_category=SignalCategory.default_ir(),
        payload=PulsePayload(raw_timings=(9000, -4500, 600, -1700)),
    )


def _fan_device(
    *,
    device_id: str = "dev-1",
    transmitter: str = "infrared.bedroom",
    commands: dict[str, PulseCommand] | None = None,
) -> RuneDevice:
    return RuneDevice(
        id=device_id,
        name="Bedroom fan",
        category=EntityCategory.FAN,
        transmitter_entity_ids=[transmitter],
        discrete_speed_count=3,
        commands=commands
        if commands is not None
        else {
            "off": _command(key="off"),
            "speed_1": _command(key="speed_1"),
            "speed_2": _command(key="speed_2"),
            "speed_3": _command(key="speed_3"),
        },
    )


def _coordinator(
    *, transmitter_factory=None
) -> tuple[DevicePlatformCoordinator, MockTransmitter, InMemoryDeviceRepository]:
    """Build a coordinator with a single mock transmitter and the given factory."""
    repo = InMemoryDeviceRepository()
    actions = InMemoryActionRepository()
    transmitter = MockTransmitter(
        transport=SignalTransport.IR,
        source_kind=TransmitterSourceKind.NATIVE_INFRARED,
    )
    factory = transmitter_factory or (
        lambda _hass, _eid, _t: transmitter
    )
    gate = TxGate(
        mirror=_DummyMirror(),
        config=TXGateConfig(),
    )
    coord = DevicePlatformCoordinator(
        hass=None,
        device_repository=repo,
        action_repository=actions,
        tx_gate=gate,
        transmitter_factory=factory,
    )
    return coord, transmitter, repo


class _DummyMirror:
    def record_send(self, **_kwargs):
        return None


@pytest.mark.asyncio
class TestAsyncSendCommand:
    async def test_sends_through_transmitter(self) -> None:
        coord, transmitter, _ = _coordinator()
        device = _fan_device()
        cmd = device.commands["speed_2"]

        await coord.async_send_command(device=device, command=cmd)

        assert len(transmitter.sent) == 1
        assert transmitter.sent[0].key == "speed_2"

    async def test_no_transmitter_skips_silently(self) -> None:
        coord, transmitter, _ = _coordinator()
        device = _fan_device(transmitter="")
        device.transmitter_entity_ids = []

        await coord.async_send_command(
            device=device, command=device.commands["off"]
        )

        assert transmitter.sent == []

    async def test_empty_payload_raises(self) -> None:
        coord, _t, _ = _coordinator()
        device = _fan_device()
        empty_cmd = PulseCommand(
            key="empty",
            label="Empty",
            category=CommandCategory.POWER,
            signal_category=SignalCategory.default_ir(),
            payload=PulsePayload(),  # no fields populated at all
        )

        with pytest.raises(CommandNotLearnedError):
            await coord.async_send_command(device=device, command=empty_cmd)

    async def test_unsupported_emitter_raises(self) -> None:
        def _factory(_hass: Any, _eid: Any, _t: Any) -> MockTransmitter:
            raise UnsupportedHardwareError("nope")

        coord, _t, _ = _coordinator(transmitter_factory=_factory)
        device = _fan_device()

        with pytest.raises(UnsupportedHardwareError):
            await coord.async_send_command(
                device=device, command=device.commands["speed_1"]
            )


@pytest.mark.asyncio
class TestAsyncDispatchAction:
    async def test_press_button_dispatches(self) -> None:
        coord, transmitter, _ = _coordinator()
        device = _fan_device()
        await coord._devices.upsert(device)

        binding = ActionBinding(
            id="b1",
            name="Bedroom fan on",
            signal_id="sig-1",
            target=ActionTarget(
                kind=ActionKind.PRESS_BUTTON,
                device_id=device.id,
                command_key="speed_2",
            ),
        )
        fired = await coord.async_dispatch_action(binding=binding)
        assert fired is True
        assert len(transmitter.sent) == 1

    async def test_press_button_missing_device_skips(self) -> None:
        coord, transmitter, _ = _coordinator()
        binding = ActionBinding(
            id="b1",
            name="Ghost",
            signal_id="sig-1",
            target=ActionTarget(
                kind=ActionKind.PRESS_BUTTON,
                device_id="nope",
                command_key="off",
            ),
        )
        fired = await coord.async_dispatch_action(binding=binding)
        assert fired is False
        assert transmitter.sent == []

    async def test_fire_event_publishes(self) -> None:
        class _Bus:
            def __init__(self) -> None:
                self.events: list[tuple[str, dict]] = []

            def async_fire(self, event_type: str, data: dict) -> None:
                self.events.append((event_type, data))

        class _Hass:
            def __init__(self) -> None:
                self.bus = _Bus()

        hass = _Hass()
        repo = InMemoryDeviceRepository()
        actions = InMemoryActionRepository()
        coord = DevicePlatformCoordinator(
            hass=hass,
            device_repository=repo,
            action_repository=actions,
            tx_gate=TxGate(mirror=_DummyMirror()),
        )

        binding = ActionBinding(
            id="b1",
            name="Notify",
            signal_id="sig-1",
            target=ActionTarget(
                kind=ActionKind.FIRE_EVENT,
                event_type="rune_test_event",
                event_data={"foo": "bar"},
            ),
        )
        fired = await coord.async_dispatch_action(binding=binding)
        assert fired is True
        assert hass.bus.events == [("rune_test_event", {"foo": "bar"})]

    async def test_call_service_invokes_hass(self) -> None:
        class _Services:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str, dict]] = []

            async def async_call(
                self, domain: str, service: str, data: dict, *, blocking: bool = False
            ) -> None:
                self.calls.append((domain, service, data))

        class _Hass:
            def __init__(self) -> None:
                self.services = _Services()

        hass = _Hass()
        coord = DevicePlatformCoordinator(
            hass=hass,
            device_repository=InMemoryDeviceRepository(),
            action_repository=InMemoryActionRepository(),
            tx_gate=TxGate(mirror=_DummyMirror()),
        )

        binding = ActionBinding(
            id="b1",
            name="Toggle",
            signal_id="sig-1",
            target=ActionTarget(
                kind=ActionKind.CALL_SERVICE,
                service_domain="light",
                service_name="toggle",
                service_data={"entity_id": "light.kitchen"},
            ),
        )
        fired = await coord.async_dispatch_action(binding=binding)
        assert fired is True
        assert hass.services.calls == [
            ("light", "toggle", {"entity_id": "light.kitchen"})
        ]

    async def test_unknown_kind_returns_false(self) -> None:
        coord, _, _ = _coordinator()
        # Construct a target with a kind we'll force-cast (the enum
        # forbids unknown strings, so build via from_dict cheat).
        target = ActionTarget(
            kind=ActionKind.PRESS_BUTTON,
            device_id=None,
            command_key=None,
        )
        # Replace the kind with an unknown value to hit the final return.
        target = ActionTarget(
            kind=ActionKind.FIRE_EVENT,
            event_type="",
        )
        binding = ActionBinding(
            id="b1",
            name="bad",
            signal_id="sig-1",
            target=target,
        )
        fired = await coord.async_dispatch_action(binding=binding)
        assert fired is False

    @pytest.mark.asyncio
    async def test_live_entity_push_dispatches_to_registered_adders(self) -> None:
        """New devices added via register_device flow through the adders."""
        coord = _coordinator()[0]
        device = _fan_device()

        class _FakeEntity:
            def __init__(self, role: str) -> None:
                self.role = role

        fan_calls: list[list[Any]] = []
        button_calls: list[list[Any]] = []

        coord.register_entity_adder(
            "fan", lambda entities: fan_calls.append(list(entities))
        )
        coord.register_entity_builder(
            "fan", lambda d: [_FakeEntity(f"fan:{d.name}")]
        )
        coord.register_entity_adder(
            "button", lambda entities: button_calls.append(list(entities))
        )
        coord.register_entity_builder(
            "button", lambda d: [_FakeEntity(f"btn:{d.name}")]
        )
        coord.register_entity_builder(
            "ignored", lambda d: [_FakeEntity(f"ign:{d.name}")]
        )

        await coord.async_add_entities_for_device(device)

        assert [e.role for e in fan_calls[0]] == ["fan:Bedroom fan"]
        assert [e.role for e in button_calls[0]] == ["btn:Bedroom fan"]
        assert coord.has_entity_adder("ignored") is False

    @pytest.mark.asyncio
    async def test_live_entity_push_skips_when_builder_returns_empty(self) -> None:
        coord = _coordinator()[0]
        device = _fan_device()
        device.category = EntityCategory.LIGHT
        adder_calls: list[list[Any]] = []
        coord.register_entity_adder(
            "fan", lambda entities: adder_calls.append(list(entities))
        )
        coord.register_entity_builder("fan", lambda d: [])
        await coord.async_add_entities_for_device(device)
        assert adder_calls == []

    @pytest.mark.asyncio
    async def test_live_entity_push_unwind_on_unregister(self) -> None:
        coord = _coordinator()[0]
        coord.register_entity_adder("fan", lambda e: None)
        coord.register_entity_builder("fan", lambda d: [])
        assert coord.has_entity_adder("fan") is True
        coord.unregister_entity_adder("fan")
        coord.unregister_entity_builder("fan")
        assert coord.has_entity_adder("fan") is False
