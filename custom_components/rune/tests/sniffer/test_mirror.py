"""Tests for the MirrorLog and echo matching."""
from __future__ import annotations

from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.sniffer.mirror import MIRROR_DEVICE_ID, MirrorLog


class _Clock:
    def __init__(self) -> None:
        self.now_value = 0.0

    def __call__(self) -> float:
        return self.now_value

    def advance(self, seconds: float) -> None:
        self.now_value += seconds


class TestMirrorLog:
    def test_record_send_creates_entry(self) -> None:
        clock = _Clock()
        log = MirrorLog(now_provider=clock)
        log.record_send(
            device_name="Bedroom fan",
            command_key="off",
            timings=(9000, -4500, 600, -1700),
            transport=SignalTransport.IR,
            carrier_frequency_hz=38_000,
        )
        entries = log.active_entries()
        assert len(entries) == 1
        assert entries[0].label == "Bedroom fan / off"

    def test_echo_claim_after_send(self) -> None:
        clock = _Clock()
        log = MirrorLog(now_provider=clock)
        log.record_send(
            device_name="X",
            command_key="y",
            timings=(100, -200, 300),
            transport=SignalTransport.IR,
            carrier_frequency_hz=38_000,
        )
        claimed = log.record_echo(
            receiver_entity_id="remote.bedroom",
            timings=(100, -200, 300),
        )
        assert claimed is True

    def test_no_echo_claim_for_unrelated_capture(self) -> None:
        clock = _Clock()
        log = MirrorLog(now_provider=clock)
        log.record_send(
            device_name="X",
            command_key="y",
            timings=(100, -200),
            transport=SignalTransport.IR,
            carrier_frequency_hz=38_000,
        )
        claimed = log.record_echo(
            receiver_entity_id="remote.kitchen",
            timings=(999, 888),
        )
        assert claimed is False

    def test_purge_after_ttl(self) -> None:
        from custom_components.rune.const import MIRROR_ECHO_TTL_S  # noqa: PLC0415

        clock = _Clock()
        log = MirrorLog(now_provider=clock)
        log.record_send(
            device_name="X",
            command_key="y",
            timings=(100,),
            transport=SignalTransport.IR,
            carrier_frequency_hz=38_000,
        )
        assert len(log.active_entries()) == 1
        clock.advance(MIRROR_ECHO_TTL_S + 1)
        # Purging happens lazily on the next record_echo / record_send.
        log.record_send(
            device_name="Z",
            command_key="z",
            timings=(200,),
            transport=SignalTransport.IR,
            carrier_frequency_hz=38_000,
        )
        assert len(log.active_entries()) == 1  # only the new one
        assert log.active_entries()[0].label == "Z / z"

    def test_echo_records_heard_by(self) -> None:
        clock = _Clock()
        log = MirrorLog(now_provider=clock)
        log.record_send(
            device_name="X",
            command_key="y",
            timings=(100, -200),
            transport=SignalTransport.IR,
            carrier_frequency_hz=38_000,
        )
        log.record_echo(receiver_entity_id="r1", timings=(100, -200))
        log.record_echo(receiver_entity_id="r2", timings=(100, -200))
        entries = log.active_entries()
        assert sorted(entries[0].heard_by) == ["r1", "r2"]
        # r1 again doesn't duplicate.
        log.record_echo(receiver_entity_id="r1", timings=(100, -200))
        assert sorted(log.active_entries()[0].heard_by) == ["r1", "r2"]

    def test_rf_echo_with_close_magnitudes(self) -> None:
        clock = _Clock()
        log = MirrorLog(now_provider=clock)
        # Sent: 1000, -1000. Heard: 1010, -1010 (1% drift).
        log.record_send(
            device_name="X",
            command_key="y",
            timings=(1000, -1000),
            transport=SignalTransport.RF,
            carrier_frequency_hz=433_920_000,
        )
        claimed = log.record_echo(
            receiver_entity_id="remote.x",
            timings=(1010, -1010),
        )
        assert claimed is True

    def test_rf_echo_rejected_on_large_drift(self) -> None:
        clock = _Clock()
        log = MirrorLog(now_provider=clock)
        log.record_send(
            device_name="X",
            command_key="y",
            timings=(1000, -1000),
            transport=SignalTransport.RF,
            carrier_frequency_hz=433_920_000,
        )
        # Heard: 2000, -2000 (100% drift) — not plausibly an echo.
        claimed = log.record_echo(
            receiver_entity_id="remote.x",
            timings=(2000, -2000),
        )
        assert claimed is False

    def test_rf_echo_rejected_on_length_mismatch(self) -> None:
        clock = _Clock()
        log = MirrorLog(now_provider=clock)
        log.record_send(
            device_name="X",
            command_key="y",
            timings=(1000, -1000, 500),
            transport=SignalTransport.RF,
            carrier_frequency_hz=433_920_000,
        )
        claimed = log.record_echo(
            receiver_entity_id="remote.x",
            timings=(1000, -1000),
        )
        assert claimed is False


class TestMirrorDeviceId:
    def test_id_is_stable(self) -> None:
        assert MIRROR_DEVICE_ID == "rune-mirror"
