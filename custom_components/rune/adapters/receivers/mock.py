"""Mock receiver — records delivered captures for tests.

The mock receiver is a stand-in for any real :class:`ReceiverPort`.
It exposes ``deliver(timings)`` so tests can push synthetic captures
through the sniffer pipeline without spinning up real hardware.

Two usage patterns:

- ``mock.deliver(timings)`` directly — bypasses the receiver subscription
  entirely; useful when the test wants to inject a capture after
  the sniffer has already started.
- ``mock.start_listening(callback)`` then ``mock.deliver(timings)`` —
  exercises the full subscription path including the unsubscribe
  callable.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from custom_components.rune.domain.enums import (
    ReceiverSourceKind,
    SignalCategory,
    SignalEncoding,
    SignalTransport,
)
from custom_components.rune.ports.receiver import (
    CaptureCallback,
    CapturedPulse,
    ReceiverPort,
)


@dataclass
class MockReceiver(ReceiverPort):
    """In-process capture for IR/RF receives."""

    transport: SignalTransport = SignalTransport.IR
    source_kind: ReceiverSourceKind = ReceiverSourceKind.MOCK
    label: str = "mock"
    receiver_entity_id: str = "mock.receiver"
    captures: list[CapturedPulse] = field(default_factory=list)
    _listening: bool = field(default=False, init=False)
    _on_capture: CaptureCallback | None = field(default=None, init=False)
    _hass: Any = field(default=None, init=False)

    @property
    def is_available(self) -> bool:
        return True

    async def start_listening(self, on_capture: CaptureCallback) -> Callable[[], None]:
        self._listening = True
        self._on_capture = on_capture

        def _stop() -> None:
            self._listening = False
            self._on_capture = None

        return _stop

    async def stop_listening(self) -> None:
        self._listening = False
        self._on_capture = None

    def set_hass(self, hass: Any) -> None:
        """Attach a hass reference so ``deliver`` schedules via its event loop."""
        self._hass = hass

    def deliver(self, *, timings: list[int], frequency_hz: int = 38_000) -> None:
        """Push a synthetic capture into the mock.

        Synchronous — bypasses the receiver subscription. If
        ``start_listening`` was called, also dispatches via the
        subscription so the user callback fires.
        """
        captured = CapturedPulse(
            receiver_entity_id=self.receiver_entity_id,
            signal_category=SignalCategory(
                transport=self.transport,
                encoding=SignalEncoding.RAW_TIMINGS,
                carrier_frequency_hz=frequency_hz,
            ),
            raw_timings=tuple(int(t) for t in timings),
        )
        self.captures.append(captured)
        if self._listening and self._on_capture is not None:
            self._hass_or_loop_create_task(self._on_capture(captured))

    def _hass_or_loop_create_task(self, coro: Any) -> None:
        # For unit tests, callers iterate ``captures`` directly. For
        # integration tests, the sniffer provides a real hass whose
        # event loop we use.
        if self._hass is not None:
            self._hass.async_create_task(coro)
            return
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            loop.create_task(coro)
        else:
            # No running loop — close the coroutine to silence warnings.
            coro.close()
