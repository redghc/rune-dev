"""Tiered signal-identity matching.

Three tiers, strongest first:

1. Decoded protocol identity — e.g. ``"NEC:0xFB04:0x08"``. Jitter-immune.
2. Byte hash — Pronto timing words quantized to multiples of
   ``PRONTO_BYTE_HASH_BIN``. Jitter-tolerant within the bin.
3. S/L fingerprint — short/long pattern. Jitter-fragile at the boundary.

Matching rule: the highest tier BOTH sides carry decides. So a Sony
capture whose S/L pattern flipped across the threshold still matches
its trigger via byte hash. A pre-tier-2 trigger (no byte hash) matches
on S/L alone (legacy behavior).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalIdentity:
    """A captured signal's identity at all three tiers.

    Each tier is optional: a capture may have decoded identity but no
    byte hash (impossible in practice but defensively handled), or a
    byte hash but no decoded identity (sub-threshold protocols).
    """

    decoded_fingerprint: str | None
    byte_hash: str | None
    sl_fingerprint: str

    def match_tier(self, other: SignalIdentity) -> int | None:
        """Return the tier (1/2/3) at which ``self`` matches ``other``.

        Returns ``None`` when no tier matches. The lower the tier number,
        the stronger the identity.
        """
        if (
            self.decoded_fingerprint is not None
            and other.decoded_fingerprint is not None
            and self.decoded_fingerprint == other.decoded_fingerprint
        ):
            return 1
        if (
            self.byte_hash is not None
            and other.byte_hash is not None
            and self.byte_hash == other.byte_hash
        ):
            return 2
        if self.sl_fingerprint and self.sl_fingerprint == other.sl_fingerprint:
            return 3
        return None

    def same_as(self, other: SignalIdentity) -> bool:
        """Return True if any tier matches."""
        return self.match_tier(other) is not None
