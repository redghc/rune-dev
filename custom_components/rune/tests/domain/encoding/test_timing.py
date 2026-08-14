"""Tests for the timing utility helpers."""
from __future__ import annotations

from custom_components.rune.const import TERMINATOR_SPACE_US
from custom_components.rune.domain.encoding.timing import (
    apply_bounded_terminator,
    trim_idle,
)


class TestTrimIdle:
    def test_leading_idle_dropped(self) -> None:
        assert trim_idle([50_000, 100, -50]) == [100, -50]

    def test_trailing_idle_dropped(self) -> None:
        assert trim_idle([100, -50, 30_000]) == [100, -50]

    def test_internal_gap_preserved(self) -> None:
        # The -50_000 us is at the END, so trim_idle strips it as trailing idle.
        # To assert internal preservation, place the long gap in the middle.
        timings = [100, -500, -50_000, 200, -50]
        # Trailing -50 < 20_000, stays; leading 100 < 20_000, stays; the middle
        # long gap is internal and should stay.
        assert trim_idle(timings) == timings

    def test_both_ends_trimmed(self) -> None:
        timings = [60_000, 100, -50, 90_000]
        assert trim_idle(timings) == [100, -50]

    def test_below_threshold_kept(self) -> None:
        # 1000 us is below IDLE_TRIM_US (20_000).
        timings = [1000, -500, 800]
        assert trim_idle(timings) == timings

    def test_empty_unchanged(self) -> None:
        assert trim_idle([]) == []

    def test_returns_new_list(self) -> None:
        original = [100, -50]
        result = trim_idle(original)
        assert result is not original


class TestApplyBoundedTerminator:
    def test_empty_returns_empty(self) -> None:
        assert apply_bounded_terminator([]) == []

    def test_ends_on_mark_appends_terminator(self) -> None:
        result = apply_bounded_terminator([9000, 4500])
        assert result[-1] == -TERMINATOR_SPACE_US
        assert result[:2] == [9000, 4500]

    def test_ends_on_short_space_unchanged(self) -> None:
        timings = [1000, -5000]
        assert apply_bounded_terminator(timings) == timings

    def test_ends_on_long_space_clamped(self) -> None:
        long_space = -100_000
        result = apply_bounded_terminator([1000, long_space])
        assert result[-1] == -TERMINATOR_SPACE_US
        assert result[0] == 1000

    def test_returns_new_list(self) -> None:
        original = [100, -50]
        result = apply_bounded_terminator(original)
        assert result is not original
