"""Tests for ``BroadlinkRFCaptureProvider``.

The provider drives the Broadlink two-phase sweep + capture flow
behind the orchestrator's one-shot ``start → wait → stop`` contract.
We exercise that bridge with two fixtures:

- ``FakeBroadlinkAPI`` — implements the methods
  ``BroadlinkRFReceiver`` invokes (``sweep_frequency``,
  ``check_frequency``, ``find_rf_packet``, ``check_data``,
  ``cancel_sweep_frequency``) so we don't need real hardware.
- ``FakeHass`` — minimal state + data; matches the shape the
  ``broadlink_rf`` adapter expects.

Tests cover:
- ``is_available`` returns False when ``device_api`` is missing
  (the WS handler currently passes None).
- ``is_available`` returns True when a live API is bound.
- ``async_start_capture`` raises ``CaptureProviderUnavailableError``
  with a clear "device_api not configured" message when the API
  is missing.
- ``async_wait_for_signal`` runs sweep + capture inline and returns
  a populated ``CapturedPulse`` with ``b64_packet`` set.
- Calling ``async_wait_for_signal`` a second time returns the cached
  pulse (no second sweep).
- ``async_stop_capture`` is a no-op (RF capture is on-demand).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

import pytest

from custom_components.rune.adapters.capture.broadlink_rf import (
    BroadlinkRFCaptureProvider,
)
from custom_components.rune.domain.enums import (
    SignalCategory,
    SignalEncoding,
    SignalTransport,
)
from custom_components.rune.domain.errors import (
    CaptureProviderUnavailableError,
)
from custom_components.rune.ports.receiver import CapturedPulse


class FakeHass:
    def __init__(self) -> None:
        self.states: dict[str, Any] = {}
        self.data: dict[str, Any] = {}


@dataclass
class FakeBroadlinkAPI:
    """Stands in for the Broadlink ``device_api`` object.

    The RF adapter calls ``sweep_frequency`` / ``check_frequency``
    first, then ``find_rf_packet`` / ``check_data``. We expose
    configurable hooks so each test can script the flow.
    """

    sweep_delay_s: float = 0.0
    find_delay_s: float = 0.0
    frequency_mhz: float = 433.92
    packet: bytes = b"\xb2\x01\x04\x01\x02\x03\x04"
    capture_result: CapturedPulse | None = None
    raise_on_sweep: Exception | None = None
    raise_on_capture: Exception | None = None
    sweep_called: int = 0
    find_called: int = 0
    check_data_calls: int = 0

    async def sweep_frequency(self) -> None:
        self.sweep_called += 1
        if self.raise_on_sweep is not None:
            raise self.raise_on_sweep
        if self.sweep_delay_s:
            await asyncio.sleep(self.sweep_delay_s)

    async def check_frequency(self) -> tuple[bool, float]:
        # Return the configured frequency on the first call.
        return True, self.frequency_mhz

    async def cancel_sweep_frequency(self) -> None:
        return None

    async def find_rf_packet(self, _frequency_mhz: float | None) -> None:
        self.find_called += 1
        if self.raise_on_capture is not None:
            raise self.raise_on_capture
        if self.find_delay_s:
            await asyncio.sleep(self.find_delay_s)

    async def check_data(self) -> bytes:
        self.check_data_calls += 1
        return self.packet


class TestBroadlinkRFCaptureProvider:
    @pytest.mark.asyncio
    async def test_is_available_false_without_device_api(self) -> None:
        provider = BroadlinkRFCaptureProvider(
            FakeHass(), "remote.broadlink", device_api=None
        )
        assert provider.is_available is False

    @pytest.mark.asyncio
    async def test_is_available_true_with_device_api(self) -> None:
        provider = BroadlinkRFCaptureProvider(
            FakeHass(), "remote.broadlink", device_api=FakeBroadlinkAPI()
        )
        assert provider.is_available is True

    @pytest.mark.asyncio
    async def test_start_without_api_raises(self) -> None:
        provider = BroadlinkRFCaptureProvider(
            FakeHass(), "remote.broadlink", device_api=None
        )
        with pytest.raises(CaptureProviderUnavailableError) as info:
            await provider.async_start_capture(timeout_s=1.0)
        assert "device_api" in str(info.value).lower()
        assert "remote.broadlink" in str(info.value)

    @pytest.mark.asyncio
    async def test_wait_returns_captured_pulse_with_b64(self) -> None:
        api = FakeBroadlinkAPI()
        provider = BroadlinkRFCaptureProvider(
            FakeHass(), "remote.broadlink", device_api=api
        )
        await provider.async_start_capture(timeout_s=5.0)
        pulse = await provider.async_wait_for_signal(timeout_s=5.0)
        assert pulse is not None
        # Carrier derived from API frequency.
        assert pulse.signal_category.transport is SignalTransport.RF
        assert pulse.signal_category.encoding is SignalEncoding.RAW_TIMINGS
        assert pulse.signal_category.carrier_frequency_hz == int(433.92 * 1_000_000)
        # b64 packet surfaces so the SPA can build a resendable
        # ``b64:<payload>`` PulseCommand.
        assert pulse.b64_packet is not None
        assert pulse.raw_timings  # non-empty
        assert api.sweep_called == 1
        assert api.find_called == 1

    @pytest.mark.asyncio
    async def test_wait_caches_result(self) -> None:
        """A second ``wait_for_signal`` must NOT trigger a second
        sweep — the user already pressed the button once."""
        api = FakeBroadlinkAPI()
        provider = BroadlinkRFCaptureProvider(
            FakeHass(), "remote.broadlink", device_api=api
        )
        await provider.async_start_capture(timeout_s=5.0)
        first = await provider.async_wait_for_signal(timeout_s=5.0)
        second = await provider.async_wait_for_signal(timeout_s=5.0)
        assert first is second
        assert api.sweep_called == 1

    @pytest.mark.asyncio
    async def test_wait_returns_none_when_sweep_fails(self) -> None:
        """Hardware failures during sweep must surface as ``None``
        (timeout-like state) rather than a raw exception, so the
        orchestrator can render a clean "no signal" UI state."""
        from custom_components.rune.domain.errors import CaptureError

        api = FakeBroadlinkAPI(raise_on_sweep=CaptureError("broadlink offline"))
        provider = BroadlinkRFCaptureProvider(
            FakeHass(), "remote.broadlink", device_api=api
        )
        await provider.async_start_capture(timeout_s=5.0)
        result = await provider.async_wait_for_signal(timeout_s=5.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_stop_is_noop(self) -> None:
        provider = BroadlinkRFCaptureProvider(
            FakeHass(), "remote.broadlink", device_api=FakeBroadlinkAPI()
        )
        await provider.async_start_capture(timeout_s=1.0)
        await provider.async_stop_capture()
        # After stop, ``wait_for_signal`` refuses to run again.
        with pytest.raises(RuntimeError, match="before async_start_capture"):
            await provider.async_wait_for_signal(timeout_s=0.05)
