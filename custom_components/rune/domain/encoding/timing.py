"""Timing utilities for raw pulse arrays.

Two transforms live here:

- :func:`trim_idle` — drop leading/trailing gaps longer than
  ``IDLE_TRIM_US`` (the capture-time learning timeout noise).
- :func:`apply_bounded_terminator` — guarantee the array ends on a
  bounded space, applied at the transmit boundary only.

Both are pure, take a list, return a new list, never mutate input.
"""
from __future__ import annotations

from custom_components.rune.const import IDLE_TRIM_US, TERMINATOR_SPACE_US


def trim_idle(timings: list[int]) -> list[int]:
    """Drop leading and trailing gaps longer than ``IDLE_TRIM_US``.

    Captures often include long idle periods at the start and end
    (Broadlink's learning timeout, the receiver settling). Those
    desync some receivers on replay — and they're never part of the
    signal. Internal gaps are left untouched.
    """
    trimmed = [int(t) for t in timings]
    while trimmed and abs(trimmed[0]) > IDLE_TRIM_US:
        trimmed.pop(0)
    while trimmed and abs(trimmed[-1]) > IDLE_TRIM_US:
        trimmed.pop()
    return trimmed


def apply_bounded_terminator(timings: list[int]) -> list[int]:
    """Return a copy of ``timings`` ending on a bounded trailing space.

    Four rules:

    1. Empty input → empty output.
    2. Last entry is a space whose magnitude is ``<= TERMINATOR_SPACE_US``
       → unchanged.
    3. Last entry is a space whose magnitude is ``> TERMINATOR_SPACE_US``
       → clamped to ``-TERMINATOR_SPACE_US``.
    4. Last entry is a mark → a ``-TERMINATOR_SPACE_US`` space is appended.

    The bound exists because 16-bit-format emitters (Tuya, ZoSung behind
    Zigbee2MQTT) reject any timing over 65,535 us, while Broadlink RM4
    Pro firmware garbles a stream that does not END on a space. 50ms fits
    uint16 with margin AND exceeds every interior frame gap in the
    SmartIR corpus (Daikin 35ms is the largest).
    """
    if not timings:
        return []
    result = [int(t) for t in timings]
    last = result[-1]
    if last < 0:
        if abs(last) > TERMINATOR_SPACE_US:
            result[-1] = -TERMINATOR_SPACE_US
        return result
    result.append(-TERMINATOR_SPACE_US)
    return result
