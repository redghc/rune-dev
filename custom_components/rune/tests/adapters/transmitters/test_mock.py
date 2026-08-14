"""Tests for the in-process MockTransmitter."""
from __future__ import annotations

import pytest

from custom_components.rune.adapters.transmitters.mock import MockTransmitter
from custom_components.rune.domain.enums import (
    CommandCategory,
    SignalCategory,
    SignalTransport,
)
from custom_components.rune.domain.errors import (
    UnsupportedHardwareError,
)
from custom_components.rune.domain.models import PulseCommand, PulsePayload


def _command(key: str = "power") -> PulseCommand:
    return PulseCommand(
        key=key,
        label=key.title(),
        category=CommandCategory.POWER,
        signal_category=SignalCategory.default_ir(),
        payload=PulsePayload(raw_timings=(100, -200)),
    )


class TestMockTransmitter:
    @pytest.mark.asyncio
    async def test_send_records_command(self) -> None:
        mock = MockTransmitter()
        cmd = _command()
        await mock.send(cmd)
        assert mock.call_count == 1
        assert mock.last_sent() is cmd

    @pytest.mark.asyncio
    async def test_multiple_sends_accumulate(self) -> None:
        mock = MockTransmitter()
        await mock.send(_command("a"))
        await mock.send(_command("b"))
        await mock.send(_command("c"))
        assert [c.key for c in mock.sent] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_raise_on_send_propagates(self) -> None:
        mock = MockTransmitter(raise_on_send=UnsupportedHardwareError("nope"))
        with pytest.raises(UnsupportedHardwareError):
            await mock.send(_command())

    def test_is_available_always_true(self) -> None:
        assert MockTransmitter().is_available is True

    def test_reset_clears_history(self) -> None:
        mock = MockTransmitter()
        # Populate via sync helper since reset doesn't need async.
        mock.sent.append(_command())
        mock.reset()
        assert mock.call_count == 0
        assert mock.last_sent() is None

    def test_default_transport_is_ir(self) -> None:
        assert MockTransmitter().transport == SignalTransport.IR
