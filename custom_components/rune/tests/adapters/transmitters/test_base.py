"""Tests for the shared transmitter helpers."""
from __future__ import annotations

import pytest

from custom_components.rune.adapters.transmitters.base import (
    build_known_hardware_keys,
    ha_carrier_from_signal_category,
    prepare_timings,
    select_payload,
)
from custom_components.rune.const import TERMINATOR_SPACE_US
from custom_components.rune.domain.enums import (
    CommandCategory,
    SignalCategory,
    SignalTransport,
)
from custom_components.rune.domain.models import PulseCommand, PulsePayload


def _command_with_raw(timings: tuple[int, ...]) -> PulseCommand:
    return PulseCommand(
        key="k",
        label="L",
        category=CommandCategory.POWER,
        signal_category=SignalCategory.default_ir(),
        payload=PulsePayload(raw_timings=timings),
    )


class TestPrepareTimings:
    def test_returns_none_when_payload_has_no_timings(self) -> None:
        cmd = PulseCommand(
            key="k",
            label="L",
            category=CommandCategory.POWER,
            signal_category=SignalCategory.default_ir(),
            payload=PulsePayload(decoded_hex="0000"),
        )
        assert prepare_timings(cmd) is None

    def test_trims_idle_then_terminates(self) -> None:
        # Leading 60_000 us gap (learning-timeout noise), short pulses,
        # trailing 30_000 us gap. Ends on a mark, so the terminator is
        # appended after trim_idle removes the trailing gap.
        cmd = _command_with_raw((60_000, 100, -50, 100, 30_000))
        prepared = prepare_timings(cmd)
        assert prepared is not None
        # Trailing long idles removed; bounded terminator appended
        # because the trimmed array ends on a mark.
        assert 60_000 not in prepared.raw_timings
        assert 30_000 not in prepared.raw_timings
        assert prepared.raw_timings[-1] == -TERMINATOR_SPACE_US

    def test_preserves_carrier_and_repeat(self) -> None:
        cmd = PulseCommand(
            key="k",
            label="L",
            category=CommandCategory.POWER,
            signal_category=SignalCategory.default_rf(433_920_000),
            payload=PulsePayload(raw_timings=(100, -200, 300), repeat_count=2, send_count=3),
        )
        prepared = prepare_timings(cmd)
        assert prepared is not None
        assert prepared.carrier_frequency_hz == 433_920_000
        assert prepared.repeat_count == 2
        assert prepared.send_count == 3

    def test_ends_on_mark_appends_terminator(self) -> None:
        cmd = _command_with_raw((100,))
        prepared = prepare_timings(cmd)
        assert prepared is not None
        assert prepared.raw_timings == [100, -TERMINATOR_SPACE_US]

    def test_ends_on_short_space_unchanged(self) -> None:
        cmd = _command_with_raw((100, -500))
        prepared = prepare_timings(cmd)
        assert prepared is not None
        assert prepared.raw_timings == [100, -500]


class TestSelectPayload:
    def test_returns_same_payload(self) -> None:
        payload = PulsePayload(raw_timings=(1, -2))
        cmd = PulseCommand(
            key="k",
            label="L",
            category=CommandCategory.POWER,
            signal_category=SignalCategory.default_ir(),
            payload=payload,
        )
        assert select_payload(cmd) is payload


class TestHaCarrierFromSignalCategory:
    def test_returns_frequency_for_ir(self) -> None:
        assert (
            ha_carrier_from_signal_category(SignalTransport.IR, 38_000)
            == 38_000
        )

    def test_returns_frequency_for_rf(self) -> None:
        assert (
            ha_carrier_from_signal_category(SignalTransport.RF, 433_920_000)
            == 433_920_000
        )

    def test_zero_frequency_raises(self) -> None:
        with pytest.raises(ValueError):
            ha_carrier_from_signal_category(SignalTransport.IR, 0)


class TestBuildKnownHardwareKeys:
    def test_returns_expected_keys(self) -> None:
        keys = build_known_hardware_keys()
        assert "infrared_domain" in keys
        assert "radio_frequency_domain" in keys
        assert "broadlink_domain" in keys
        assert "esphome_domain" in keys
