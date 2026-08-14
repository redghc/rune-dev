"""Tests for the time helpers."""
from __future__ import annotations

import pytest

from custom_components.rune.domain.time import monotonic_seconds, parse_iso, utcnow_iso


class TestUtcnowIso:
    def test_returns_string(self) -> None:
        assert isinstance(utcnow_iso(), str)

    def test_ends_with_z_suffix(self) -> None:
        assert utcnow_iso().endswith("Z")


class TestParseIso:
    def test_parses_z_suffix(self) -> None:
        parsed = parse_iso("2026-08-12T20:00:00Z")
        assert parsed.year == 2026
        assert parsed.month == 8
        assert parsed.day == 12
        assert parsed.hour == 20
        assert parsed.tzinfo is not None

    def test_parses_offset_suffix(self) -> None:
        parsed = parse_iso("2026-08-12T20:00:00+00:00")
        assert parsed.tzinfo is not None

    def test_naive_timestamp_gets_utc(self) -> None:
        parsed = parse_iso("2026-08-12T20:00:00")
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0

    def test_malformed_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_iso("not-a-timestamp")


class TestMonotonicSeconds:
    def test_returns_float(self) -> None:
        assert isinstance(monotonic_seconds(), float)

    def test_monotonic_increasing(self) -> None:
        a = monotonic_seconds()
        b = monotonic_seconds()
        assert b >= a
