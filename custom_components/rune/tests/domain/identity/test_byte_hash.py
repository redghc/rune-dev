"""Tests for the byte-hash quantization."""
from __future__ import annotations

from custom_components.rune.domain.identity.byte_hash import compute_byte_hash


class TestComputeByteHash:
    def test_returns_hex_string_or_none(self) -> None:
        result = compute_byte_hash([9000, -4500, 600, -1700])
        assert result is not None
        assert len(result) == 64  # SHA-256 hex

    def test_identical_inputs_produce_identical_hash(self) -> None:
        a = compute_byte_hash([9000, -4500, 600, -1700])
        b = compute_byte_hash([9000, -4500, 600, -1700])
        assert a == b

    def test_jitter_within_bin_collapses(self) -> None:
        # Both inputs differ by <= 5 us (less than PRONTO_BYTE_HASH_BIN=20).
        a = compute_byte_hash([9000, -4500, 600, -1700])
        b = compute_byte_hash([9003, -4501, 601, -1702])
        assert a == b

    def test_jitter_beyond_bin_differs(self) -> None:
        # Differ by >= 40 us — multiple bins apart, after the first
        # mark rounds to a different bin.
        a = compute_byte_hash([9000, -4500, 600, -1700])
        b = compute_byte_hash([9100, -4500, 600, -1700])
        assert a != b

    def test_short_input_returns_none(self) -> None:
        assert compute_byte_hash([100]) is None

    def test_empty_input_returns_none(self) -> None:
        assert compute_byte_hash([]) is None

    def test_leading_gap_stripped(self) -> None:
        # A leading 50_000 us gap is way above GAP_THRESHOLD_US (25_000).
        a = compute_byte_hash([50_000, 9000, -4500, 600, -1700])
        b = compute_byte_hash([9000, -4500, 600, -1700])
        assert a == b
