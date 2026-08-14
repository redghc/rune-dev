"""Signal matching — find the existing UnknownSignal a capture belongs to.

The matcher walks an incoming ``NormalizedSignal`` against every signal
on every remote in the catalog and returns the highest-tier match. A
capture that doesn't match any existing signal is a candidate for a
new unknown-signal row.

Tiers, strongest first:

1. Decoded protocol fingerprint.
2. Byte hash.
3. S/L fingerprint.

The matcher prefers a lower-tier match on the same remote over a
higher-tier match on a different remote: a Sony capture from remote A
whose byte hash matches an A-row is more likely correct than one
whose decoded identity happens to coincide with a B-row (rare but
possible under decoded collisions). The caller decides whether
``device_address`` is part of the match — it isn't here, because
``UnknownSignal`` already groups by device address.
"""
from __future__ import annotations

from dataclasses import dataclass

from custom_components.rune.domain.identity.signal_identity import SignalIdentity
from custom_components.rune.domain.models import UnknownRemote, UnknownSignal
from custom_components.rune.domain.signal.normalize import NormalizedSignal


@dataclass(frozen=True)
class MatchResult:
    """Result of an identity lookup across the unknown catalog."""

    remote: UnknownRemote | None
    signal: UnknownSignal | None
    tier: int | None


def match(
    capture: NormalizedSignal,
    remotes: list[UnknownRemote],
) -> MatchResult:
    """Return the best match for ``capture`` across ``remotes``.

    Iterates tier-by-tier rather than first-match-wins on a single
    linear pass, so grouping does not depend on row insertion order:
    a decode-failed row sitting above its decoded sibling must not
    absorb a capture via tier 2 before the sibling's tier-1 match is
    considered.
    """
    incoming_identity = SignalIdentity(
        decoded_fingerprint=capture.decoded_fingerprint,
        byte_hash=capture.byte_hash,
        sl_fingerprint=capture.sl_fingerprint,
    )
    # Tier 1 first
    tier1 = _scan(capture, remotes, incoming_identity, target_tier=1)
    if tier1.signal is not None:
        return tier1
    # Then tier 2
    tier2 = _scan(capture, remotes, incoming_identity, target_tier=2)
    if tier2.signal is not None:
        return tier2
    # Finally tier 3
    return _scan(capture, remotes, incoming_identity, target_tier=3)


def _scan(
    capture: NormalizedSignal,
    remotes: list[UnknownRemote],
    incoming: SignalIdentity,
    *,
    target_tier: int,
) -> MatchResult:
    """Walk remotes at exactly ``target_tier``; return the first match."""
    for remote in remotes:
        for signal in remote.signals:
            if signal.protocol_label != capture.protocol_label:
                continue
            candidate = SignalIdentity(
                decoded_fingerprint=signal.decoded_fingerprint,
                byte_hash=signal.byte_hash,
                sl_fingerprint=signal.fingerprint,
            )
            tier = candidate.match_tier(incoming)
            if tier == target_tier:
                return MatchResult(remote=remote, signal=signal, tier=target_tier)
    return MatchResult(remote=None, signal=None, tier=None)
