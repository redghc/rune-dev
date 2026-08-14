"""Tests for the Broadlink IR/RF pack/unpack and base64 wrap."""
from __future__ import annotations

from base64 import b64decode

import pytest

from custom_components.rune.domain.encoding.broadlink import (
    BroadlinkFormatError,
    broadlink_to_base64,
    broadlink_to_lirc,
    decode_broadlink_rf_packet,
    lirc_to_broadlink,
)


class TestLircToBroadlink:
    def test_short_tick_packs_one_byte(self) -> None:
        buf = bytes(lirc_to_broadlink([50]))
        assert len(buf) == 1
        # 50 * 269 / 8192 = 1.64 → rounds to 2.
        assert buf[0] == 2

    def test_long_tick_emits_escape_sequence(self) -> None:
        buf = bytes(lirc_to_broadlink([8192]))
        # 8192 * 269 / 8192 = 269 → > 255 → escape sequence.
        assert buf[0] == 0x00
        assert len(buf) == 3
        assert (buf[1] << 8) | buf[2] == 269

    def test_negative_clamped_to_zero(self) -> None:
        buf = bytes(lirc_to_broadlink([-5]))
        assert buf == b"\x00"


class TestBroadlinkToLirc:
    def test_inverse_of_short(self) -> None:
        # Values whose encoded ticks fit in one byte (< 255).
        # Use mid-range values where rounding error is small relative to the value.
        original = [1000, 5000]
        buf = bytes(lirc_to_broadlink(original))
        restored = broadlink_to_lirc(buf)
        # The 269/8192 scale is inherently ~1% lossy; allow ~2% tolerance.
        for o, g in zip(original, restored, strict=True):
            assert abs(o - g) <= max(2, int(o * 0.02))

    def test_inverse_of_long(self) -> None:
        # Values that exceed 255 ticks and trigger the escape sequence.
        original = [8000, 16_000]
        buf = bytes(lirc_to_broadlink(original))
        restored = broadlink_to_lirc(buf)
        for o, g in zip(original, restored, strict=True):
            assert abs(o - g) <= max(2, int(o * 0.02))

    def test_handles_plain_byte(self) -> None:
        # Plain byte (no 0x00 escape) → straightforward round-trip.
        assert broadlink_to_lirc(b"\x05") == [round(5 * 8192 / 269)]


class TestBroadlinkToBase64:
    def test_returns_ascii_string(self) -> None:
        result = broadlink_to_base64(b"\x26\x00\x00\x01abc")
        assert isinstance(result, str)
        assert result.isascii()

    def test_round_trips(self) -> None:
        original = b"\x26\x00\x00\x01abc\x00\x00\x00"
        encoded = broadlink_to_base64(original)
        assert b64decode(encoded) == original


class TestDecodeBroadlinkRfPacket:
    def _build_packet(self, pulses: list[int]) -> bytes:
        body = bytearray()
        for pulse in pulses:
            tick = round(abs(pulse) / 32.84)
            if tick < 256:
                body.append(tick)
            else:
                body.append(0x00)
                body.append((tick >> 8) & 0xFF)
                body.append(tick & 0xFF)
        return bytes([0xB2, 5, len(body) & 0xFF, (len(body) >> 8) & 0xFF]) + bytes(body)

    def test_decodes_short_pulses(self) -> None:
        packet = self._build_packet([100, -200, 300, -400])
        timings, repeat = decode_broadlink_rf_packet(packet)
        assert repeat == 5
        assert len(timings) == 4
        assert timings[0] > 0  # mark
        assert timings[1] < 0  # space

    def test_decodes_long_pulses(self) -> None:
        packet = self._build_packet([10_000, -10_000])
        timings, repeat = decode_broadlink_rf_packet(packet)
        assert repeat == 5
        # round(10_000 / 32.84) ~ 304 ticks, * 32.84 us ~ 10_000 us.
        assert timings[0] > 8000
        assert timings[1] < -8000

    def test_short_packet_raises(self) -> None:
        with pytest.raises(BroadlinkFormatError):
            decode_broadlink_rf_packet(b"\xB2\x00")

    def test_empty_pulses_section(self) -> None:
        packet = bytes([0xB2, 7, 0, 0])
        timings, repeat = decode_broadlink_rf_packet(packet)
        assert timings == []
        assert repeat == 7
