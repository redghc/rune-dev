"""Tests for capture-denoising helpers."""
from __future__ import annotations

from custom_components.rune.domain.signal.quality import (
    clean_frame,
    consensus,
    frame_cells,
    split_repeats,
    trim_idle_for_quality,
)


class TestTrimIdleForQuality:
    def test_drops_long_idle(self) -> None:
        assert trim_idle_for_quality([50_000, 100, -50, 30_000]) == [100, -50]

    def test_preserves_short_gaps(self) -> None:
        assert trim_idle_for_quality([1000, -500]) == [1000, -500]


class TestSplitRepeats:
    def test_single_frame_no_split(self) -> None:
        result = split_repeats([100, -200, 300])
        assert result == [[100, -200, 300]]

    def test_split_on_long_gap(self) -> None:
        # Space of -1500 us separates frames.
        timings = [100, -200, 100, -1500, 100, -200, 100]
        result = split_repeats(timings)
        assert len(result) == 2

    def test_empty(self) -> None:
        assert split_repeats([]) == []


class TestFrameCells:
    def test_short_mark(self) -> None:
        # |v| < 600 → single cell.
        assert frame_cells([300]) == "H"

    def test_long_mark(self) -> None:
        # |v| >= 600 → two cells.
        assert frame_cells([700]) == "HH"

    def test_marks_and_spaces(self) -> None:
        # [300, -700] → H + ll.
        assert frame_cells([300, -700]) == "Hll"


class TestConsensus:
    def test_empty(self) -> None:
        assert consensus([]) == ("", 0, 0)

    def test_single_frame_full_agreement(self) -> None:
        cell_str, agreeing, total = consensus([100, -200, 300])
        assert total == 1
        assert agreeing == 1
        assert cell_str  # not empty

    def test_majority_wins(self) -> None:
        timings = (
            [100, -200, 100, -200, 100, -1500,  # frame 1
             100, -200, 100, -200, 100, -1500,  # frame 2 (same)
             999, 999, 999, 999, 999, -1500]   # frame 3 (garbage)
        )
        _, agreeing, total = consensus(timings)
        assert total == 3
        assert agreeing == 2


class TestCleanFrame:
    def test_returns_one_frame_plus_trailing_gap(self) -> None:
        # Two identical frames separated by a -1500 us inter-frame gap.
        timings = [100, -200, 100, -1500, 100, -200, 100, -1500]
        result = clean_frame(timings)
        # Each frame is 3 values [100, -200, 100] → one frame + 1 trailing gap = 4.
        assert len(result) == 4
        assert result[-1] == -1800  # default trailing gap
        assert result[:3] == [100, -200, 100]

    def test_empty_returns_empty(self) -> None:
        assert clean_frame([]) == []
