"""Transmitter port — send a learned pulse through hardware.

Each concrete transmitter adapter handles ONE transport (IR or RF) for
ONE hardware family (native HA, Broadlink, ESPHome, Mock). The factory
selects adapters based on the device's chosen ``transmitter_entity_id``
and the SignalCategory transport.

The port intentionally hides all encoding details. Adapters convert
the domain's :class:`~custom_components.rune.domain.models.PulseCommand`
into whatever the underlying hardware wants (raw timings for native RF,
Pronto hex for native IR, ``b64:...`` for Broadlink, JSON action for
ESPHome). Encoding lives in ``custom_components.rune.domain.encoding``
and is reused across adapters.
"""
from __future__ import annotations

from typing import Protocol

from custom_components.rune.domain.enums import ReceiverSourceKind, SignalTransport
from custom_components.rune.domain.models import PulseCommand


class TransmitterPort(Protocol):
    """One hardware family's transmitter for one transport."""

    transport: SignalTransport
    source_kind: ReceiverSourceKind  # reuses the same enum for symmetry

    @property
    def is_available(self) -> bool:
        """True when the underlying entity is loaded and reachable."""
        ...

    async def send(self, command: PulseCommand) -> None:
        """Transmit ``command`` through the hardware."""
        ...
