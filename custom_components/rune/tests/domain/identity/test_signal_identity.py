"""Tests for the tiered signal identity matcher."""
from __future__ import annotations

from custom_components.rune.domain.identity.signal_identity import SignalIdentity


class TestSignalIdentity:
    def test_tier1_match_returns_one(self) -> None:
        a = SignalIdentity(
            decoded_fingerprint="NEC:0xFB04:0x08", byte_hash="x", sl_fingerprint="SLLS"
        )
        b = SignalIdentity(
            decoded_fingerprint="NEC:0xFB04:0x08", byte_hash="y", sl_fingerprint="LLSS"
        )
        assert a.match_tier(b) == 1

    def test_tier2_match_returns_two(self) -> None:
        a = SignalIdentity(decoded_fingerprint=None, byte_hash="same", sl_fingerprint="SLLS")
        b = SignalIdentity(decoded_fingerprint=None, byte_hash="same", sl_fingerprint="LLSS")
        assert a.match_tier(b) == 2

    def test_tier3_match_returns_three(self) -> None:
        a = SignalIdentity(decoded_fingerprint=None, byte_hash=None, sl_fingerprint="SLSLLS")
        b = SignalIdentity(
            decoded_fingerprint=None, byte_hash="different", sl_fingerprint="SLSLLS"
        )
        assert a.match_tier(b) == 3

    def test_no_match_returns_none(self) -> None:
        a = SignalIdentity(decoded_fingerprint=None, byte_hash=None, sl_fingerprint="SLLS")
        b = SignalIdentity(decoded_fingerprint=None, byte_hash=None, sl_fingerprint="LLSS")
        assert a.match_tier(b) is None

    def test_decoded_takes_precedence_over_byte_hash(self) -> None:
        # Both have same byte_hash (would be tier 2), only one has decoded.
        # Tier 1 still wins when both sides carry decoded and match.
        a = SignalIdentity(decoded_fingerprint="X", byte_hash="same", sl_fingerprint="SLSLLS")
        b = SignalIdentity(decoded_fingerprint="X", byte_hash="same", sl_fingerprint="DIFFERENT")
        assert a.match_tier(b) == 1

    def test_decoded_mismatch_falls_through(self) -> None:
        # Decoded identities differ → tier 1 fails; check tier 2.
        a = SignalIdentity(decoded_fingerprint="X", byte_hash="same", sl_fingerprint="SLSLLS")
        b = SignalIdentity(decoded_fingerprint="Y", byte_hash="same", sl_fingerprint="DIFFERENT")
        assert a.match_tier(b) == 2

    def test_one_side_missing_decoded_skips_tier1(self) -> None:
        a = SignalIdentity(decoded_fingerprint="X", byte_hash="same", sl_fingerprint="SLSLLS")
        b = SignalIdentity(decoded_fingerprint=None, byte_hash="same", sl_fingerprint="DIFFERENT")
        # Tier 1: a has decoded, b doesn't → can't match.
        # Tier 2: same byte_hash → match.
        assert a.match_tier(b) == 2

    def test_same_as_returns_bool(self) -> None:
        a = SignalIdentity(decoded_fingerprint=None, byte_hash=None, sl_fingerprint="AB")
        b = SignalIdentity(decoded_fingerprint=None, byte_hash=None, sl_fingerprint="AB")
        c = SignalIdentity(decoded_fingerprint=None, byte_hash=None, sl_fingerprint="CD")
        assert a.same_as(b) is True
        assert a.same_as(c) is False
