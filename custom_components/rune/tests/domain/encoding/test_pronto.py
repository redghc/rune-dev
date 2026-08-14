"""Tests for Pronto hex ⇄ raw timings conversion."""
from __future__ import annotations

import pytest

from custom_components.rune.domain.encoding.pronto import (
    ProntoFormatError,
    pronto_hex_to_raw_timings,
    raw_timings_to_pronto_hex,
)


class TestProntoHexToRawTimings:
    def test_learned_format_passes_microseconds_through(self) -> None:
        # Header: 0 0 0 0, then 9000, 4500, 600, 1700 (signed alternating).
        # Words: 0x2328 = 9000, 0x1194 = 4500, 0x0258 = 600, 0x06A4 = 1700.
        result = pronto_hex_to_raw_timings("0000 0000 0000 0000 2328 1194 0258 06A4")
        assert result == [9000, -4500, 600, -1700]

    def test_signed_alternating_marks_spaces(self) -> None:
        # 4 timing words: mark, space, mark, space.
        result = pronto_hex_to_raw_timings("0000 0000 0000 0000 2328 1194 0258 06A4")
        assert result[0] > 0   # mark
        assert result[1] < 0   # space
        assert result[2] > 0   # mark
        assert result[3] < 0   # space
        assert len(result) == 4

    def test_compact_hex_input(self) -> None:
        compact = pronto_hex_to_raw_timings("000000000000000023281194")
        spaced = pronto_hex_to_raw_timings("0000 0000 0000 0000 2328 1194")
        assert compact == spaced

    def test_tab_and_newline_whitespace_stripped(self) -> None:
        messy = "0000\t0000\n0000\r0000\t2328\n1194"
        clean = pronto_hex_to_raw_timings(messy)
        assert clean == [9000, -4500]

    def test_empty_input_raises(self) -> None:
        with pytest.raises(ProntoFormatError):
            pronto_hex_to_raw_timings("")

    def test_odd_digit_count_raises(self) -> None:
        with pytest.raises(ProntoFormatError, match="multiple of 4"):
            pronto_hex_to_raw_timings("000")

    def test_non_hex_raises(self) -> None:
        with pytest.raises(ProntoFormatError, match="Non-hex"):
            pronto_hex_to_raw_timings("0000 GGGG")


class TestRawTimingsToProntoHex:
    def test_learned_format_round_trip(self) -> None:
        original = [9000, -4500, 600, -1700, 600, -1700]
        hex_str = raw_timings_to_pronto_hex(original)
        assert hex_str.startswith("0000 ")
        restored = pronto_hex_to_raw_timings(hex_str)
        # Round-trip with rounding tolerance — Pronto uses integer
        # microsecond words, so a ±1us drift per word is normal.
        for o, r in zip(original, restored, strict=True):
            assert abs(o - r) <= 1

    def test_with_frequency_emits_freq_word(self) -> None:
        hex_str = raw_timings_to_pronto_hex([100, -100, 200, -200], frequency_hz=38_000)
        # First word is non-zero when a frequency is provided.
        first_word = int(hex_str.split(" ")[0], 16)
        assert first_word != 0

    def test_zero_frequency_treated_as_learned(self) -> None:
        hex_str = raw_timings_to_pronto_hex([100, -100], frequency_hz=0)
        assert hex_str.startswith("0000 ")

    def test_empty_timings_returns_just_header(self) -> None:
        hex_str = raw_timings_to_pronto_hex([])
        # Header is 4 words, all zero for learned/raw.
        assert hex_str == "0000 0000 0000 0000"
