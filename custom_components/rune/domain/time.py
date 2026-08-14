"""Time helpers — pure Python, no HA imports.

The point of these helpers is twofold:

1. Single source of truth for "what does an ISO timestamp look like in
   RUNE?" so every record in every store is consistent.
2. Single source of truth for "where does monotonic time come from?" so
   tests can inject a frozen clock without monkey-patching modules.
"""
from __future__ import annotations

from datetime import UTC, datetime
from time import monotonic as _system_monotonic


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a 'Z' suffix.

    Always UTC, always with explicit timezone, always millisecond-free
    (second resolution). Persisted on every model that carries a
    ``created_at`` / ``updated_at`` field.
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def monotonic_seconds() -> float:
    """Monotonic wall clock in seconds.

    Always use this for measuring elapsed time inside the domain. Never
    call ``time.monotonic()`` directly — tests can stub this function.
    """
    return _system_monotonic()


def parse_iso(timestamp: str) -> datetime:
    """Parse an RUNE ISO timestamp back to a ``datetime``.

    Raises ``ValueError`` for malformed input. The parsed datetime is
    always timezone-aware (UTC).
    """
    if timestamp.endswith("Z"):
        timestamp = timestamp[:-1] + "+00:00"
    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed
