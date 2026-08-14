"""Tests for the domain enums."""
from __future__ import annotations

import pytest

from custom_components.rune.domain.enums import (
    ActionKind,
    CaptureState,
    CommandCategory,
    EntityCategory,
    ReceiverSourceKind,
    SignalCategory,
    SignalEncoding,
    SignalTransport,
    SpeedMode,
    TransmitterSourceKind,
)


class TestEntityCategory:
    def test_all_values_are_lowercase_strings(self) -> None:
        for member in EntityCategory:
            assert member.value == member.value.lower()
            assert " " not in member.value


class TestSignalCategory:
    def test_default_ir_has_38khz_carrier(self) -> None:
        category = SignalCategory.default_ir()
        assert category.transport == SignalTransport.IR
        assert category.carrier_frequency_hz == 38_000

    def test_default_rf_uses_provided_frequency(self) -> None:
        category = SignalCategory.default_rf(433_920_000)
        assert category.transport == SignalTransport.RF
        assert category.carrier_frequency_hz == 433_920_000

    def test_zero_carrier_rejected(self) -> None:
        with pytest.raises(ValueError, match="carrier_frequency_hz"):
            SignalCategory(
                transport=SignalTransport.IR,
                encoding=SignalEncoding.RAW_TIMINGS,
                carrier_frequency_hz=0,
            )

    def test_negative_carrier_rejected(self) -> None:
        with pytest.raises(ValueError, match="carrier_frequency_hz"):
            SignalCategory(
                transport=SignalTransport.RF,
                encoding=SignalEncoding.RAW_TIMINGS,
                carrier_frequency_hz=-1,
            )

    def test_with_encoding_returns_new_instance(self) -> None:
        original = SignalCategory.default_ir()
        swapped = original.with_encoding(SignalEncoding.DECODED)
        assert swapped.encoding == SignalEncoding.DECODED
        assert swapped.transport == original.transport
        assert swapped.carrier_frequency_hz == original.carrier_frequency_hz
        assert swapped is not original


class TestSpeedMode:
    def test_three_modes_defined(self) -> None:
        assert {m.value for m in SpeedMode} == {"percentage", "discrete", "hybrid"}


class TestActionKind:
    def test_all_kinds_listed(self) -> None:
        assert {k.value for k in ActionKind} == {
            "press_button",
            "call_service",
            "activate_scene",
            "run_script",
            "fire_event",
        }


class TestCaptureState:
    def test_lifecycle_states_present(self) -> None:
        expected = {"idle", "listening", "captured", "timeout", "error", "cancelled"}
        assert {s.value for s in CaptureState} == expected


class TestCommandCategory:
    def test_speed_preset_present(self) -> None:
        assert CommandCategory.SPEED_PRESET == "speed_preset"


class TestSourceKinds:
    def test_receiver_kinds_include_native(self) -> None:
        assert ReceiverSourceKind.NATIVE_INFRARED == "native_infrared"

    def test_transmitter_kinds_include_native_rf(self) -> None:
        assert TransmitterSourceKind.NATIVE_RADIO_FREQUENCY == "native_radio_frequency"
