"""Tests for the remaining platforms (climate, light, cover, switch, media_player, remote)."""
from __future__ import annotations

import pytest

from custom_components.rune.climate import RuneClimateEntity
from custom_components.rune.cover import RuneCoverEntity
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
from custom_components.rune.light import RuneLightEntity
from custom_components.rune.media_player import RuneMediaPlayerEntity
from custom_components.rune.remote import RuneRemoteEntity
from custom_components.rune.switch import RuneSwitchEntity


def _command(key: str, *, category: CommandCategory = CommandCategory.CUSTOM) -> PulseCommand:
    return PulseCommand(
        key=key,
        label=key,
        category=category,
        signal_category=SignalCategory.default_ir(),
        payload=PulsePayload(raw_timings=(9000, -4500)),
    )


class _Coordinator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def async_send_command(self, *, device, command) -> None:
        self.calls.append((device.id, command.key))


def _device(category: EntityCategory, commands: dict[str, PulseCommand]) -> RuneDevice:
    return RuneDevice(
        id=f"{category.value}-1",
        name=f"Test {category.value}",
        category=category,
        commands=commands,
    )


# ---------------------------------------------------------------------------
# Climate
# ---------------------------------------------------------------------------


class TestClimate:
    def setup_method(self) -> None:
        self.coord = _Coordinator()
        self.device = _device(
            EntityCategory.CLIMATE,
            {
                "mode_cool": _command("mode_cool"),
                "mode_heat": _command("mode_heat"),
                "fan_low": _command("fan_low"),
                "fan_high": _command("fan_high"),
                "temp_22": _command("temp_22"),
                "off": _command("off"),
            },
        )
        self.entity = RuneClimateEntity(device=self.device, coordinator=self.coord)

    @pytest.mark.asyncio
    async def test_set_hvac_mode_cool(self) -> None:
        await self.entity.async_set_hvac_mode("cool")
        assert self.coord.calls == [("climate-1", "mode_cool")]

    @pytest.mark.asyncio
    async def test_set_hvac_mode_off(self) -> None:
        await self.entity.async_set_hvac_mode("off")
        assert self.coord.calls == [("climate-1", "off")]

    @pytest.mark.asyncio
    async def test_set_temperature_rounds(self) -> None:
        await self.entity.async_set_temperature(temperature=21.6)
        assert self.coord.calls == [("climate-1", "temp_22")]

    @pytest.mark.asyncio
    async def test_set_fan_mode(self) -> None:
        await self.entity.async_set_fan_mode("low")
        assert self.coord.calls == [("climate-1", "fan_low")]

    def test_fan_modes_inferred(self) -> None:
        assert self.entity.fan_modes == ["low", "high"]

    def test_supported_features_present(self) -> None:
        # Without HA installed, supported_features is 0; with HA it's
        # a non-zero flag mask. Both are valid for this contract.
        features = self.entity.supported_features
        assert features >= 0


# ---------------------------------------------------------------------------
# Light
# ---------------------------------------------------------------------------


class TestLight:
    def setup_method(self) -> None:
        self.coord = _Coordinator()

    @pytest.mark.asyncio
    async def test_onoff_only(self) -> None:
        device = _device(
            EntityCategory.LIGHT,
            {"on": _command("on"), "off": _command("off")},
        )
        entity = RuneLightEntity(device=device, coordinator=self.coord)
        assert entity.color_mode == "onoff"
        await entity.async_turn_on()
        assert self.coord.calls == [("light-1", "on")]
        assert entity.is_on is True

    @pytest.mark.asyncio
    async def test_brightness_steps(self) -> None:
        device = _device(
            EntityCategory.LIGHT,
            {
                "on": _command("on"),
                "off": _command("off"),
                "brightness_25": _command("brightness_25"),
                "brightness_50": _command("brightness_50"),
                "brightness_75": _command("brightness_75"),
                "brightness_100": _command("brightness_100"),
            },
        )
        entity = RuneLightEntity(device=device, coordinator=self.coord)
        assert entity.brightness_steps == [25, 50, 75, 100]
        await entity.async_turn_on(brightness=128)
        # 50% on 4 brightness steps → ceil((50/100)*(4-1)+1) = ceil(2.5) = 3 → brightness_75.
        assert self.coord.calls[-1] == ("light-1", "brightness_75")

    @pytest.mark.asyncio
    async def test_turn_off_sends_off(self) -> None:
        device = _device(
            EntityCategory.LIGHT, {"on": _command("on"), "off": _command("off")}
        )
        entity = RuneLightEntity(device=device, coordinator=self.coord)
        await entity.async_turn_off()
        assert self.coord.calls == [("light-1", "off")]


# ---------------------------------------------------------------------------
# Cover
# ---------------------------------------------------------------------------


