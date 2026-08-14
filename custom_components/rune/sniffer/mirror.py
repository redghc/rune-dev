"""Mirror device — synthetic catalog entry that logs HA-originated TXs.

Every time RUNE sends a pulse, the mirror records:

- The device + command label that was sent.
- A "heard_by" list: which receivers echoed the signal back within
  :attr:`MIRROR_ECHO_TTL_S`.

The mirror row lives in the regular unknown-signal store but is
identified by a special remote id (:attr:`MIRROR_DEVICE_ID`) so the
sniffer's Sniffer tab can filter it out of the user-facing feed.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from custom_components.rune.const import (
    MIRROR_DEVICE_ID,
    MIRROR_DEVICE_LABEL,
    MIRROR_ECHO_TTL_S,
)
from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.domain.models import UnknownRemote
from custom_components.rune.domain.time import monotonic_seconds, utcnow_iso

_LOGGER = logging.getLogger(__name__)


@dataclass
class MirrorEntry:
    """One row in the mirror device."""

    remote_id: str
    label: str
    pulse_timings: tuple[int, ...]
    transport: SignalTransport
    carrier_frequency_hz: int
    sent_at_monotonic: float
    sent_at_iso: str
    heard_by: list[str] = field(default_factory=list)


class MirrorLog:
    """In-memory buffer of recent RUNE-originated sends.

    Entries auto-expire after :attr:`MIRROR_ECHO_TTL_S`. The sniffer
    calls :meth:`record_send` before transmitting and :meth:`record_echo`
    when an arriving capture matches a recent send.
    """

    def __init__(self, *, now_provider: Callable[[], float] = monotonic_seconds) -> None:
        self._now = now_provider
        self._entries: list[MirrorEntry] = []

    def record_send(
        self,
        *,
        device_name: str,
        command_key: str,
        timings: tuple[int, ...],
        transport: SignalTransport,
        carrier_frequency_hz: int,
    ) -> None:
        """Mark a TX as in-flight so its echo can be claimed later."""
        self._purge_expired()
        self._entries.append(
            MirrorEntry(
                remote_id=MIRROR_DEVICE_ID,
                label=f"{device_name} / {command_key}",
                pulse_timings=timings,
                transport=transport,
                carrier_frequency_hz=carrier_frequency_hz,
                sent_at_monotonic=self._now(),
                sent_at_iso=utcnow_iso(),
            )
        )

    def record_echo(self, *, receiver_entity_id: str, timings: tuple[int, ...]) -> bool:
        """Match an incoming capture against recent sends.

        Returns True if the capture was claimed as an echo (and should
        be swallowed by the sniffer). Returns False if no match.
        """
        self._purge_expired()
        for entry in self._entries:
            if self._is_echo_of(entry, timings):
                if receiver_entity_id not in entry.heard_by:
                    entry.heard_by.append(receiver_entity_id)
                return True
        return False

    def active_entries(self) -> list[MirrorEntry]:
        """Return a snapshot of in-flight entries (for diagnostics)."""
        self._purge_expired()
        return list(self._entries)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_echo_of(self, entry: MirrorEntry, timings: tuple[int, ...]) -> bool:
        """Return True if ``timings`` is plausibly an echo of ``entry``."""
        if entry.transport == SignalTransport.RF:
            # For RF, exact match on length + close magnitude is a
            # good heuristic (jitter on RF is small).
            if len(timings) != len(entry.pulse_timings):
                return False
            if len(timings) == 0:
                return True
            mismatches = 0
            for sent, heard in zip(entry.pulse_timings, timings, strict=True):
                if sent == 0:
                    continue
                if abs(sent - heard) / max(abs(sent), 1) > 0.35:
                    mismatches += 1
            return (mismatches / len(timings)) <= 0.35
        # IR echo: usually exact match.
        return timings == entry.pulse_timings

    def _purge_expired(self) -> None:
        cutoff = self._now() - MIRROR_ECHO_TTL_S
        self._entries = [e for e in self._entries if e.sent_at_monotonic >= cutoff]


def build_mirror_remote() -> UnknownRemote:
    """Build the canonical Mirror remote (empty until entries land)."""
    return UnknownRemote(
        id=MIRROR_DEVICE_ID,
        label=MIRROR_DEVICE_LABEL,
        protocol_label=None,
        device_address=None,
        signals=[],
        dismissed=False,
        first_seen=utcnow_iso(),
        last_seen=utcnow_iso(),
        hit_count=0,
        source="sniffed",
    )


__all__ = [
    "MIRROR_DEVICE_ID",
    "MirrorEntry",
    "MirrorLog",
    "build_mirror_remote",
]
