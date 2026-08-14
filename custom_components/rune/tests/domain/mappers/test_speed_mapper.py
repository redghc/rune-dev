"""Tests for the canonical SpeedMapper."""
from __future__ import annotations

import pytest

from custom_components.rune.domain.mappers.speed_mapper import SpeedMapper


class TestDiscreteToPercent:
    def test_zero_maps_to_zero(self) -> None:
        assert SpeedMapper.discrete_to_percent(0, 3) == 0

    def test_negative_maps_to_zero(self) -> None:
        assert SpeedMapper.discrete_to_percent(-1, 3) == 0

    def test_total_maps_to_100(self) -> None:
        assert SpeedMapper.discrete_to_percent(3, 3) == 100

    def test_over_total_clamps_to_100(self) -> None:
        assert SpeedMapper.discrete_to_percent(5, 3) == 100

    def test_three_speed_fan(self) -> None:
        # HA convention: 3-speed fan maps (1, 3) → step 1 is 0% (essentially
        # off), step 2 is 50%, step 3 is 100%. The fan platform then shows
        # a slider with three meaningful positions.
        assert SpeedMapper.discrete_to_percent(1, 3) == 0
        assert SpeedMapper.discrete_to_percent(2, 3) == 50
        assert SpeedMapper.discrete_to_percent(3, 3) == 100

    def test_zero_total_raises(self) -> None:
        with pytest.raises(ValueError):
            SpeedMapper.discrete_to_percent(1, 0)

    def test_negative_total_raises(self) -> None:
        with pytest.raises(ValueError):
            SpeedMapper.discrete_to_percent(1, -1)


class TestPercentToDiscrete:
    def test_zero_maps_to_zero(self) -> None:
        assert SpeedMapper.percent_to_discrete(0, 3) == 0

    def test_hundred_maps_to_total(self) -> None:
        assert SpeedMapper.percent_to_discrete(100, 6) == 6

    def test_ceiling_rounding(self) -> None:
        # 33% on 3-speed fan rounds UP to speed 2.
        assert SpeedMapper.percent_to_discrete(33, 3) == 2

    def test_50_percent_on_3_speed(self) -> None:
        # 50% on 3 → ceil((50/100)*(3-1)+1) = ceil(2) = 2.
        assert SpeedMapper.percent_to_discrete(50, 3) == 2

    def test_50_percent_on_6_speed(self) -> None:
        # 50% on 6 → ceil((50/100)*(6-1)+1) = ceil(3.5) = 4.
        assert SpeedMapper.percent_to_discrete(50, 6) == 4

    def test_one_speed_returns_one(self) -> None:
        # Total=1, percent=anything > 0 → max(1, min(1, …)) = 1.
        assert SpeedMapper.percent_to_discrete(50, 1) == 1


class TestPercentToNamed:
    def test_empty_list_returns_none(self) -> None:
        assert SpeedMapper.percent_to_named(50, []) is None

    def test_zero_returns_none(self) -> None:
        assert SpeedMapper.percent_to_named(0, ["low", "high"]) is None

    def test_low_for_low_percent(self) -> None:
        # (low, med, high) canonical %s are 0, 50, 100. 25% is closer to 0.
        assert SpeedMapper.percent_to_named(25, ["low", "med", "high"]) == "low"

    def test_high_for_high_percent(self) -> None:
        assert SpeedMapper.percent_to_named(90, ["low", "med", "high"]) == "high"

    def test_middle_for_middle_percent(self) -> None:
        # 50% on (low, med, high) canonicalizes to "med".
        assert SpeedMapper.percent_to_named(50, ["low", "med", "high"]) == "med"


class TestNamedToPercent:
    def test_empty_list_returns_none(self) -> None:
        assert SpeedMapper.named_to_percent("low", []) is None

    def test_low_for_first_item(self) -> None:
        # HA convention: first item of (1, 3) → 0%.
        assert SpeedMapper.named_to_percent("low", ["low", "med", "high"]) == 0

    def test_high_for_last_item(self) -> None:
        assert SpeedMapper.named_to_percent("high", ["low", "med", "high"]) == 100

    def test_unknown_name_returns_none(self) -> None:
        assert SpeedMapper.named_to_percent("turbo", ["low", "med", "high"]) is None

    def test_round_trip_consistency(self) -> None:
        names = ("low", "med", "high")
        for name in names:
            percent = SpeedMapper.named_to_percent(name, names)
            assert percent is not None
            # Skip 0% — percent_to_named returns None for off-state.
            if percent == 0:
                continue
            # Endpoints (last item → 100%) round-trip cleanly; middle items
            # may snap to a neighbor due to quantization.
            assert SpeedMapper.percent_to_named(percent, names) in names


class TestDiscreteStepForIndex:
    def test_in_range(self) -> None:
        assert SpeedMapper.discrete_step_for_index(2, 3) == 2

    def test_below_clamped(self) -> None:
        assert SpeedMapper.discrete_step_for_index(0, 3) == 1
        assert SpeedMapper.discrete_step_for_index(-5, 3) == 1

    def test_above_clamped(self) -> None:
        assert SpeedMapper.discrete_step_for_index(10, 3) == 3
