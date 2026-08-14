"""Tests for the signal catalog matcher."""
from __future__ import annotations

from custom_components.rune.domain.enums import SignalCategory
from custom_components.rune.domain.models import UnknownRemote, UnknownSignal
from custom_components.rune.domain.signal.matcher import match
from custom_components.rune.domain.signal.normalize import NormalizedSignal, normalize


def _signal(
    *,
    fingerprint: str,
    protocol: str | None = None,
    decoded: str | None = None,
    byte_hash: str | None = None,
) -> UnknownSignal:
    return UnknownSignal(
        id=f"sig-{fingerprint}",
        fingerprint=fingerprint,
        byte_hash=byte_hash,
        decoded_fingerprint=decoded,
        signal_category=SignalCategory.default_ir(),
        protocol_label=protocol,
        raw_timings=(),
        first_seen="2026-08-12T20:00:00Z",
        last_seen="2026-08-12T20:00:00Z",
        hit_count=1,
    )


def _remote(*, signals: list[UnknownSignal], protocol: str | None = None) -> UnknownRemote:
    return UnknownRemote(
        id=f"r-{signals[0].id if signals else 'empty'}",
        label=None,
        protocol_label=protocol,
        device_address=None,
        signals=signals,
    )


class TestMatch:
    def test_tier1_decoded_match(self) -> None:
        remote = _remote(
            protocol="NEC",
            signals=[_signal(fingerprint="X", protocol="NEC", decoded="NEC:0xA:0x1")],
        )
        cap = normalize(
            timings=[100, -200],
            signal_category=SignalCategory.default_ir(),
            protocol_label="NEC",
            decoded_fingerprint="NEC:0xA:0x1",
        )
        result = match(cap, [remote])
        assert result.tier == 1
        assert result.signal is not None
        assert result.signal.decoded_fingerprint == "NEC:0xA:0x1"

    def test_tier2_byte_hash_match(self) -> None:
        # Same byte hash but no decoded — match at tier 2.
        byte_hash = "deadbeef" + "0" * 56  # 64 hex chars
        remote = _remote(
            protocol="Sony",
            signals=[_signal(fingerprint="X", protocol="Sony", byte_hash=byte_hash)],
        )
        cap = NormalizedSignal(
            transport=SignalCategory.default_ir().transport,
            carrier_frequency_hz=38_000,
            protocol_label="Sony",
            code_hex=None,
            raw_timings=(9000, -4500, 600, -1700),
            sl_fingerprint="LLSS",
            byte_hash=byte_hash,
            decoded_fingerprint=None,
            device_address=None,
        )
        result = match(cap, [remote])
        assert result.tier == 2

    def test_tier3_sl_match(self) -> None:
        remote = _remote(protocol="Sony", signals=[_signal(fingerprint="LLLL", protocol="Sony")])
        cap = normalize(
            timings=[9000, -4500, 600, -1700],
            signal_category=SignalCategory.default_ir(),
            protocol_label="Sony",
        )
        # All magnitudes > SL_THRESHOLD_US → fingerprint "LLLL".
        result = match(cap, [remote])
        assert result.tier == 3

    def test_no_match(self) -> None:
        # Signal has short trailing timing → "LLLS" fingerprint.
        # Capture has long trailing timing → "LLLL" fingerprint.
        remote = _remote(
            protocol="NEC",
            signals=[_signal(fingerprint="LLLS", protocol="NEC")],
        )
        cap = normalize(
            timings=[9000, -4500, 600, -1700],
            signal_category=SignalCategory.default_ir(),
            protocol_label="NEC",
        )
        result = match(cap, [remote])
        assert result.signal is None

    def test_protocol_mismatch_blocks_match(self) -> None:
        remote = _remote(
            protocol="NEC",
            signals=[_signal(fingerprint="LLLS", protocol="NEC")],
        )
        cap = normalize(
            timings=[9000, -4500, 600, -1700],
            signal_category=SignalCategory.default_ir(),
            protocol_label="Sony",
        )
        result = match(cap, [remote])
        assert result.signal is None

    def test_tier_precedence_order(self) -> None:
        # Two signals with same fingerprint but one has decoded identity.
        sig_no_decoded = _signal(fingerprint="LLLS", protocol="Sony")
        sig_decoded = _signal(fingerprint="LLLS", protocol="NEC", decoded="NEC:0xA:0x1")
        remote_a = _remote(protocol="Sony", signals=[sig_no_decoded])
        remote_b = _remote(protocol="NEC", signals=[sig_decoded])
        cap = normalize(
            timings=[9000, -4500, 600, -1700],
            signal_category=SignalCategory.default_ir(),
            protocol_label="NEC",
            decoded_fingerprint="NEC:0xA:0x1",
        )
        result = match(cap, [remote_a, remote_b])
        assert result.tier == 1
        assert result.signal is sig_decoded
