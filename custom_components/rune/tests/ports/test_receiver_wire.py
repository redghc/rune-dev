"""Tests for ``CapturedPulse.to_dict`` — wire shape the WS handler emits.

The WS layer relies on this serialization so the SPA can spread the
captured record into a fresh :class:`PulseCommand`. The shape must
match the ``LearnResult.captured`` interface in the Lit panel.
"""
from __future__ import annotations

from custom_components.rune.domain.enums import (
    SignalCategory,
    SignalEncoding,
    SignalTransport,
)
from custom_components.rune.ports.receiver import CapturedPulse


def _pulse(**overrides: object) -> CapturedPulse:
    base: dict[str, object] = {
        "receiver_entity_id": "infrared.bedroom",
        "signal_category": SignalCategory(
            transport=SignalTransport.IR,
            encoding=SignalEncoding.RAW_TIMINGS,
            carrier_frequency_hz=38_000,
        ),
        "raw_timings": (100, -200, 300),
        "protocol_label": None,
        "code_hex": None,
        "decoded_fingerprint": None,
    }
    base.update(overrides)
    return CapturedPulse(**base)  # type: ignore[arg-type]


class TestCapturedPulseToDict:
    def test_minimal_pulse_serializes(self) -> None:
        out = _pulse().to_dict()
        assert out["protocol_label"] is None
        assert out["signal_category"] == {
            "transport": "ir",
            "encoding": "raw_timings",
            "carrier_frequency_hz": 38_000,
        }
        assert out["payload"] == {"raw_timings": [100, -200, 300]}
        # No decoded fields populated → nothing leaked into payload.
        assert "decoded_hex" not in out["payload"]
        assert "decoded_fingerprint" not in out["payload"]

    def test_decoded_metadata_layers_in(self) -> None:
        out = _pulse(
            protocol_label="NEC",
            code_hex="20 DF 10 EF",
            decoded_fingerprint="nec:20df10ef",
        ).to_dict()
        assert out["protocol_label"] == "NEC"
        assert out["payload"]["decoded_hex"] == "20 DF 10 EF"
        assert out["payload"]["decoded_fingerprint"] == "nec:20df10ef"
        # Raw timings still ride along.
        assert out["payload"]["raw_timings"] == [100, -200, 300]

    def test_signal_category_str_enums_are_plain_strings(self) -> None:
        out = _pulse(
            signal_category=SignalCategory(
                transport=SignalTransport.RF,
                encoding=SignalEncoding.DECODED,
                carrier_frequency_hz=433_920,
            )
        ).to_dict()
        assert out["signal_category"]["transport"] == "rf"
        assert out["signal_category"]["encoding"] == "decoded"
        assert out["signal_category"]["carrier_frequency_hz"] == 433_920
