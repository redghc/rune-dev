"""Tests for the receiver factory."""
from __future__ import annotations

import pytest

from custom_components.rune.adapters.receivers.broadlink_rf import (
    BroadlinkRFReceiver,
)
from custom_components.rune.adapters.receivers.esphome_legacy_ir import (
    ESPHomeLegacyIRReceiver,
)
from custom_components.rune.adapters.receivers.factory import select_receiver
from custom_components.rune.adapters.receivers.native_ir import NativeIRReceiver
from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.domain.errors import UnsupportedHardwareError


class FakeHass:
    def __init__(self) -> None:
        self.bus = type("Bus", (), {})()


class TestSelectReceiver:
    def test_native_ir(self) -> None:
        r = select_receiver(FakeHass(), "infrared.bedroom", SignalTransport.IR)
        assert isinstance(r, NativeIRReceiver)

    def test_esphome_legacy_ir(self) -> None:
        r = select_receiver(FakeHass(), "esphome.living_room", SignalTransport.IR)
        assert isinstance(r, ESPHomeLegacyIRReceiver)

    def test_broadlink_rf_requires_device_api(self) -> None:
        with pytest.raises(UnsupportedHardwareError, match="device API"):
            select_receiver(FakeHass(), "remote.broadlink", SignalTransport.RF)

    def test_broadlink_rf_with_device_api(self) -> None:
        api = object()
        r = select_receiver(
            FakeHass(), "remote.broadlink", SignalTransport.RF, device_api=api
        )
        assert isinstance(r, BroadlinkRFReceiver)
        assert r._device_api is api

    def test_empty_entity_id_raises(self) -> None:
        with pytest.raises(UnsupportedHardwareError):
            select_receiver(FakeHass(), "", SignalTransport.IR)

    def test_unknown_entity_raises(self) -> None:
        with pytest.raises(UnsupportedHardwareError):
            select_receiver(FakeHass(), "media_player.x", SignalTransport.IR)

    def test_ir_emitter_domain_is_not_a_receiver(self) -> None:
        # An IR emitter-only entity has no RX path.
        with pytest.raises(UnsupportedHardwareError):
            select_receiver(FakeHass(), "infrared.foo", SignalTransport.RF)
