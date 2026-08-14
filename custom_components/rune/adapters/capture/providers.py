"""Capture providers — abstract base + test double.

The :class:`CaptureProvider` ABC defines the contract every concrete
provider implements:

- :meth:`is_available` — can we use this right now?
- :meth:`async_start_capture` — begin listening.
- :meth:`async_wait_for_signal` — return one captured pulse or None on timeout.
- :meth:`async_stop_capture` — clean up.

The :class:`MockProvider` is the test double: it lets us drive the
orchestrator through the full state machine without real hardware.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.ports.receiver import CapturedPulse


class CaptureProvider(ABC):
    """Abstract capture provider."""

    transport: SignalTransport
    name: str = "provider"
    is_available: bool = False  # subclasses set True when ready

    @abstractmethod
    async def async_start_capture(self, timeout_s: float) -> None:
        """Begin listening for a signal.

        Called once per session before :meth:`async_wait_for_signal`.
        Implementations may use ``timeout_s`` to install their own internal
        deadline; the orchestrator also enforces it externally.
        """

    @abstractmethod
    async def async_wait_for_signal(self, timeout_s: float) -> CapturedPulse | None:
        """Return one captured pulse or ``None`` if the window elapsed empty."""

    @abstractmethod
    async def async_stop_capture(self) -> None:
        """Clean up any subscription or hardware state."""


class MockProvider(CaptureProvider):
    """In-process capture provider for tests.

    Three control surfaces:

    - :attr:`deliver_on_start` — push a pulse right after start_capture.
    - :meth:`deliver` — push a pulse at any time during the wait.
    - :attr:`timeout` — when True, ``wait_for_signal`` returns None.

    Tracks every state transition so tests can assert the full
    state-machine path.
    """

    def __init__(
        self,
        *,
        transport: SignalTransport = SignalTransport.IR,
        timeout: bool = False,
        deliver_on_start: CapturedPulse | None = None,
    ) -> None:
        self.transport = transport
        self.name = "mock"
        self.is_available = True
        self._timeout = timeout
        self._deliver_on_start = deliver_on_start
        self._pulse_queue: asyncio.Queue[CapturedPulse | None] = asyncio.Queue()
        self.started = False
        self.stopped = False
        self.received_results: list[CapturedPulse | None] = []

    async def async_start_capture(self, timeout_s: float) -> None:
        self.started = True
        if self._deliver_on_start is not None:
            await self._pulse_queue.put(self._deliver_on_start)
        if self._timeout:
            # Sentinel: None means "no pulse arrived".
            await self._pulse_queue.put(None)

    async def async_wait_for_signal(self, timeout_s: float) -> CapturedPulse | None:
        try:
            result = await asyncio.wait_for(self._pulse_queue.get(), timeout=timeout_s)
        except TimeoutError:
            return None
        self.received_results.append(result)
        return result

    async def async_stop_capture(self) -> None:
        self.stopped = True

    async def deliver(self, pulse: CapturedPulse) -> None:
        """Push a pulse into the mock's queue."""
        await self._pulse_queue.put(pulse)

    async def end_with_timeout(self) -> None:
        """Tell the mock to return None on the next wait."""
        await self._pulse_queue.put(None)
