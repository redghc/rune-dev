"""Tests for the CaptureOrchestrator state machine."""
from __future__ import annotations

import asyncio

import pytest

from custom_components.rune.adapters.capture.orchestrator import (
    CaptureInProgressError,
    CaptureOrchestrator,
)
from custom_components.rune.adapters.capture.providers import MockProvider
from custom_components.rune.domain.enums import (
    SignalCategory,
    SignalEncoding,
    SignalTransport,
)
from custom_components.rune.ports.receiver import CapturedPulse


def _pulse(*, timings: tuple[int, ...] = (100, -200, 300)) -> CapturedPulse:
    return CapturedPulse(
        receiver_entity_id="mock.receiver",
        signal_category=SignalCategory(
            transport=SignalTransport.IR,
            encoding=SignalEncoding.RAW_TIMINGS,
            carrier_frequency_hz=38_000,
        ),
        raw_timings=timings,
    )


class TestStartCapture:
    @pytest.mark.asyncio
    async def test_starts_when_no_session_active(self) -> None:
        orch = CaptureOrchestrator()
        provider = MockProvider(deliver_on_start=_pulse())
        await orch.start_capture(provider, "s1", timeout_s=1.0)
        assert orch.is_capturing is True
        # Wait briefly for the loop to deliver
        await asyncio.sleep(0.05)
        assert orch.is_capturing is False
        assert provider.started is True
        assert provider.stopped is True

    @pytest.mark.asyncio
    async def test_second_start_raises_while_first_running(self) -> None:
        orch = CaptureOrchestrator()
        slow_provider = MockProvider()  # no auto-deliver → stays listening
        await orch.start_capture(slow_provider, "s1", timeout_s=5.0)
        with pytest.raises(CaptureInProgressError):
            await orch.start_capture(MockProvider(), "s2", timeout_s=0.5)
        await orch.cancel_capture("s1")
        await asyncio.sleep(0.05)


class TestCaptureStateTransitions:
    @pytest.mark.asyncio
    async def test_listeners_see_each_state(self) -> None:
        orch = CaptureOrchestrator()
        provider = MockProvider(deliver_on_start=_pulse())
        states: list[str] = []

        def _on_state_change(state, _result):
            states.append(str(state))

        # Subscribe BEFORE start_capture so we don't miss LISTENING.
        orch.subscribe("s1", _on_state_change)
        await orch.start_capture(provider, "s1", timeout_s=1.0)
        await asyncio.sleep(0.1)
        assert any("listening" in s for s in states)
        assert any("captured" in s for s in states)


class TestTimeoutAndCancellation:
    @pytest.mark.asyncio
    async def test_timeout_returns_none_result(self) -> None:
        orch = CaptureOrchestrator()
        provider = MockProvider(timeout=True)
        states: list[str] = []

        def _on_state_change(state, _result):
            states.append(str(state))

        orch.subscribe("s1", _on_state_change)
        await orch.start_capture(provider, "s1", timeout_s=0.1)
        await asyncio.sleep(0.2)
        assert orch.is_capturing is False
        assert orch.get_session_result("s1") is None
        assert any("timeout" in s for s in states)

    @pytest.mark.asyncio
    async def test_cancel_stops_running_session(self) -> None:
        orch = CaptureOrchestrator()
        provider = MockProvider()
        await orch.start_capture(provider, "s1", timeout_s=5.0)
        # Yield to the loop so the _capture_loop task actually starts.
        # Without this, the task is still pending when cancel arrives.
        await asyncio.sleep(0)
        assert orch.is_capturing is True
        await orch.cancel_capture("s1")
        assert orch.is_capturing is False


class TestDeliveryToListeners:
    @pytest.mark.asyncio
    async def test_captured_pulse_delivered(self) -> None:
        orch = CaptureOrchestrator()
        provider = MockProvider(deliver_on_start=_pulse())
        delivered: list[CapturedPulse] = []

        def _on_state_change(state, result):
            if result is not None:
                delivered.append(result)

        orch.subscribe("s1", _on_state_change)
        await orch.start_capture(provider, "s1", timeout_s=1.0)
        await asyncio.sleep(0.1)
        assert len(delivered) == 1
        assert delivered[0].raw_timings == (100, -200, 300)

    @pytest.mark.asyncio
    async def test_push_during_run_delivers(self) -> None:
        orch = CaptureOrchestrator()
        provider = MockProvider()
        delivered: list[CapturedPulse] = []

        def _on_state_change(state, result):
            if result is not None:
                delivered.append(result)

        orch.subscribe("s1", _on_state_change)
        await orch.start_capture(provider, "s1", timeout_s=2.0)
        await asyncio.sleep(0.05)
        await provider.deliver(_pulse(timings=(9000, -4500)))
        await asyncio.sleep(0.1)
        assert any(p.raw_timings == (9000, -4500) for p in delivered)


class TestUnsubscribe:
    def test_unsubscribe_removes_listener(self) -> None:
        orch = CaptureOrchestrator()
        called: list[str] = []

        def _cb(state, _result):
            called.append(str(state))

        unsubscribe = orch.subscribe("s1", _cb)
        unsubscribe()
        # Internal state cleared.
        assert "s1" not in orch._listeners  # type: ignore[attr-defined]


class TestProviderUnavailable:
    @pytest.mark.asyncio
    async def test_unavailable_provider_raises(self) -> None:
        from custom_components.rune.domain.errors import (
            CaptureProviderUnavailableError,
        )

        orch = CaptureOrchestrator()
        provider = MockProvider()
        provider.is_available = False
        with pytest.raises(CaptureProviderUnavailableError) as info:
            await orch.start_capture(provider, "s1", timeout_s=0.1)
        # Message must point at the provider by name + (if known)
        # the receiver entity so the panel can show a useful hint.
        assert "mock" in str(info.value)


class TestStaleResults:
    """``_results`` lingered forever — a re-learn of the same
    ``device_id.command_key`` would instantly "succeed" with the
    previous capture's timings. ``start_capture`` must drop any
    stale result for the session id it's about to reuse."""

    @pytest.mark.asyncio
    async def test_restart_drops_stale_result(self) -> None:
        orch = CaptureOrchestrator()
        first = MockProvider(deliver_on_start=_pulse())
        await orch.start_capture(first, "s1", timeout_s=1.0)
        await asyncio.sleep(0.1)
        stale = orch.get_session_result("s1")
        assert stale is not None

        second = MockProvider(timeout=True)
        await orch.start_capture(second, "s1", timeout_s=0.2)
        # The old result must NOT leak into the new session.
        assert orch.get_session_result("s1") is None
