"""Tests for the pulse-button platform."""
from __future__ import annotations

import pytest

from custom_components.rune.domain.enums import (
    CommandCategory,
    EntityCategory,
    SignalCategory,
)
from custom_components.rune.domain.models import (
    PulseCommand,
    PulsePayload,
    RuneDevice,
)
from custom_components.rune.platforms.button import RunePulseButtonEntity


def _command(key: str = "power_on") -> PulseCommand:
    return PulseCommand(
        key=key,
        label=key.replace("_", " ").title(),
        category=CommandCategory.POWER,
        signal_category=SignalCategory.default_ir(),
        payload=PulsePayload(raw_timings=(9000, -4500)),
    )


class _Device:
    def __init__(self, commands: dict[str, PulseCommand]) -> None:
        self.id = "dev-1"
        self.name = "Test"
        self.manufacturer = None
        self.model = None
        self.commands = commands


class _Coordinator:
    def __init__(self) -> None:
        self.calls: list[tuple[object, str]] = []

    async def async_send_command(self, *, device, command) -> None:
        self.calls.append((device, command.key))


class TestRunePulseButtonEntity:
    def setup_method(self) -> None:
        self.coord = _Coordinator()
        self.device = _Device({"power_on": _command()})
        self.entity = RunePulseButtonEntity(
            device=self.device,
            coordinator=self.coord,
            command_key="power_on",
            command_label="Power On",
            command_category=CommandCategory.POWER,
        )

    def test_name_uses_label(self) -> None:
        assert self.entity.name == "Power On"

    def test_name_falls_back_to_key(self) -> None:
        e = RunePulseButtonEntity(
            device=self.device,
            coordinator=self.coord,
            command_key="x",
            command_label="",
            command_category=CommandCategory.CUSTOM,
        )
        assert e.name == "x"

    def test_unique_id(self) -> None:
        assert self.entity.unique_id == "rune_dev-1_primary"

    def test_unique_id_with_sub_role(self) -> None:
        e = RunePulseButtonEntity(
            device=self.device,
            coordinator=self.coord,
            command_key="speed_3",
            command_label="Speed 3",
            command_category=CommandCategory.FAN_SPEED,
            sub_role="speed_3",
        )
        assert e.unique_id == "rune_dev-1_speed_3"

    def test_command_properties(self) -> None:
        assert self.entity.command_key == "power_on"
        assert self.entity.command_label == "Power On"
        assert self.entity.command_category == CommandCategory.POWER

    @pytest.mark.asyncio
    async def test_async_press_dispatches(self) -> None:
        await self.entity.async_press()
        assert len(self.coord.calls) == 1
        assert self.coord.calls[0][1] == "power_on"


class TestButtonPlatformBuilder:
    @pytest.mark.asyncio
    async def test_builds_one_entity_per_command(self) -> None:
        from custom_components.rune.adapters.storage.memory import (
            InMemoryDeviceRepository,
        )
        from custom_components.rune.domain.enums import (
            CommandCategory,
            SignalCategory,
        )
        from custom_components.rune.domain.models import (
            PulseCommand,
            PulsePayload,
        )
        from custom_components.rune.platforms.button import RuneButtonPlatform

        def _make_cmd(key: str) -> PulseCommand:
            return PulseCommand(
                key=key,
                label=key,
                category=CommandCategory.POWER,
                signal_category=SignalCategory.default_ir(),
                payload=PulsePayload(raw_timings=(9000, -4500)),
            )

        device = RuneDevice(
            id="dev-1",
            name="Test",
            category=EntityCategory.CUSTOM,
            commands={"on": _make_cmd("on"), "off": _make_cmd("off")},
        )

        repo = InMemoryDeviceRepository()
        await repo.upsert(device)

        added: list = []

        # ``async_add_entities`` in HA can be sync — it just appends
        # to the internal pending list. Match that here.
        def _add(entities: list) -> None:
            added.extend(entities)

        coord = _Coordinator()
        coord._devices = repo  # type: ignore[attr-defined]
        platform = RuneButtonPlatform(hass=None, coordinator=coord)
        await platform.async_setup_platform(_add)

        assert len(added) == 2
        assert {e.command_key for e in added} == {"on", "off"}
