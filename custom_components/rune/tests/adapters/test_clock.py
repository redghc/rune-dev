"""Tests for the SystemClockAdapter and FrozenClockAdapter."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.rune.adapters.clock import (
    FrozenClockAdapter,
    SystemClockAdapter,
)


class TestSystemClockAdapter:
    def test_now_is_utc(self) -> None:
        now = SystemClockAdapter().now()
        assert now.tzinfo is not None
        assert now.utcoffset().total_seconds() == 0

    def test_monotonic_is_float(self) -> None:
        assert isinstance(SystemClockAdapter().monotonic(), float)

    def test_monotonic_increases(self) -> None:
        clock = SystemClockAdapter()
        first = clock.monotonic()
        second = clock.monotonic()
        assert second >= first


class TestFrozenClockAdapter:
    def test_default_origin(self) -> None:
        clock = FrozenClockAdapter()
        assert clock.now().year == 2026
        assert clock.now().tzinfo is not None
        assert clock.now().utcoffset().total_seconds() == 0

    def test_custom_origin(self) -> None:
        origin = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        clock = FrozenClockAdapter(origin=origin)
        assert clock.now() == origin

    def test_initial_monotonic_is_zero(self) -> None:
        assert FrozenClockAdapter().monotonic() == 0.0

    def test_advance_moves_monotonic(self) -> None:
        clock = FrozenClockAdapter()
        clock.advance(5.0)
        assert clock.monotonic() == 5.0
        clock.advance(2.5)
        assert clock.monotonic() == 7.5

    def test_advance_moves_wall_clock(self) -> None:
        origin = datetime(2026, 1, 1, tzinfo=UTC)
        clock = FrozenClockAdapter(origin=origin)
        clock.advance(60.0)
        assert clock.now() == datetime(2026, 1, 1, 0, 1, 0, tzinfo=UTC)

    def test_negative_advance_rejected(self) -> None:
        with pytest.raises(ValueError, match="rewind"):
            FrozenClockAdapter().advance(-1.0)

    def test_zero_advance_is_noop(self) -> None:
        clock = FrozenClockAdapter()
        clock.advance(0.0)
        assert clock.monotonic() == 0.0
