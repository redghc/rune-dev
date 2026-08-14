"""Tests for the fan platform entity."""
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
from custom_components.rune.platforms.fan import RuneFanEntity


def _command(key: str) -> PulseCommand:
    return PulseCommand(
        key=key,
        label=key,
        category=CommandCategory.FAN_SPEED if "speed" in key else CommandCategory.POWER,
        signal_category=SignalCategory.default_ir(),
        payload=PulsePayload(raw_timings=(9000, -4500)),
    )


def _fan_device(steps: int = 3, has_on: bool = False) -> RuneDevice:
    commands = {
        "off": _command("off"),
        **{f"speed_{i}": _command(f"speed_{i}") for i in range(1, steps + 1)},
    }
    if has_on:
        commands["on"] = _command("on")
    return RuneDevice(
        id="fan-1",
        name="Bedroom fan",
        category=EntityCategory.FAN,
        discrete_speed_count=steps,
        commands=commands,
    )


class _Coordinator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def async_send_command(self, *, device, command) -> None:
        self.calls.append((device.id, command.key))


class TestRuneFanEntity:
    def setup_method(self) -> None:
        self.coord = _Coordinator()
        self.entity = RuneFanEntity(device=_fan_device(), coordinator=self.coord)

    def test_basic_properties(self) -> None:
        assert self.entity.name == "Bedroom fan"
        assert self.entity.unique_id == "rune_fan-1_fan"
        assert self.entity.speed_count == 3
        assert self.entity.is_on is False
        assert self.entity.percentage == 0

    @pytest.mark.asyncio
    async def test_turn_off_sends_off_command(self) -> None:
        await self.entity.async_turn_off()
        assert self.coord.calls == [("fan-1", "off")]
        assert self.entity.is_on is False

    @pytest.mark.asyncio
    async def test_set_percentage_sends_correct_step(self) -> None:
        # 50% on a 3-speed fan (HA convention) maps to step 2.
        await self.entity.async_set_percentage(50)
        assert self.coord.calls == [("fan-1", "speed_2")]
        assert self.entity.is_on is True

    @pytest.mark.asyncio
    async def test_set_percentage_zero_turns_off(self) -> None:
        await self.entity.async_set_percentage(0)
        assert self.coord.calls == [("fan-1", "off")]
        assert self.entity.is_on is False

    @pytest.mark.asyncio
    async def test_set_percentage_100_sends_top_speed(self) -> None:
        await self.entity.async_set_percentage(100)
        assert self.coord.calls == [("fan-1", "speed_3")]

    @pytest.mark.asyncio
    async def test_turn_on_with_percentage(self) -> None:
        # 33% on a 3-speed fan (HA convention) → ceil((33/100)*(3-1)+1) = ceil(1.66) = speed_2.
        await self.entity.async_turn_on(percentage=33)
        assert self.coord.calls == [("fan-1", "speed_2")]

    @pytest.mark.asyncio
    async def test_turn_on_with_on_button(self) -> None:
        entity = RuneFanEntity(device=_fan_device(has_on=True), coordinator=self.coord)
        await entity.async_turn_on()
        assert self.coord.calls == [("fan-1", "on")]
        assert entity.is_on is True

    @pytest.mark.asyncio
    async def test_turn_on_no_on_falls_back_to_step(self) -> None:
        await self.entity.async_turn_on()
        # No 'on' command → first speed step.
        assert self.coord.calls == [("fan-1", "speed_1")]

    @pytest.mark.asyncio
    async def test_missing_speed_step_logs_warning(self) -> None:
        device = _fan_device(steps=3)
        del device.commands["speed_2"]
        entity = RuneFanEntity(device=device, coordinator=self.coord)
        await entity.async_set_percentage(50)
        assert self.coord.calls == []  # nothing sent


class TestFanPlatformBuilder:
    @pytest.mark.asyncio
    async def test_only_fan_devices_emitted(self) -> None:
        from custom_components.rune.adapters.storage.memory import (
            InMemoryDeviceRepository,
        )
        from custom_components.rune.platforms.fan import RuneFanPlatform

        fan = _fan_device()
        light = RuneDevice(
            id="light-1",
            name="Light",
            category=EntityCategory.LIGHT,
            commands={},
        )

        repo = InMemoryDeviceRepository()
        await repo.upsert(fan)
        await repo.upsert(light)

        added: list = []

        def _add(entities: list) -> None:
            added.extend(entities)

        coord = _Coordinator()
        coord._devices = repo  # type: ignore[attr-defined]
        platform = RuneFanPlatform(hass=None, coordinator=coord)
        await platform.async_setup_platform(_add)

        assert len(added) == 1
        assert added[0].device.id == "fan-1"
