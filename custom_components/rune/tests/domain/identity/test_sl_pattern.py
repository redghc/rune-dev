"""Tests for the S/L fingerprint extractor."""
from __future__ import annotations

from custom_components.rune.const import GAP_THRESHOLD_US, SL_THRESHOLD_US
from custom_components.rune.domain.identity.sl_pattern import (
    extract_device_address,
    extract_sl_pattern,
)


class TestExtractSlPattern:
    def test_short_timing_word(self) -> None:
        # Magnitude 10 < SL_THRESHOLD_US (500).
        assert extract_sl_pattern([10]) == "S"

    def test_long_timing_word(self) -> None:
        # Magnitude 1000 > SL_THRESHOLD_US.
        assert extract_sl_pattern([1000]) == "L"

    def test_at_threshold_is_long(self) -> None:
        assert extract_sl_pattern([SL_THRESHOLD_US]) == "L"

    def test_just_below_threshold_is_short(self) -> None:
        assert extract_sl_pattern([SL_THRESHOLD_US - 1]) == "S"

    def test_negative_values_use_magnitude(self) -> None:
        assert extract_sl_pattern([-1000]) == "L"
        assert extract_sl_pattern([-10]) == "S"

    def test_gap_terminates(self) -> None:
        # First entry is a huge space → 'G' then stop.
        assert extract_sl_pattern([GAP_THRESHOLD_US + 1000, 100, 200]) == "G"

    def test_empty(self) -> None:
        assert extract_sl_pattern([]) == ""


class TestExtractDeviceAddress:
    def test_nec_address_parsed(self) -> None:
        # NEC Pronto layout: header (4 words) + address word + command word.
        result = extract_device_address("NEC", "0000 0068 0000 00C2 FB04 0008")
        assert result == "0xFB04"

    def test_non_nec_returns_none(self) -> None:
        assert extract_device_address("RC5", "0000 0068 0000 00C2") is None

    def test_no_protocol_returns_none(self) -> None:
        assert extract_device_address(None, "0000 0068 0000 00C2") is None

    def test_short_pronto_returns_none(self) -> None:
        # Only the 4-word header — no address word.
        assert extract_device_address("NEC", "0000 0068 0000 0000") is None

    def test_no_code_returns_none(self) -> None:
        assert extract_device_address("NEC", None) is None

    def test_malformed_pronto_returns_none(self) -> None:
        # Odd digit count — _parse_pronto_words returns empty list.
        assert extract_device_address("NEC", "000") is None
