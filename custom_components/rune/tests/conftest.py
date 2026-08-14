"""Shared pytest fixtures for the RUNE test suite."""
from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _isolate_utcnow(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Freeze utcnow_iso to a known value so timestamps are deterministic.

    Domain code should not call ``datetime.now()`` directly — it calls
    ``utcnow_iso()`` from ``custom_components.rune.domain.time``. This
    fixture patches that single function, not the stdlib, so behavior is
    faithful to production.
    """
    counter = {"n": 0}
    base = "2026-08-12T20:00:00Z"

    def _frozen() -> str:
        counter["n"] += 1
        return base

    monkeypatch.setattr(
        "custom_components.rune.domain.time.utcnow_iso", _frozen
    )
    yield
