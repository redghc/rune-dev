"""Tests for the MockProvider."""
from __future__ import annotations

import pytest

from custom_components.rune.adapters.capture.providers import MockProvider
from custom_components.rune.domain.enums import (
    SignalCategory,
    SignalEncoding,
    SignalTransport,
)
from custom_components.rune.ports.receiver import CapturedPulse


def _pulse() -> CapturedPulse:
    return CapturedPulse(
        receiver_entity_id="mock.rx",
        signal_category=SignalCategory(
            transport=SignalTransport.IR,
            encoding=SignalEncoding.RAW_TIMINGS,
            carrier_frequency_hz=38_000,
        ),
        raw_timings=(100, -200),
    )


class TestMockProvider:
    @pytest.mark.asyncio
    async def test_is_available_always_true(self) -> None:
        assert MockProvider().is_available is True

    @pytest.mark.asyncio
    async def test_deliver_on_start_returns_pulse(self) -> None:
        provider = MockProvider(deliver_on_start=_pulse())
        await provider.async_start_capture(timeout_s=1.0)
        result = await provider.async_wait_for_signal(timeout_s=0.5)
        assert result is not None
        assert result.raw_timings == (100, -200)
        assert provider.started is True

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self) -> None:
        provider = MockProvider(timeout=True)
        await provider.async_start_capture(timeout_s=0.1)
        result = await provider.async_wait_for_signal(timeout_s=0.1)
        assert result is None

    @pytest.mark.asyncio
    async def test_deliver_mid_run(self) -> None:
        provider = MockProvider()
        await provider.async_start_capture(timeout_s=2.0)
        await provider.deliver(_pulse())
        result = await provider.async_wait_for_signal(timeout_s=0.5)
        assert result is not None

    @pytest.mark.asyncio
    async def test_stop_sets_flag(self) -> None:
        provider = MockProvider()
        await provider.async_stop_capture()
        assert provider.stopped is True

    def test_default_transport_is_ir(self) -> None:
        assert MockProvider().transport == SignalTransport.IR

    def test_custom_transport(self) -> None:
        provider = MockProvider(transport=SignalTransport.RF)
        assert provider.transport == SignalTransport.RF
