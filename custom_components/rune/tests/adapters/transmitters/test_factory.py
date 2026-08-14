"""Tests for the transmitter factory.

The factory itself is pure (no HA imports needed). Tests for the
individual adapters live alongside them with HA-mocked fakes.
"""
from __future__ import annotations

import pytest

from custom_components.rune.adapters.transmitters.broadlink_ir import (
    BroadlinkIRTransmitter,
)
from custom_components.rune.adapters.transmitters.broadlink_rf import (
    BroadlinkRFTransmitter,
)
from custom_components.rune.adapters.transmitters.esphome_ir import (
    ESPHomeIRTransmitter,
)
from custom_components.rune.adapters.transmitters.esphome_rf import (
    ESPHomeRFTransmitter,
)
from custom_components.rune.adapters.transmitters.factory import select_transmitter
from custom_components.rune.adapters.transmitters.native_ir import (
    NativeIRTransmitter,
)
from custom_components.rune.adapters.transmitters.native_rf import (
    NativeRFTransmitter,
)
from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.domain.errors import UnsupportedHardwareError


class FakeHass:
    """Minimal hass stub."""

    def __init__(self) -> None:
        self.states: dict[str, object] = {}


class TestSelectTransmitter:
    def test_native_ir(self) -> None:
        t = select_transmitter(FakeHass(), "infrared.bedroom_blaster", SignalTransport.IR)
        assert isinstance(t, NativeIRTransmitter)

    def test_native_rf(self) -> None:
        t = select_transmitter(FakeHass(), "radio_frequency.kitchen_blaster", SignalTransport.RF)
        assert isinstance(t, NativeRFTransmitter)

    def test_broadlink_ir_legacy(self) -> None:
        t = select_transmitter(FakeHass(), "remote.broadlink_rm_pro", SignalTransport.IR)
        assert isinstance(t, BroadlinkIRTransmitter)

    def test_broadlink_rf_legacy(self) -> None:
        t = select_transmitter(FakeHass(), "remote.broadlink_rm_pro", SignalTransport.RF)
        assert isinstance(t, BroadlinkRFTransmitter)

    def test_esphome_ir(self) -> None:
        t = select_transmitter(FakeHass(), "esphome.living_room_ir", SignalTransport.IR)
        assert isinstance(t, ESPHomeIRTransmitter)

    def test_esphome_rf(self) -> None:
        t = select_transmitter(FakeHass(), "esphome.living_room_rf", SignalTransport.RF)
        assert isinstance(t, ESPHomeRFTransmitter)

    def test_empty_entity_id_raises(self) -> None:
        with pytest.raises(UnsupportedHardwareError):
            select_transmitter(FakeHass(), "", SignalTransport.IR)

    def test_unknown_entity_raises(self) -> None:
        with pytest.raises(UnsupportedHardwareError):
            select_transmitter(FakeHass(), "media_player.kitchen", SignalTransport.IR)

    def test_domain_transport_mismatch_raises(self) -> None:
        # ``infrared.`` is IR-only.
        with pytest.raises(UnsupportedHardwareError):
            select_transmitter(FakeHass(), "infrared.foo", SignalTransport.RF)
