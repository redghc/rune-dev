"""Receiver port — listen for incoming signals.

The sniffer engine wires one ``ReceiverPort`` per subscribed receiver
entity. Each port owns its subscription lifecycle: ``start_listening``
returns an unsubscribe callable that the sniffer calls to detach.

Captures flow as :class:`CapturedPulse` records — the normalized form
the matcher consumes (raw timings + optional protocol metadata). The
``receiver_entity_id`` is attached so downstream code can apply receiver
scope.
"""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Protocol

from custom_components.rune.domain.enums import (
    ReceiverSourceKind,
    SignalCategory,
    SignalTransport,
)


@dataclass(frozen=True)
class CapturedPulse:
    """A single pulse train received from hardware.

    The receiver adapter populates ``raw_timings`` always. The optional
    fields let the matcher upgrade to tier-1 (decoded) identity when the
    receiver decodes the protocol natively.
    """

    receiver_entity_id: str
    signal_category: SignalCategory
    raw_timings: tuple[int, ...]
    protocol_label: str | None = None
    code_hex: str | None = None
    decoded_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the wire format the SPA's Learn flow expects.

        Mirrors the shape the Lit panel reads in
        ``LearnResult.captured`` — ``protocol_label`` (when the receiver
        decoded the protocol natively), ``signal_category`` (transport /
        encoding / carrier), and ``payload`` carrying the raw timings.
        Decoded-hex / fingerprint fields are layered in when populated
        so the SPA can upgrade to a tier-1 identity if it wants to.
        """
        payload: dict[str, Any] = {"raw_timings": list(self.raw_timings)}
        if self.code_hex is not None:
            payload["decoded_hex"] = self.code_hex
        if self.decoded_fingerprint is not None:
            payload["decoded_fingerprint"] = self.decoded_fingerprint
        return {
            "protocol_label": self.protocol_label,
            "signal_category": {
                "transport": str(self.signal_category.transport),
                "encoding": str(self.signal_category.encoding),
                "carrier_frequency_hz": self.signal_category.carrier_frequency_hz,
            },
            "payload": payload,
        }


CaptureCallback = Callable[[CapturedPulse], Coroutine[None, None, None]]


class ReceiverPort(Protocol):
    """One hardware family's receiver for one transport."""

    transport: SignalTransport
    source_kind: ReceiverSourceKind
    receiver_entity_id: str

    @property
    def is_available(self) -> bool:
        """True when the underlying entity is loaded and reachable."""
        ...

    async def start_listening(self, on_capture: CaptureCallback) -> Callable[[], None]:
        """Begin delivering captures to ``on_capture``.

        Returns an unsubscribe callable. Implementations MUST guarantee
        the callback runs on the HA event loop (use ``hass.async_create_task``
        or ``hass.async_run_hass_job`` for blocking I/O).
        """
        ...

    async def stop_listening(self) -> None:
        """Detach any active subscription and release resources."""
        ...
