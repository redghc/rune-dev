"""Tests for the capacity guard."""
from __future__ import annotations

import pytest

from custom_components.rune.domain.enums import SignalCategory, SignalEncoding, SignalTransport
from custom_components.rune.domain.models import UnknownRemote, UnknownSignal
from custom_components.rune.sniffer.capacity import (
    CapacityLimits,
    enforce_global_cap,
    enforce_per_device_cap,
    total_signal_count,
)


def _signal(
    signal_id: str,
    *,
    hit_count: int = 5,
    last_seen: str = "2026-08-12T20:00:00Z",
) -> UnknownSignal:
    return UnknownSignal(
        id=signal_id,
        fingerprint=f"fp-{signal_id}",
        signal_category=SignalCategory(
            transport=SignalTransport.IR,
            encoding=SignalEncoding.RAW_TIMINGS,
            carrier_frequency_hz=38_000,
        ),
        raw_timings=(),
        first_seen=last_seen,
        last_seen=last_seen,
        hit_count=hit_count,
    )


def _remote(*, signals: list[UnknownSignal], remote_id: str = "r1") -> UnknownRemote:
    return UnknownRemote(
        id=remote_id,
        label=None,
        protocol_label="NEC",
        device_address="0xFB04",
        signals=signals,
    )


class TestEnforcePerDeviceCap:
    def test_under_cap_passes_through(self) -> None:
        remote = _remote(signals=[_signal("a"), _signal("b")])
        limits = CapacityLimits(max_signals_per_device=10)
        result = enforce_per_device_cap(remote, limits, now_iso="2026-08-12T20:00:00Z")
        assert result is remote or result == remote

    def test_over_cap_evicts_oldest(self) -> None:
        signals = [
            _signal(f"s{i}", last_seen=f"2026-08-{12 + i:02d}T20:00:00Z")
            for i in range(15)
        ]
        remote = _remote(signals=signals)
        limits = CapacityLimits(max_signals_per_device=5)
        result = enforce_per_device_cap(remote, limits, now_iso="2026-09-01T00:00:00Z")
        assert len(result.signals) == 5

    def test_cold_old_signals_evicted_first(self) -> None:
        # Recent cold signals + old warm signals → warm ones survive.
        signals = [
            _signal("hot_old", hit_count=100, last_seen="2025-01-01T00:00:00Z"),
            _signal("cold_new", hit_count=1, last_seen="2026-08-12T20:00:00Z"),
            _signal("warm_old", hit_count=50, last_seen="2025-06-01T00:00:00Z"),
        ]
        remote = _remote(signals=signals)
        limits = CapacityLimits(
            max_signals_per_device=2,
            evict_min_hits=5,
            evict_age_days=30,
        )
        result = enforce_per_device_cap(
            remote, limits, now_iso="2026-08-12T20:00:00Z"
        )
        # "hot_old" and "warm_old" should survive; cold_new is evicted
        # because it's the only cold AND it exceeds the cap.
        ids = {s.id for s in result.signals}
        assert "hot_old" in ids
        assert "warm_old" in ids


class TestEnforceGlobalCap:
    def test_under_cap_passes_through(self) -> None:
        remotes = [
            _remote(signals=[_signal(f"r{i}-s{j}") for j in range(2)], remote_id=f"r{i}")
            for i in range(3)
        ]
        limits = CapacityLimits(max_total_signals=10)
        result = enforce_global_cap(remotes, limits, now_iso="2026-08-12T20:00:00Z")
        assert total_signal_count(result) == 6

    def test_over_cap_drops_lowest_priority(self) -> None:
        # Build 3 remotes with 4 signals each = 12 signals. Cap at 8.
        remotes = []
        for r in range(3):
            signals_per_remote = [
                _signal(f"r{r}-s{s}", hit_count=10 + r * 5) for s in range(4)
            ]
            remotes.append(_remote(signals=signals_per_remote, remote_id=f"r{r}"))
        limits = CapacityLimits(
            max_total_signals=8,
            evict_min_hits=1,
            evict_age_days=999,
        )
        result = enforce_global_cap(remotes, limits, now_iso="2026-08-12T20:00:00Z")
        assert total_signal_count(result) == 8

    def test_invalid_limits_rejected(self) -> None:
        with pytest.raises(ValueError):
            CapacityLimits(max_signals_per_device=0)
        with pytest.raises(ValueError):
            CapacityLimits(max_total_signals=0)


class TestTotalSignalCount:
    def test_sums_across_remotes(self) -> None:
        remotes = [
            _remote(signals=[_signal(f"a{s}") for s in range(3)], remote_id="a"),
            _remote(signals=[_signal(f"b{s}") for s in range(5)], remote_id="b"),
        ]
        assert total_signal_count(remotes) == 8
