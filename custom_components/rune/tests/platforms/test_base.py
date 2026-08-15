"""Tests for the RunePlatformBase mixin."""
from __future__ import annotations

import pytest

from custom_components.rune._platform_support._base import RunePlatformBase
from custom_components.rune.domain.enums import EntityCategory
from custom_components.rune.domain.models import RuneDevice


def _device(
    *, device_id: str = "dev-1", name: str = "Test", with_pulse: str | None = "off"
) -> RuneDevice:
    from custom_components.rune.domain.enums import CommandCategory, SignalCategory
    from custom_components.rune.domain.models import PulseCommand, PulsePayload

    commands: dict[str, PulseCommand] = {}
    if with_pulse is not None:
        commands[with_pulse] = PulseCommand(
            key=with_pulse,
            label=with_pulse,
            category=CommandCategory.POWER,
            signal_category=SignalCategory.default_ir(),
            payload=PulsePayload(raw_timings=(9000, -4500)),
        )
    return RuneDevice(
        id=device_id,
        name=name,
        category=EntityCategory.FAN,
        manufacturer="Acme",
        model="FRM97",
        commands=commands,
    )


class _Entity(RunePlatformBase):
    """Concrete subclass to exercise the mixin."""

    @property
    def name(self) -> str:
        return self._device.name


class _Coordinator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def async_send_command(self, *, device, command) -> None:
        self.calls.append((device.id, command.key))


class TestRunePlatformBase:
    def setup_method(self) -> None:
        self.coord = _Coordinator()
        self.device = _device()
        self.entity = _Entity(
            device=self.device, coordinator=self.coord, sub_role="speed_2"
        )

    def test_basic_properties(self) -> None:
        assert self.entity.device is self.device
        assert self.entity.sub_role == "speed_2"
        assert self.entity.unique_id_suffix == "speed_2"

    def test_unique_id_suffix_default(self) -> None:
        e = _Entity(device=self.device, coordinator=self.coord)
        assert e.unique_id_suffix == "primary"

    def test_device_info(self) -> None:
        info = self.entity.device_info()
        assert info["identifiers"] == {("rune", "dev-1")}
        assert info["manufacturer"] == "Acme"
        assert info["model"] == "FRM97"

    def test_device_info_extra_can_override(self) -> None:
        class _CustomEntity(_Entity):
            def device_info_extra(self) -> dict:
                return {"via_device": ("hue", "bridge-1")}

        e = _CustomEntity(device=self.device, coordinator=self.coord)
        info = e.device_info()
        assert info["via_device"] == ("hue", "bridge-1")

    @pytest.mark.asyncio
    async def test_async_send_pulse_dispatches(self) -> None:
        await self.entity.async_send_pulse("off")
        assert self.coord.calls == [("dev-1", "off")]

    @pytest.mark.asyncio
    async def test_async_send_pulse_missing_raises(self) -> None:
        with pytest.raises(Exception):
            await self.entity.async_send_pulse("nonexistent")
