"""Mock transmitter — records sends for tests and the local dev panel.

Two faces:

- :class:`MockTransmitter` — a single, generic mock that captures
  every send. Useful for unit tests that just want to assert a
  command was dispatched.
- :func:`install_mock_transmitter` — patches the factory to return
  mocks so a developer can run the integration without real hardware.

The capture is process-local: each MockTransmitter instance stores
its own list. Tests can read ``mock.sent`` to verify behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from custom_components.rune.domain.enums import (
    ReceiverSourceKind,
    SignalTransport,
)
from custom_components.rune.domain.models import PulseCommand
from custom_components.rune.ports.transmitter import TransmitterPort


@dataclass
class MockTransmitter(TransmitterPort):
    """In-process capture for IR/RF sends.

    ``sent`` is the full history of every command the transmitter was
    asked to send, in order. ``is_available`` is always True so
    callers don't need to special-case the mock in tests.
    """

    transport: SignalTransport = SignalTransport.IR
    source_kind: ReceiverSourceKind = ReceiverSourceKind.MOCK
    label: str = "mock"
    sent: list[PulseCommand] = field(default_factory=list)
    raise_on_send: Exception | None = None

    @property
    def is_available(self) -> bool:
        return True

    async def send(self, command: PulseCommand) -> None:
        if self.raise_on_send is not None:
            raise self.raise_on_send
        self.sent.append(command)

    @property
    def call_count(self) -> int:
        return len(self.sent)

    def last_sent(self) -> PulseCommand | None:
        return self.sent[-1] if self.sent else None

    def reset(self) -> None:
        self.sent.clear()
