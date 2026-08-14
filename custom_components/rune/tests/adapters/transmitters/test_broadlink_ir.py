"""Tests for the Broadlink IR adapter's encoding helpers.

The path-detection and send paths require HA (skipped when HA is
unavailable). The pure encoding logic — Pronto → Broadlink pack →
base64 — is exercised here without HA.
"""
from __future__ import annotations

import pytest

from custom_components.rune.adapters.transmitters.broadlink_ir import (
    BroadlinkIRTransmitter,
)
from custom_components.rune.domain.enums import (
    CommandCategory,
    SignalCategory,
)
from custom_components.rune.domain.errors import CommandNotLearnedError
from custom_components.rune.domain.models import PulseCommand, PulsePayload


def _command(
    *,
    raw_timings: tuple[int, ...] | None = None,
    decoded_hex: str | None = None,
    base64_packet: str | None = None,
) -> PulseCommand:
    return PulseCommand(
        key="k",
        label="L",
        category=CommandCategory.POWER,
        signal_category=SignalCategory.default_ir(),
        payload=PulsePayload(
            raw_timings=raw_timings,
            decoded_hex=decoded_hex,
            base64_packet=base64_packet,
        ),
    )


class FakeHass:
    def __init__(self) -> None:
        self.states: dict[str, object] = {}


class TestEncodeToBase64:
    def test_pre_encoded_packet_passes_through_with_prefix(self) -> None:
        adapter = BroadlinkIRTransmitter(FakeHass(), "remote.x")
        cmd = _command(base64_packet="JgASAB4D")
        result = adapter._encode_to_base64(cmd)
        assert result == "b64:JgASAB4D"

    def test_raw_timings_round_trip(self) -> None:
        adapter = BroadlinkIRTransmitter(FakeHass(), "remote.x")
        cmd = _command(raw_timings=(9000, -4500, 600, -1700))
        result = adapter._encode_to_base64(cmd)
        assert result is not None
        assert result.startswith("b64:")

    def test_pronto_hex_input(self) -> None:
        adapter = BroadlinkIRTransmitter(FakeHass(), "remote.x")
        cmd = _command(decoded_hex="0000 0000 0000 0000 2328 1194 0258 06A4")
        result = adapter._encode_to_base64(cmd)
        assert result is not None
        assert result.startswith("b64:")

    def test_empty_payload_returns_none(self) -> None:
        adapter = BroadlinkIRTransmitter(FakeHass(), "remote.x")
        cmd = _command()
        result = adapter._encode_to_base64(cmd)
        assert result is None

    def test_is_available_reflects_state(self) -> None:
        hass = FakeHass()
        hass.states["remote.x"] = type("State", (), {"state": "idle"})()
        adapter = BroadlinkIRTransmitter(hass, "remote.x")
        assert adapter.is_available is True

        hass.states["remote.x"] = type("State", (), {"state": "unavailable"})()
        assert adapter.is_available is False

        hass.states.pop("remote.x")
        assert adapter.is_available is False


class TestSendWithoutPayload:
    @pytest.mark.asyncio
    async def test_send_with_empty_payload_raises(self) -> None:
        adapter = BroadlinkIRTransmitter(FakeHass(), "remote.x")
        cmd = _command()
        with pytest.raises(CommandNotLearnedError):
            await adapter.send(cmd)


# Skip the path-detection tests when HA is not importable.
homeassistant = pytest.importorskip("homeassistant", reason="HA not installed")
