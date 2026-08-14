"""Pronto byte-hash quantization (tier 2 identity).

Two captures of the same button collapse to the same byte hash iff
their timing words, when quantized to multiples of
``PRONTO_BYTE_HASH_BIN``, are equal. This is the tiebreaker for
sub-threshold protocols whose S/L pattern flips across the boundary
on jitter (Sony SIRC, Panasonic/Kaseikyo, TCL).

The bin size of 20 is empirically tuned — smaller bins make the hash
jitter-fragile, larger bins collide distinct buttons of protocols
whose long pulse sits below ``SL_THRESHOLD_US``.
"""
from __future__ import annotations

import hashlib

from custom_components.rune.const import GAP_THRESHOLD_US, PRONTO_BYTE_HASH_BIN


def compute_byte_hash(timings: list[int]) -> str | None:
    """Compute the byte-level hash of a timing array, or ``None`` if invalid.

    Returns ``None`` for inputs too short to identify (< 2 timing words
    after sanitization) or with no payload (just a gap). The hash is a
    hex-encoded SHA-256 of the canonical form: each timing word,
    after stripping leading/trailing gaps, is rounded to the nearest
    ``PRONTO_BYTE_HASH_BIN`` and emitted as a 4-digit upper-case hex
    string.
    """
    sanitized = _sanitize(timings)
    if len(sanitized) < 2:
        return None
    canonical = " ".join(
        f"{round(v / PRONTO_BYTE_HASH_BIN) * PRONTO_BYTE_HASH_BIN:04X}" for v in sanitized
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest


def _sanitize(timings: list[int]) -> list[int]:
    """Strip leading and trailing idle above ``GAP_THRESHOLD_US``.

    Leading idle skews the hash when receivers settle for different
    durations; the gap-threshold cutoff ensures the hash only covers
    the actual signal, not the post-signal dead air. Internal gaps
    are NOT stripped — they're part of the signal.
    """
    sanitized = [abs(int(t)) for t in timings if t]
    while sanitized and sanitized[0] >= GAP_THRESHOLD_US:
        sanitized.pop(0)
    while sanitized and sanitized[-1] >= GAP_THRESHOLD_US:
        sanitized.pop()
    return sanitized
