"""Clock port — abstraction over ``time``.

Two faces of "now" that the domain cares about:

- **wall clock** (``now``) — for ISO timestamps persisted on records.
- **monotonic clock** (``monotonic``) — for measuring elapsed time
  inside trigger windows, dedup windows, TX-gate delays.

Why both? Wall clock can jump (NTP corrections, DST); monotonic cannot.
Using wall clock for trigger windows would let a backward jump reset
half-finished trigger chains.

The default adapter delegates to ``custom_components.rune.domain.time``
which already wraps the stdlib. Tests inject a frozen clock via the
``monotonic`` parameter.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    """Source of timestamps and elapsed-time measurements."""

    def now(self) -> datetime:
        """Return the current wall-clock time (timezone-aware UTC)."""
        ...

    def monotonic(self) -> float:
        """Return a monotonically-increasing seconds counter."""
        ...
