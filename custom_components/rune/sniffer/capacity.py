"""Capacity guard for the unknown-signal catalog.

Two limits enforced:

- :attr:`SNIFER_MAX_SIGNALS_PER_DEVICE` (200 by default) — per-remote
  cap. The freshest signals stay; oldest low-hit signals are evicted.
- :attr:`SNIFER_MAX_TOTAL_SIGNALS` (20_000 by default) — global cap
  across all remotes. Same eviction policy.

Eviction policy (HAIR's, learned the hard way):

A signal is evicted when it has fewer than ``SNIFER_EVICT_MIN_HITS``
hits AND is older than ``SNIFER_EVICT_AGE_DAYS`` days. Real remotes
have a few hot buttons (high hits) and a long tail of cold buttons
(low hits); the cold tail grows without bound on a noisy RF source,
hence the cap.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from custom_components.rune.const import (
    SNIFER_EVICT_AGE_DAYS,
    SNIFER_EVICT_MIN_HITS,
    SNIFER_MAX_SIGNALS_PER_DEVICE,
    SNIFER_MAX_TOTAL_SIGNALS,
)
from custom_components.rune.domain.models import UnknownRemote, UnknownSignal
from custom_components.rune.domain.time import parse_iso


@dataclass(frozen=True)
class CapacityLimits:
    """Tunable capacity guard bounds.

    Defaults come from ``const.py``. Tests inject tighter bounds.
    """

    max_signals_per_device: int = SNIFER_MAX_SIGNALS_PER_DEVICE
    max_total_signals: int = SNIFER_MAX_TOTAL_SIGNALS
    evict_min_hits: int = SNIFER_EVICT_MIN_HITS
    evict_age_days: int = SNIFER_EVICT_AGE_DAYS

    def __post_init__(self) -> None:
        if self.max_signals_per_device <= 0:
            raise ValueError("max_signals_per_device must be positive")
        if self.max_total_signals <= 0:
            raise ValueError("max_total_signals must be positive")


def enforce_per_device_cap(
    remote: UnknownRemote,
    limits: CapacityLimits,
    *,
    now_iso: str,
) -> UnknownRemote:
    """Return a copy of ``remote`` with the per-device cap enforced.

    If the remote has more than ``limits.max_signals_per_device``
    signals, the lowest-priority ones are dropped first:

    1. Signals below the hit threshold AND older than the age
       threshold are evicted (oldest first).
    2. If still over the cap, signals are dropped oldest-first
       regardless of hits.
    """
    if len(remote.signals) <= limits.max_signals_per_device:
        return remote

    def _age_days(signal: UnknownSignal) -> float:
        try:
            delta = parse_iso(now_iso) - parse_iso(signal.last_seen)
        except ValueError:
            return 0.0
        return delta.total_seconds() / 86400.0

    def _eviction_priority(signal: UnknownSignal) -> tuple[int, float, float]:
        """Lower tuple = evicted first.

        (0, age, hit_count) — cold+old first.
        """
        is_cold = int(signal.hit_count < limits.evict_min_hits)
        is_old = int(_age_days(signal) >= limits.evict_age_days)
        evict_first = 0 if (is_cold and is_old) else 1
        return (evict_first, _age_days(signal), float(signal.hit_count))

    sorted_signals = sorted(remote.signals, key=_eviction_priority, reverse=True)
    keep = sorted_signals[: limits.max_signals_per_device]
    return UnknownRemote(
        id=remote.id,
        label=remote.label,
        protocol_label=remote.protocol_label,
        device_address=remote.device_address,
        signals=list(keep),
        dismissed=remote.dismissed,
        first_seen=remote.first_seen,
        last_seen=remote.last_seen,
        hit_count=remote.hit_count,
        source=remote.source,
    )


def enforce_global_cap(
    remotes: list[UnknownRemote],
    limits: CapacityLimits,
    *,
    now_iso: str,
) -> list[UnknownRemote]:
    """Return a copy of ``remotes`` with the global cap enforced.

    Eviction policy mirrors :func:`enforce_per_device_cap` but applied
    across remotes. Each remote keeps its existing label and address;
    only its signal list is trimmed.
    """
    total_signals = sum(len(r.signals) for r in remotes)
    if total_signals <= limits.max_total_signals:
        return list(remotes)

    # Flatten all signals with their remote context, sort by eviction
    # priority, drop the lowest.
    flat: list[tuple[UnknownRemote, UnknownSignal]] = []
    for remote in remotes:
        for signal in remote.signals:
            flat.append((remote, signal))

    def _age_days(signal: UnknownSignal) -> float:
        try:
            delta = parse_iso(now_iso) - parse_iso(signal.last_seen)
        except ValueError:
            return 0.0
        return delta.total_seconds() / 86400.0

    def _priority(item: tuple[UnknownRemote, UnknownSignal]) -> tuple[int, float, float]:
        signal = item[1]
        is_cold = int(signal.hit_count < limits.evict_min_hits)
        is_old = int(_age_days(signal) >= limits.evict_age_days)
        evict_first = 0 if (is_cold and is_old) else 1
        return (evict_first, _age_days(signal), float(signal.hit_count))

    sorted_items = sorted(flat, key=_priority, reverse=True)
    keep_count = limits.max_total_signals
    kept_signal_ids: dict[str, set[str]] = {r.id: set() for r in remotes}
    for remote, signal in sorted_items[:keep_count]:
        kept_signal_ids[remote.id].add(signal.id)

    capped_remotes: list[UnknownRemote] = []
    for remote in remotes:
        kept_signals = [s for s in remote.signals if s.id in kept_signal_ids[remote.id]]
        capped_remotes.append(
            UnknownRemote(
                id=remote.id,
                label=remote.label,
                protocol_label=remote.protocol_label,
                device_address=remote.device_address,
                signals=kept_signals,
                dismissed=remote.dismissed,
                first_seen=remote.first_seen,
                last_seen=remote.last_seen,
                hit_count=remote.hit_count,
                source=remote.source,
            )
        )
    return capped_remotes


def total_signal_count(remotes: Iterable[UnknownRemote]) -> int:
    """Helper: count every signal across every remote."""
    return sum(len(r.signals) for r in remotes)
