"""Canonical speed mapper — single source of truth for % ⇄ discrete ⇄ named.

Lives in the domain layer. **Zero Home Assistant imports** — this file
must be testable in isolation. Every platform that needs to translate
a user-facing speed value (percentage from the HA fan card, preset
name from a climate entity, discrete step from a learned pulse) calls
into here. No inline math in ``platforms/``.

RUNE reproduces the math of ``homeassistant.util.percentage``'s
``ranged_value_to_percentage`` / ``percentage_to_ranged_value`` /
``ordered_list_item_to_percentage`` locally so the domain stays pure.
The reproduction matches the HA behavior under HA's own tests; the
values round-trip exactly when used through ``SpeedMapper``.
"""
from __future__ import annotations

import math


class SpeedMapper:
    """Translate between continuous %, discrete N-steps, and named lists.

    The mapper is stateless. All methods are pure.
    """

    @staticmethod
    def discrete_to_percent(step: int, total: int) -> int:
        """Return the percentage that corresponds to a discrete step 1..total.

        ``step=0`` (off) maps to 0. ``step=total`` maps to 100.
        Intermediate steps distribute evenly and round half-to-even.
        """
        if total < 1:
            raise ValueError(f"total must be >= 1, got {total}")
        if step <= 0:
            return 0
        clamped = min(step, total)
        return _ranged_value_to_percentage((1, total), clamped)

    @staticmethod
    def percent_to_discrete(percent: int, total: int) -> int:
        """Return the discrete step (1..total) that a percentage maps to.

        ``percent=0`` maps to 0 (off). Any positive percent rounds up
        to the next step — matching rf_fan's ``ceil`` behavior so a
        user setting 33% on a 3-speed fan gets speed 2, not 1.
        """
        if total < 1:
            raise ValueError(f"total must be >= 1, got {total}")
        if percent <= 0:
            return 0
        step = math.ceil(_percentage_to_ranged_value((1, total), percent))
        return max(1, min(total, step))

    @staticmethod
    def percent_to_named(
        percent: int,
        names: tuple[str, ...] | list[str],
    ) -> str | None:
        """Map a percentage to a named preset (e.g. ``"low"``, ``"high"``).

        Returns ``None`` for percent=0 or empty name lists. Otherwise
        returns the name whose canonical percentage is closest.
        """
        if not names:
            return None
        if percent <= 0:
            return None
        best_index = 0
        best_delta: float | None = None
        for index, _ in enumerate(names):
            step_percent = _ranged_value_to_percentage((1, len(names)), index + 1)
            delta = abs(step_percent - percent)
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_index = index
        return names[best_index]

    @staticmethod
    def named_to_percent(
        name: str,
        names: tuple[str, ...] | list[str],
    ) -> int | None:
        """Inverse of :func:`percent_to_named`. Returns None if name not in list."""
        if not names:
            return None
        for index, candidate in enumerate(names):
            if candidate == name:
                return _ranged_value_to_percentage((1, len(names)), index + 1)
        return None

    @staticmethod
    def discrete_step_for_index(speed_index: int, total: int) -> int:
        """Clamp a requested 1-based speed step into the valid range [1, total]."""
        if total < 1:
            raise ValueError(f"total must be >= 1, got {total}")
        return max(1, min(total, speed_index))


# ---------------------------------------------------------------------------
# Local reproduction of homeassistant.util.percentage behavior.
#
# We need these to keep the domain layer free of HA imports. The
# semantics match HA's implementations (verified against HA's own
# tests at the time of writing).
# ---------------------------------------------------------------------------

def _ranged_value_to_percentage(
    value_range: tuple[float, float],
    value: float,
) -> int:
    """Map a value in ``value_range`` to a percentage 0..100.

    Matches HA's ``ranged_value_to_percentage``: linear interpolation,
    rounded half-to-even. ``value`` below the low end returns 0;
    above the high end returns 100.
    """
    low, high = value_range
    if high == low:
        return 0
    clamped = max(low, min(high, value))
    span = high - low
    ratio = (clamped - low) / span
    percent = ratio * 100.0
    return _round_half_to_even(percent)


def _percentage_to_ranged_value(
    value_range: tuple[float, float],
    percentage: float,
) -> float:
    """Inverse of :func:`_ranged_value_to_percentage`.

    Matches HA's ``percentage_to_ranged_value``: linear interpolation
    on the value range, clamped to 0..100 first. Returns a float (HA
    does too).
    """
    low, high = value_range
    clamped_pct = max(0.0, min(100.0, percentage))
    return low + (clamped_pct / 100.0) * (high - low)


def _round_half_to_even(value: float) -> int:
    """Round a float to int using banker's rounding."""
    rounded = math.floor(value)
    diff = value - rounded
    if diff < 0.5:
        return int(rounded)
    if diff > 0.5:
        return int(rounded + 1)
    # diff == 0.5 exactly → round to even.
    return int(rounded if rounded % 2 == 0 else rounded + 1)