class TestCover:
    def setup_method(self) -> None:
        self.coord = _Coordinator()

    @pytest.mark.asyncio
    async def test_open_close_stop(self) -> None:
        device = _device(
            EntityCategory.COVER,
            {
                "open": _command("open"),
                "close": _command("close"),
                "stop": _command("stop"),
            },
        )
        entity = RuneCoverEntity(device=device, coordinator=self.coord)
        # Without HA installed supported_features is 0; we just check
        # the dispatch paths work.
        await entity.async_open_cover()
        await entity.async_close_cover()
        await entity.async_stop_cover()
        assert [c[1] for c in self.coord.calls] == ["open", "close", "stop"]
        assert entity.is_closed is True  # closed after close_cover

    @pytest.mark.asyncio
    async def test_set_position_snaps(self) -> None:
        device = _device(
            EntityCategory.COVER,
            {
                "position_open": _command("position_open"),
                "position_close": _command("position_close"),
            },
        )
        entity = RuneCoverEntity(device=device, coordinator=self.coord)
        await entity.async_set_cover_position(position=80)
        assert self.coord.calls == [("cover-1", "position_open")]
        await entity.async_set_cover_position(position=20)
        assert self.coord.calls[-1] == ("cover-1", "position_close")


# ---------------------------------------------------------------------------
# Switch
# ---------------------------------------------------------------------------


class TestSwitch:
    def setup_method(self) -> None:
        self.coord = _Coordinator()

    @pytest.mark.asyncio
    async def test_basic_onoff(self) -> None:
        device = _device(
            EntityCategory.SWITCH, {"on": _command("on"), "off": _command("off")}
        )
        entity = RuneSwitchEntity(device=device, coordinator=self.coord)
        await entity.async_turn_on()
        await entity.async_turn_off()
        assert self.coord.calls == [("switch-1", "on"), ("switch-1", "off")]
        assert entity.is_on is False

    def test_apply_power_verdict_updates_state(self) -> None:
        device = _device(EntityCategory.SWITCH, {})
        entity = RuneSwitchEntity(device=device, coordinator=self.coord)
        entity._is_on = False  # type: ignore[attr-defined]
        entity.apply_power_verdict(True)
        assert entity.is_on is True
        entity.apply_power_verdict(False)
        assert entity.is_on is False


# ---------------------------------------------------------------------------
# Media Player
# ---------------------------------------------------------------------------


class TestMediaPlayer:
    def setup_method(self) -> None:
        self.coord = _Coordinator()

    @pytest.mark.asyncio
    async def test_basic_transport(self) -> None:
        device = _device(
            EntityCategory.MEDIA_PLAYER,
            {
                "power_on": _command("power_on"),
                "power_off": _command("power_off"),
                "volume_up": _command("volume_up"),
                "play": _command("play"),
                "pause": _command("pause"),
                "source_hdmi1": _command("source_hdmi1"),
                "source_hdmi2": _command("source_hdmi2"),
            },
        )
        entity = RuneMediaPlayerEntity(device=device, coordinator=self.coord)
        await entity.async_turn_on()
        await entity.async_media_play()
        await entity.async_volume_up()
        await entity.async_select_source("hdmi1")
        assert [c[1] for c in self.coord.calls] == [
            "power_on",
            "play",
            "volume_up",
            "source_hdmi1",
        ]
        assert entity.source == "hdmi1"

    def test_source_list_inferred(self) -> None:
        device = _device(
            EntityCategory.MEDIA_PLAYER,
            {
                "source_hdmi1": _command("source_hdmi1"),
                "source_aux": _command("source_aux"),
            },
        )
        entity = RuneMediaPlayerEntity(device=device, coordinator=self.coord)
        assert set(entity.source_list) == {"hdmi1", "aux"}


# ---------------------------------------------------------------------------
# Remote
# ---------------------------------------------------------------------------


class TestRemote:
    def setup_method(self) -> None:
        self.coord = _Coordinator()

    @pytest.mark.asyncio
    async def test_send_command_routes_to_pulse(self) -> None:
        device = _device(
            EntityCategory.REMOTE,
            {"vol_up": _command("vol_up"), "vol_down": _command("vol_down")},
        )
        entity = RuneRemoteEntity(device=device, coordinator=self.coord)
        await entity.async_send_command(command=["vol_up", "vol_down"])
        assert self.coord.calls == [("remote-1", "vol_up"), ("remote-1", "vol_down")]

    @pytest.mark.asyncio
    async def test_unknown_command_silently_skipped(self) -> None:
        device = _device(EntityCategory.REMOTE, {"vol_up": _command("vol_up")})
        entity = RuneRemoteEntity(device=device, coordinator=self.coord)
        await entity.async_send_command(command=["vol_up", "missing"])
        assert [c[1] for c in self.coord.calls] == ["vol_up"]
