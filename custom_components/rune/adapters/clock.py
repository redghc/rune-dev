"""Clock adapters — production + test implementations of ``ClockPort``.

Two adapters:

- :class:`SystemClockAdapter` — production default, delegates to the
  ``custom_components.rune.domain.time`` helpers (which themselves wrap
  stdlib ``datetime`` / ``time``).
- :class:`FrozenClockAdapter` — returns a fixed wall-clock time and
  lets tests advance the monotonic counter manually.

Both adapters are intentionally minimal — the abstraction is only as
wide as the domain actually needs.
"""
from __future__ import annotations

from datetime import UTC, datetime

from custom_components.rune.domain.time import monotonic_seconds
from custom_components.rune.ports.clock import ClockPort


class SystemClockAdapter(ClockPort):
    """Production clock adapter.

    Wall clock comes from :func:`datetime.now(UTC)`; monotonic from the
    stdlib via :func:`custom_components.rune.domain.time.monotonic_seconds`.
    """

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return monotonic_seconds()


class FrozenClockAdapter(ClockPort):
    """Test clock — fixed wall time, manually-advanced monotonic counter.

    Tests advance time by calling :meth:`advance`. The wall clock
    returned by :meth:`now` is computed from a fixed origin plus the
    elapsed monotonic, so ``now`` and ``monotonic` stay in sync — a
    trigger chain that started at ``t=0`` and got ``advance(5)`` will
    see ``now()`` move forward by 5 seconds too.
    """

    def __init__(
        self,
        *,
        origin: datetime | None = None,
    ) -> None:
        self._origin = origin or datetime(2026, 1, 1, tzinfo=UTC)
        self._monotonic_now: float = 0.0

    def now(self) -> datetime:
        from datetime import timedelta

        return self._origin + timedelta(seconds=self._monotonic_now)

    def monotonic(self) -> float:
        return self._monotonic_now

    def advance(self, seconds: float) -> None:
        """Move both clocks forward by ``seconds``."""
        if seconds < 0:
            raise ValueError(f"Cannot rewind a frozen clock: {seconds}")
        self._monotonic_now += seconds
