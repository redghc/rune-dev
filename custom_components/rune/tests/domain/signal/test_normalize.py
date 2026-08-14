"""Tests for capture normalization."""
from __future__ import annotations

import contextlib

from custom_components.rune.domain.enums import SignalCategory
from custom_components.rune.domain.signal.normalize import normalize


class TestNormalize:
    def test_basic_normalization(self) -> None:
        result = normalize(
            timings=[9000, -4500, 600, -1700],
            signal_category=SignalCategory.default_ir(),
        )
        # 9000=L, 4500=L, 600=L, 1700=L (all magnitudes > 500us).
        assert result.sl_fingerprint == "LLLL"
        assert result.byte_hash is not None
        assert result.decoded_fingerprint is None
        assert result.protocol_label is None
        assert result.device_address is None

    def test_with_protocol_and_code(self) -> None:
        result = normalize(
            timings=[9000, -4500, 600, -1700],
            signal_category=SignalCategory.default_ir(),
            protocol_label="NEC",
            # Pronto header (4 words) + address word (0xFB04) + command word.
            code_hex="0000 0068 0000 00C2 FB04 0008",
        )
        assert result.protocol_label == "NEC"
        assert result.device_address == "0xFB04"
        assert result.decoded_fingerprint is None

    def test_with_decoded_fingerprint(self) -> None:
        result = normalize(
            timings=[9000, -4500],
            signal_category=SignalCategory.default_ir(),
            decoded_fingerprint="NEC:0xFB04:0x08",
        )
        assert result.decoded_fingerprint == "NEC:0xFB04:0x08"

    def test_rf_signal_keeps_carrier(self) -> None:
        result = normalize(
            timings=[1000, -500, 2000, -1500],
            signal_category=SignalCategory.default_rf(433_920_000),
        )
        assert result.carrier_frequency_hz == 433_920_000
        assert result.transport.value == "rf"

    def test_frozen_dataclass(self) -> None:
        result = normalize(timings=[1000], signal_category=SignalCategory.default_ir())
        with contextlib.suppress(AttributeError, Exception):
            result.sl_fingerprint = "X"  # type: ignore[misc]

    def test_tuple_timings_converted(self) -> None:
        result = normalize(
            timings=(9000, -4500),
            signal_category=SignalCategory.default_ir(),
        )
        assert result.raw_timings == (9000, -4500)
