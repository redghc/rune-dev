"""Tests for ``NativeIRCaptureProvider``.

The provider bridges the push-style :class:`NativeIRReceiver`
subscription into the orchestrator's one-shot
``start → wait → stop`` contract. We exercise that bridge with two
fixtures:

- ``FakeNativeIRReceiver`` — pretends to be a receiver: ``start_listening``
  hands back the unsubscribe hook and stashes the capture callback so
  the test can fire pulses on demand.
- ``FakeHass`` — just enough state for ``is_available`` to peek at.

Tests cover:
- ``is_available`` resolves the receiver via the factory and reads the
  entity state.
- ``async_wait_for_signal`` returns the first pulse pushed after
  ``start_capture`` and ``None`` on timeout.
- ``async_stop_capture`` unsubscribes and drains stragglers.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

import pytest

from custom_components.rune.adapters.capture.native_ir import (
    NativeIRCaptureProvider,
)
from custom_components.rune.domain.enums import (
    SignalCategory,
    SignalEncoding,
    SignalTransport,
)
from custom_components.rune.ports.receiver import (
    CaptureCallback,
    CapturedPulse,
    ReceiverPort,
)


class _FakeState:
    def __init__(self, state: str) -> None:
        self.state = state


class _States:
    def __init__(self, mapping: dict[str, _FakeState]) -> None:
        self._mapping = mapping

    def get(self, entity_id: str) -> _FakeState | None:
        return self._mapping.get(entity_id)


class FakeHass:
    def __init__(
        self,
        states: dict[str, _FakeState] | None = None,
        *,
        ir_receivers: list[str] | None = None,
    ) -> None:
        self.states = _States(states or {})
        self.captured: list[CapturedPulse] = []
        # ``hass.data[DOMAIN]`` — providers probe this to detect
        # entities registered with the infrared platform.
        self.data: dict[str, dict[str, object]] = {}
        if ir_receivers is not None:
            self.data["infrared"] = {entity_id: object() for entity_id in ir_receivers}

    def async_create_task(self, coro: Any) -> asyncio.Task:  # pragma: no cover - unused
        return asyncio.create_task(coro)


class FakeNativeIRReceiver(ReceiverPort):
    transport = SignalTransport.IR

    def __init__(self, available: bool = True) -> None:
        self.source_kind = None  # type: ignore[assignment]
        self.receiver_entity_id = "infrared.test"
        self._available = available
        self._on_capture: CaptureCallback | None = None
        self.started = False
        self.stopped = False
        self._unsubscribed = 0

    @property
    def is_available(self) -> bool:
        return self._available

    async def start_listening(self, on_capture: CaptureCallback) -> Callable[[], None]:
        self._on_capture = on_capture
        self.started = True

        def _stop() -> None:
            self._unsubscribed += 1
            self.stopped = True
            self._on_capture = None

        return _stop

    async def stop_listening(self) -> None:  # pragma: no cover - unused
        pass

    async def fire(self, pulse: CapturedPulse) -> None:
        if self._on_capture is None:
            raise AssertionError("fire() called without an active subscription")
        await self._on_capture(pulse)


def _pulse(carrier: int = 38_000, timings: tuple[int, ...] = (100, -200)) -> CapturedPulse:
    return CapturedPulse(
        receiver_entity_id="infrared.test",
        signal_category=SignalCategory(
            transport=SignalTransport.IR,
            encoding=SignalEncoding.RAW_TIMINGS,
            carrier_frequency_hz=carrier,
        ),
        raw_timings=timings,
    )


@pytest.fixture
def fake_receiver(monkeypatch: pytest.MonkeyPatch) -> FakeNativeIRReceiver:
    """Patch the receivers factory + IR registry probe so the
    provider picks up our fake without needing HA installed.

    The production probe (``_is_ir_receiver``) calls into
    ``homeassistant.components.infrared``, which isn't on the test
    path. We swap it for a local function that reads ``hass.data`` —
    matches the production contract, no HA dependency.
    """
    from custom_components.rune.adapters.capture import native_ir as native_ir_mod

    receiver = FakeNativeIRReceiver()
    monkeypatch.setattr(native_ir_mod, "select_receiver", lambda *_a, **_kw: receiver)

    def _is_ir(hass: Any, entity_id: str) -> bool:
        registry = getattr(hass, "data", {}).get("infrared", {})
        return entity_id in registry

    monkeypatch.setattr(native_ir_mod, "_is_ir_receiver", _is_ir)
    return receiver


class TestNativeIRCaptureProvider:
    @pytest.mark.asyncio
    async def test_is_available_probes_entity_and_factory(
        self, fake_receiver: FakeNativeIRReceiver
    ) -> None:
        hass = FakeHass(
            states={"infrared.test": _FakeState("idle")},
            ir_receivers=["infrared.test"],
        )
        provider = NativeIRCaptureProvider(hass, "infrared.test")
        assert provider.is_available is True

    @pytest.mark.asyncio
    async def test_is_available_false_when_entity_unavailable(
        self, fake_receiver: FakeNativeIRReceiver
    ) -> None:
        fake_receiver._available = False
        hass = FakeHass(
            states={"infrared.test": _FakeState("idle")},
            ir_receivers=["infrared.test"],
        )
        provider = NativeIRCaptureProvider(hass, "infrared.test")
        assert provider.is_available is False

    @pytest.mark.asyncio
    async def test_is_available_false_when_not_in_ir_registry(
        self, fake_receiver: FakeNativeIRReceiver
    ) -> None:
        # The factory says yes, but the entity isn't in HA's infrared
        # registry — ``infrared.async_subscribe_receiver`` would raise
        # ``receiver_not_found``. The probe catches that early.
        hass = FakeHass(
            states={"infrared.test": _FakeState("idle")},
            ir_receivers=[],
        )
        provider = NativeIRCaptureProvider(hass, "infrared.test")
        assert provider.is_available is False

    @pytest.mark.asyncio
    async def test_start_then_wait_returns_first_pulse(
        self, fake_receiver: FakeNativeIRReceiver
    ) -> None:
        hass = FakeHass(
            states={"infrared.test": _FakeState("idle")},
            ir_receivers=["infrared.test"],
        )
        provider = NativeIRCaptureProvider(hass, "infrared.test")
        await provider.async_start_capture(timeout_s=1.0)
        # Fire the pulse asynchronously — the subscription callback
        # queues it for ``async_wait_for_signal`` to pull.
        await fake_receiver.fire(_pulse())
        result = await provider.async_wait_for_signal(timeout_s=1.0)
        assert result is not None
        assert result.raw_timings == (100, -200)
        await provider.async_stop_capture()

    @pytest.mark.asyncio
    async def test_wait_times_out_when_no_signal(
        self, fake_receiver: FakeNativeIRReceiver
    ) -> None:
        hass = FakeHass(
            states={"infrared.test": _FakeState("idle")},
            ir_receivers=["infrared.test"],
        )
        provider = NativeIRCaptureProvider(hass, "infrared.test")
        await provider.async_start_capture(timeout_s=0.1)
        result = await provider.async_wait_for_signal(timeout_s=0.1)
        assert result is None
        await provider.async_stop_capture()

    @pytest.mark.asyncio
    async def test_stop_unsubscribes_and_drains_stragglers(
        self, fake_receiver: FakeNativeIRReceiver
    ) -> None:
        hass = FakeHass(
            states={"infrared.test": _FakeState("idle")},
            ir_receivers=["infrared.test"],
        )
        provider = NativeIRCaptureProvider(hass, "infrared.test")
        await provider.async_start_capture(timeout_s=0.5)
        # Two pulses arrive before anyone calls wait_for_signal.
        await fake_receiver.fire(_pulse(timings=(1,)))
        await fake_receiver.fire(_pulse(timings=(2,)))
        result = await provider.async_wait_for_signal(timeout_s=0.5)
        assert result is not None
        assert result.raw_timings == (1,)
        await provider.async_stop_capture()
        assert fake_receiver._unsubscribed == 1
        assert fake_receiver.stopped is True
        # After stop, ``async_wait_for_signal`` refuses to run — the
        # session is closed and any drained stragglers stay drained.
        with pytest.raises(RuntimeError, match="before async_start_capture"):
            await provider.async_wait_for_signal(timeout_s=0.05)

    @pytest.mark.asyncio
    async def test_wait_without_start_raises(
        self, fake_receiver: FakeNativeIRReceiver
    ) -> None:
        hass = FakeHass(
            states={"infrared.test": _FakeState("idle")},
            ir_receivers=["infrared.test"],
        )
        provider = NativeIRCaptureProvider(hass, "infrared.test")
        with pytest.raises(RuntimeError, match="before async_start_capture"):
            await provider.async_wait_for_signal(timeout_s=0.1)

    @pytest.mark.asyncio
    async def test_start_without_available_entity_raises(
        self, fake_receiver: FakeNativeIRReceiver
    ) -> None:
        from custom_components.rune.domain.errors import (
            CaptureProviderUnavailableError,
        )

        fake_receiver._available = False
        hass = FakeHass(
            states={"infrared.test": _FakeState("idle")},
            ir_receivers=["infrared.test"],
        )
        provider = NativeIRCaptureProvider(hass, "infrared.test")
        with pytest.raises(CaptureProviderUnavailableError):
            await provider.async_start_capture(timeout_s=0.1)

    @pytest.mark.asyncio
    async def test_start_translates_receiver_not_found(
        self, monkeypatch: pytest.MonkeyPatch, fake_receiver: FakeNativeIRReceiver
    ) -> None:
        """``infrared.async_subscribe_receiver`` raises
        ``HomeAssistantError(translation_key="receiver_not_found")``
        when the entity exists but isn't an IR receiver. We must
        surface a friendly ``CaptureProviderUnavailableError``
        instead of leaking the raw HA class name."""
        from custom_components.rune.adapters.capture import native_ir as native_ir_mod
        from custom_components.rune.domain.errors import (
            CaptureProviderUnavailableError,
        )

        class _FakeHAError(Exception):
            translation_key = "receiver_not_found"

        async def _raise(*_a: Any, **_kw: Any) -> None:
            raise _FakeHAError("receiver_not_found")

        # Swap the real ``HomeAssistantError`` import with our stand-in
        # so ``_is_unknown_receiver_error`` recognises it.
        monkeypatch.setattr(native_ir_mod, "HomeAssistantError", _FakeHAError)
        fake_receiver.start_listening = _raise  # type: ignore[method-assign]
        hass = FakeHass(
            states={"infrared.test": _FakeState("idle")},
            ir_receivers=["infrared.test"],
        )
        provider = NativeIRCaptureProvider(hass, "infrared.test")
        with pytest.raises(CaptureProviderUnavailableError, match="not a registered"):
            await provider.async_start_capture(timeout_s=0.1)
