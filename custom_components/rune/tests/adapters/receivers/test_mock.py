"""Tests for the in-process MockReceiver."""
from __future__ import annotations

import pytest

from custom_components.rune.adapters.receivers.mock import MockReceiver
from custom_components.rune.domain.enums import (
    ReceiverSourceKind,
    SignalEncoding,
    SignalTransport,
)


class TestMockReceiver:
    def test_initial_captures_empty(self) -> None:
        mock = MockReceiver()
        assert mock.captures == []

    def test_deliver_records_capture(self) -> None:
        mock = MockReceiver()
        mock.deliver(timings=[100, -200, 300])
        assert len(mock.captures) == 1
        pulse = mock.captures[0]
        assert pulse.raw_timings == (100, -200, 300)
        assert pulse.signal_category.transport == SignalTransport.IR

    def test_deliver_with_rf_carrier(self) -> None:
        mock = MockReceiver(transport=SignalTransport.RF)
        mock.deliver(timings=[1000, -500], frequency_hz=433_920_000)
        assert mock.captures[0].signal_category.carrier_frequency_hz == 433_920_000

    def test_multiple_delivers_accumulate(self) -> None:
        mock = MockReceiver()
        mock.deliver(timings=[1])
        mock.deliver(timings=[2])
        mock.deliver(timings=[3])
        assert len(mock.captures) == 3

    def test_is_available_always_true(self) -> None:
        assert MockReceiver().is_available is True

    def test_default_label_and_kind(self) -> None:
        mock = MockReceiver()
        assert mock.label == "mock"
        assert mock.source_kind == ReceiverSourceKind.MOCK
        assert mock.receiver_entity_id == "mock.receiver"

    @pytest.mark.asyncio
    async def test_start_then_stop(self) -> None:
        mock = MockReceiver()

        async def _cb(_pulse):  # pragma: no cover - never executed in this test
            return None

        stop = await mock.start_listening(_cb)
        # stop is a callable
        assert callable(stop)
        stop()

    @pytest.mark.asyncio
    async def test_stop_listening_clears_state(self) -> None:
        mock = MockReceiver()

        async def _cb(_pulse):  # pragma: no cover
            return None

        await mock.start_listening(_cb)
        await mock.stop_listening()
        # Should not raise.

    def test_captured_signal_category_uses_default_encoding(self) -> None:
        mock = MockReceiver()
        mock.deliver(timings=[1])
        assert mock.captures[0].signal_category.encoding == SignalEncoding.RAW_TIMINGS
