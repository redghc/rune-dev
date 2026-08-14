"""Tests for the power monitor adapter."""
from __future__ import annotations

import pytest

from custom_components.rune.adapters.power_monitor import (
    InMemoryPowerMonitor,
    classify_reading,
)
from custom_components.rune.ports.power_monitor import PowerReading, PowerVerdict


class TestClassifyReading:
    def test_high_wattage_is_on(self) -> None:
        assert classify_reading(watts=10, on_above_w=3.0, off_below_w=1.0) == PowerVerdict.ON

    def test_low_wattage_is_off(self) -> None:
        assert classify_reading(watts=0.5, on_above_w=3.0, off_below_w=1.0) == PowerVerdict.OFF

    def test_in_between_is_unknown(self) -> None:
        assert classify_reading(watts=2.0, on_above_w=3.0, off_below_w=1.0) == PowerVerdict.UNKNOWN

    def test_none_is_unknown(self) -> None:
        assert classify_reading(watts=None, on_above_w=3.0, off_below_w=1.0) == PowerVerdict.UNKNOWN


class TestInMemoryPowerMonitor:
    @pytest.mark.asyncio
    async def test_inject_emits_verdict(self) -> None:
        monitor = InMemoryPowerMonitor(device_id="dev-1")
        verdicts: list[PowerReading] = []

        def _cb(reading: PowerReading) -> None:
            verdicts.append(reading)

        monitor.start(_cb)
        monitor.inject(watts=10)
        assert len(verdicts) == 1
        assert verdicts[0].verdict == PowerVerdict.ON

    @pytest.mark.asyncio
    async def test_no_verdict_when_state_unchanged(self) -> None:
        monitor = InMemoryPowerMonitor(device_id="dev-1")
        verdicts: list[PowerReading] = []

        def _cb(reading: PowerReading) -> None:
            verdicts.append(reading)

        monitor.start(_cb)
        monitor.inject(watts=10)
        monitor.inject(watts=10)
        assert len(verdicts) == 1

    @pytest.mark.asyncio
    async def test_stop_unsubscribes(self) -> None:
        monitor = InMemoryPowerMonitor(device_id="dev-1")
        verdicts: list[PowerReading] = []

        def _cb(reading: PowerReading) -> None:
            verdicts.append(reading)

        stop = monitor.start(_cb)
        stop()
        monitor.inject(watts=10)
        assert verdicts == []

    @pytest.mark.asyncio
    async def test_debounce(self) -> None:
        class _Clock:
            def __init__(self) -> None:
                self.value = 0.0

            def __call__(self) -> float:
                return self.value

            def advance(self, seconds: float) -> None:
                self.value += seconds

        clock = _Clock()
        monitor = InMemoryPowerMonitor(
            device_id="dev-1",
            debounce_seconds=2.0,
            monotonic=clock,
        )
        verdicts: list[PowerReading] = []

        def _cb(reading: PowerReading) -> None:
            verdicts.append(reading)

        monitor.start(_cb)
        monitor.inject(watts=10)
        clock.advance(0.5)  # within debounce
        monitor.inject(watts=0.5)
        # The OFF verdict is suppressed by debounce.
        assert len(verdicts) == 1

        clock.advance(3.0)  # past debounce
        monitor.inject(watts=0.5)
        assert len(verdicts) == 2
        assert verdicts[1].verdict == PowerVerdict.OFF

    def test_is_available_always_true(self) -> None:
        assert InMemoryPowerMonitor(device_id="d").is_available is True

    def test_last_reading_property(self) -> None:
        monitor = InMemoryPowerMonitor(device_id="dev-1")
        monitor.inject(watts=10)
        assert monitor.last_reading is not None
        assert monitor.last_reading.watts == 10
