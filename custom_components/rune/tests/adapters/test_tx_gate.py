"""Tests for the TxGate."""
from __future__ import annotations

import asyncio

import pytest

from custom_components.rune.adapters.tx_gate import TxGate, TXGateConfig
from custom_components.rune.domain.enums import (
    CommandCategory,
    SignalCategory,
)
from custom_components.rune.domain.errors import TxGateTimeoutError
from custom_components.rune.domain.models import PulseCommand, PulsePayload
from custom_components.rune.sniffer.mirror import MirrorLog


class _Clock:
    """Clock that advances synchronously when the gate sleeps.

    The gate calls ``sleep(wait_s)`` to wait. We use a custom sleep
    that advances the clock by ``wait_s`` AND yields to the event loop
    once, so the gate's re-check sees the advanced time.
    """

    def __init__(self) -> None:
        self.now_value = 0.0

    def __call__(self) -> float:
        return self.now_value

    def advance(self, seconds: float) -> None:
        self.now_value += seconds


def _make_clock() -> _Clock:
    return _Clock()


async def _sleep_and_advance(clock: _Clock, wait_s: float) -> None:
    """Sleep helper for the gate that advances the clock.

    Real-time waits (asyncio.sleep) would block the test for the real
    duration; instead we advance the clock immediately and yield once
    so the gate can re-evaluate.
    """
    clock.advance(wait_s)
    await asyncio.sleep(0)


def _command(*, key: str = "k") -> PulseCommand:
    return PulseCommand(
        key=key,
        label=key,
        category=CommandCategory.POWER,
        signal_category=SignalCategory.default_ir(),
        payload=PulsePayload(raw_timings=(100, -200)),
    )


class TestTxGate:
    @pytest.mark.asyncio
    async def test_first_send_passes_immediately(self) -> None:
        clock = _make_clock()
        gate = TxGate(
            mirror=MirrorLog(now_provider=clock),
            config=TXGateConfig(),
            monotonic=clock,
            sleep=lambda s: _sleep_and_advance(clock, s),
        )
        called: list[PulseCommand] = []

        async def _sender(cmd):
            called.append(cmd)

        await gate.send(
            emitter_entity_id="remote.x",
            device_name="Bedroom fan",
            command=_command(),
            sender=_sender,
        )
        assert len(called) == 1
        assert gate.last_send_at("remote.x") == 0.0

    @pytest.mark.asyncio
    async def test_same_emitter_repeat_waits_for_gap(self) -> None:
        clock = _make_clock()
        gate = TxGate(
            mirror=MirrorLog(now_provider=clock),
            config=TXGateConfig(
                send_repeat_gap_s=0.5, emitter_stagger_gap_s=0.0, stagger_timeout_s=2.0
            ),
            monotonic=clock,
            sleep=lambda s: _sleep_and_advance(clock, s),
        )
        called: list[PulseCommand] = []

        async def _sender(cmd):
            called.append(cmd)

        await gate.send(
            emitter_entity_id="a", device_name="x", command=_command(), sender=_sender
        )
        # Clock still at 0 → second send on same emitter must wait.
        await gate.send(
            emitter_entity_id="a", device_name="x", command=_command(), sender=_sender
        )
        assert len(called) == 2
        # The wait advanced the clock by exactly send_repeat_gap_s.
        assert clock.now_value == 0.5

    @pytest.mark.asyncio
    async def test_different_emitter_waits_for_stagger(self) -> None:
        clock = _make_clock()
        gate = TxGate(
            mirror=MirrorLog(now_provider=clock),
            config=TXGateConfig(
                send_repeat_gap_s=0.0, emitter_stagger_gap_s=0.3, stagger_timeout_s=2.0
            ),
            monotonic=clock,
            sleep=lambda s: _sleep_and_advance(clock, s),
        )
        called: list[str] = []

        async def _sender(_cmd):
            called.append("sent")

        await gate.send(
            emitter_entity_id="a", device_name="x", command=_command(), sender=_sender
        )
        await gate.send(
            emitter_entity_id="b", device_name="x", command=_command(), sender=_sender
        )
        assert len(called) == 2
        # Stagger gap of 0.3 was honored.
        assert clock.now_value == 0.3

    @pytest.mark.asyncio
    async def test_mirror_entry_recorded_before_send(self) -> None:
        clock = _make_clock()
        mirror = MirrorLog(now_provider=clock)
        gate = TxGate(
            mirror=mirror,
            config=TXGateConfig(),
            monotonic=clock,
            sleep=lambda s: _sleep_and_advance(clock, s),
        )

        async def _sender(_cmd):
            pass

        await gate.send(
            emitter_entity_id="a",
            device_name="Bedroom fan",
            command=_command(key="off"),
            sender=_sender,
        )
        entries = mirror.active_entries()
        assert len(entries) == 1
        assert entries[0].label == "Bedroom fan / off"

    @pytest.mark.asyncio
    async def test_stagger_timeout_raises(self) -> None:
        clock = _make_clock()
        # A sleep that never advances the clock → gate can't meet the
        # required gap → raises TxGateTimeoutError after
        # stagger_timeout_s.
        async def _no_advance(_wait_s: float) -> None:
            await asyncio.sleep(0)

        gate = TxGate(
            mirror=MirrorLog(now_provider=clock),
            config=TXGateConfig(
                send_repeat_gap_s=0.0,
                emitter_stagger_gap_s=10.0,
                stagger_timeout_s=0.1,
            ),
            monotonic=clock,
            sleep=_no_advance,
        )

        async def _sender(_cmd):
            pass

        await gate.send(
            emitter_entity_id="a", device_name="x", command=_command(), sender=_sender
        )
        # On a different emitter, the stagger window blocks → timeout.
        with pytest.raises(TxGateTimeoutError):
            await gate.send(
                emitter_entity_id="b",
                device_name="x",
                command=_command(),
                sender=_sender,
            )

