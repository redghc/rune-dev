"""Tests for ``BroadlinkRFCaptureProvider``.

The provider drives the Broadlink two-phase sweep + capture flow
behind the orchestrator's one-shot ``start → wait → stop`` contract.
We exercise that bridge with two fixtures:

- ``FakeBroadlinkDevice`` — wraps a ``FakeBroadlinkAPI`` behind the
  ``device.async_request(api.method)`` coroutine wrapper the real
  Broadlink integration provides.
- ``FakeHass`` — minimal ``hass.data[BROADLINK_DOMAIN]`` so the
  provider's ``find_rf_device_for_entity`` lookup resolves the fake
  device by ``entity_id``.

Tests cover:
- ``is_available`` returns ``False`` when no Broadlink device is
  registered for the entity.
- ``is_available`` returns ``True`` when a live device is bound.
- ``async_start_capture`` raises ``CaptureProviderUnavailableError``
  with a clear "no Broadlink device found" message when missing.
- ``async_wait_for_signal`` runs sweep + capture inline and returns
  a populated ``CapturedPulse`` with ``b64_packet`` set.
- Calling ``async_wait_for_signal`` a second time returns the cached
  pulse (no second sweep).
- Direct capture skips the sweep and uses the user-picked frequency.
- ``async_stop_capture`` is a no-op (RF capture is on-demand).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from custom_components.rune.adapters.broadlink_devices import (
    find_rf_device_for_entity,
)
from custom_components.rune.adapters.capture.broadlink_rf import (
    BroadlinkRFCaptureProvider,
)
from custom_components.rune.const import BROADLINK_DOMAIN
from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.domain.errors import (
    CaptureError,
    CaptureProviderUnavailableError,
)
from custom_components.rune.ports.receiver import CapturedPulse


class FakeHass:
    """Mimics ``hass.data[BROADLINK_DOMAIN].devices[mac] = device``."""

    def __init__(self, devices: list["FakeBroadlinkDevice"] | None = None) -> None:
        self.states: dict[str, Any] = {}
        self.data: dict[str, Any] = {BROADLINK_DOMAIN: self._build_registry(devices or [])}

    def _build_registry(self, devices: list["FakeBroadlinkDevice"]):
        class _Devices:
            def __init__(self, mapping: dict[str, Any]) -> None:
                self._mapping = mapping

            def values(self):
                return self._mapping.values()

        class _DomainData:
            def __init__(self, mapping: dict[str, Any]) -> None:
                self.devices = _Devices(mapping)

        return _DomainData({device.mac_address: device for device in devices})


@dataclass
class FakeBroadlinkAPI:
    """The synchronous API the Broadlink SDK exposes.

    The provider talks to it through ``device.async_request`` so we
    just implement the SDK methods directly.
    """

    sweep_delay_s: float = 0.0
    find_delay_s: float = 0.0
    frequency_mhz: float = 433.92
    packet: bytes = b"\xb2\x01\x04\x01\x02\x03\x04"
    raise_on_sweep: Exception | None = None
    raise_on_capture: Exception | None = None
    sweep_called: int = 0
    find_called: int = 0
    check_data_calls: int = 0

    async def sweep_frequency(self) -> None:
        self.sweep_called += 1
        if self.raise_on_sweep is not None:
            raise self.raise_on_sweep
        if self.sweep_delay_s:
            await asyncio.sleep(self.sweep_delay_s)

    async def check_frequency(self) -> tuple[bool, float]:
        return True, self.frequency_mhz

    async def cancel_sweep_frequency(self) -> None:
        return None

    async def find_rf_packet(self, _frequency_mhz: float | None) -> None:
        self.find_called += 1
        if self.raise_on_capture is not None:
            raise self.raise_on_capture
        if self.find_delay_s:
            await asyncio.sleep(self.find_delay_s)

    async def check_data(self) -> bytes:
        self.check_data_calls += 1
        return self.packet


class _IrOnlyAPI:
    """Stub API for an IR-only Broadlink unit (no sweep_frequency)."""

    async def find_rf_packet(self, _frequency_mhz: float | None) -> None:
        return None


class FakeBroadlinkDevice:
    """Stand-in for ``hass.data[BROADLINK_DOMAIN].devices[mac]``.

    Wraps a ``FakeBroadlinkAPI`` behind ``async_request`` so the
    provider exercises the same call path it does in production.
    """

    def __init__(
        self,
        mac_address: str,
        entity_id: str,
        api: FakeBroadlinkAPI | None = None,
    ) -> None:
        self.mac_address = mac_address
        self.entity_id = entity_id
        self.api = api if api is not None else FakeBroadlinkAPI()
        # The provider walks ``device.entities`` to map an
        # ``entity_id`` back to the device.
        self.entities = [type("_E", (), {"entity_id": entity_id})()]

    async def async_request(self, method: Any, *args: Any) -> Any:
        """Mirror the Broadlink integration's coroutine wrapper —
        call the sync SDK method directly, awaiting the result."""
        return await method(*args)


def _hass_with_device(entity_id: str = "remote.broadlink") -> tuple[FakeHass, FakeBroadlinkDevice]:
    device = FakeBroadlinkDevice(
        mac_address="aa:bb:cc:dd:ee:ff", entity_id=entity_id
    )
    return FakeHass(devices=[device]), device


class TestBroadlinkRFCaptureProvider:
    @pytest.mark.asyncio
    async def test_is_available_false_without_device(self) -> None:
        hass = FakeHass(devices=[])
        provider = BroadlinkRFCaptureProvider(hass, "remote.broadlink")
        assert provider.is_available is False

    @pytest.mark.asyncio
    async def test_is_available_true_with_device(self) -> None:
        hass, _device = _hass_with_device()
        provider = BroadlinkRFCaptureProvider(hass, "remote.broadlink")
        assert provider.is_available is True

    @pytest.mark.asyncio
    async def test_start_without_device_raises(self) -> None:
        hass = FakeHass(devices=[])
        provider = BroadlinkRFCaptureProvider(hass, "remote.broadlink")
        with pytest.raises(CaptureProviderUnavailableError) as info:
            await provider.async_start_capture(timeout_s=1.0)
        assert "Broadlink device" in str(info.value)
        assert "remote.broadlink" in str(info.value)

    @pytest.mark.asyncio
    async def test_wait_returns_captured_pulse_with_b64(self) -> None:
        """Default mode: sweep + capture via ``async_request``."""
        hass, device = _hass_with_device()
        provider = BroadlinkRFCaptureProvider(hass, "remote.broadlink")
        await provider.async_start_capture(timeout_s=5.0)
        pulse = await provider.async_wait_for_signal(timeout_s=5.0)
        assert pulse is not None
        assert pulse.signal_category.transport is SignalTransport.RF
        assert pulse.signal_category.carrier_frequency_hz == int(433.92 * 1_000_000)
        assert pulse.b64_packet is not None
        assert pulse.raw_timings
        # ``async_request`` was hit for sweep + packet.
        assert device.api.sweep_called == 1
        assert device.api.find_called == 1

    @pytest.mark.asyncio
    async def test_wait_caches_result(self) -> None:
        """A second ``wait_for_signal`` must NOT trigger a second
        sweep — the user already pressed the button once."""
        hass, device = _hass_with_device()
        provider = BroadlinkRFCaptureProvider(hass, "remote.broadlink")
        await provider.async_start_capture(timeout_s=5.0)
        first = await provider.async_wait_for_signal(timeout_s=5.0)
        second = await provider.async_wait_for_signal(timeout_s=5.0)
        assert first is second
        assert device.api.sweep_called == 1

    @pytest.mark.asyncio
    async def test_wait_returns_none_when_sweep_fails(self) -> None:
        """Hardware failures during sweep must surface as ``None``
        (timeout-like state) rather than a raw exception, so the
        orchestrator can render a clean "no signal" UI state."""
        hass, device = _hass_with_device()
        device.api.raise_on_sweep = CaptureError("broadlink offline")
        provider = BroadlinkRFCaptureProvider(hass, "remote.broadlink")
        await provider.async_start_capture(timeout_s=5.0)
        result = await provider.async_wait_for_signal(timeout_s=5.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_direct_capture_skips_sweep(self) -> None:
        """Direct mode listens at the chosen frequency with no sweep.

        Mirrors the Mercator FRM97 case the SPA's Learn dialog
        exposes — the sweep can't lock onto short bursts, so the
        user picks the carrier explicitly.
        """
        hass, device = _hass_with_device()
        provider = BroadlinkRFCaptureProvider(
            hass,
            "remote.broadlink",
            direct=True,
            frequency_hz=433_920_000,
        )
        await provider.async_start_capture(timeout_s=5.0)
        pulse = await provider.async_wait_for_signal(timeout_s=5.0)
        assert pulse is not None
        assert pulse.signal_category.carrier_frequency_hz == 433_920_000
        assert pulse.b64_packet is not None
        # The sweep was NEVER called — direct mode skips it.
        assert device.api.sweep_called == 0
        assert device.api.find_called == 1

    @pytest.mark.asyncio
    async def test_stop_is_noop(self) -> None:
        hass, _device = _hass_with_device()
        provider = BroadlinkRFCaptureProvider(hass, "remote.broadlink")
        await provider.async_start_capture(timeout_s=1.0)
        await provider.async_stop_capture()
        with pytest.raises(RuntimeError, match="before async_start_capture"):
            await provider.async_wait_for_signal(timeout_s=0.05)


class TestFindRfDevices:
    """The ``broadlink_devices`` lookup is the single point of contact
    between RUNE and the Broadlink integration's ``hass.data`` registry.
    Locking its behaviour here so a future HA upgrade doesn't quietly
    break the resolution path."""

    def test_returns_empty_when_broadlink_not_loaded(self) -> None:
        hass = FakeHass(devices=[])
        assert find_rf_device_for_entity(hass, "remote.broadlink") is None

    def test_returns_device_for_matching_entity(self) -> None:
        device = FakeBroadlinkDevice(
            mac_address="aa:bb:cc:dd:ee:ff", entity_id="remote.broadlink"
        )
        hass = FakeHass(devices=[device])
        assert find_rf_device_for_entity(hass, "remote.broadlink") is device

    def test_ignores_ir_only_devices(self) -> None:
        """Devices whose API lacks ``sweep_frequency`` aren't RF —
        the lookup filters them out so the user never picks them."""
        device = FakeBroadlinkDevice(
            mac_address="aa:bb:cc:dd:ee:ff", entity_id="remote.broadlink"
        )
        # Replace the API with one that lacks ``sweep_frequency``
        # to simulate an IR-only unit.
        device.api = _IrOnlyAPI()
        hass = FakeHass(devices=[device])
        assert find_rf_device_for_entity(hass, "remote.broadlink") is None

    def test_returns_none_for_empty_entity_id(self) -> None:
        hass = FakeHass(devices=[])
        assert find_rf_device_for_entity(hass, "") is None
