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
    find_ir_learn_device_for_entity,
    find_rf_device_for_entity,
)
from custom_components.rune.adapters.capture.broadlink_rf import (
    BroadlinkIRCaptureProvider,
    BroadlinkRFCaptureProvider,
)
from custom_components.rune.const import BROADLINK_DOMAIN
from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.domain.errors import (
    CaptureError,
    CaptureProviderUnavailableError,
)
from custom_components.rune.ports.receiver import CapturedPulse


class FakeEntityRegistry:
    """Minimal stand-in for ``homeassistant.helpers.entity_registry``."""

    def __init__(self, mapping: dict[str, "_FakeEntityEntry"] | None = None) -> None:
        self.entities = mapping or {}


class _FakeEntityEntry:
    def __init__(self, entity_id: str, config_entry_id: str) -> None:
        self.entity_id = entity_id
        self.config_entry_id = config_entry_id


class FakeHass:
    """Mimics ``hass.data[BROADLINK_DOMAIN].devices[entry_id] = device``
    plus an entity registry so :func:`find_rf_devices` walks the
    production path (entity_registry → config_entry_id → device).
    """

    def __init__(
        self,
        devices: list["FakeBroadlinkDevice"] | None = None,
        entity_registry_entries: dict[str, _FakeEntityEntry] | None = None,
    ) -> None:
        self.states: dict[str, Any] = {}
        self.data: dict[str, Any] = {
            BROADLINK_DOMAIN: self._build_registry(devices or []),
        }
        # Inject the entity_registry module so the production
        # ``find_rf_devices`` finds it. Tests that don't care can
        # ignore this; tests that do populate it explicitly.
        self._entity_registry = entity_registry_entries or {}

    def _build_registry(self, devices: list["FakeBroadlinkDevice"]):
        class _Devices:
            def __init__(self, mapping: dict[str, Any]) -> None:
                self._mapping = mapping

            def values(self):
                return self._mapping.values()

            def keys(self):
                return self._mapping.keys()

            def get(self, key, default=None):
                return self._mapping.get(key, default)

            def __contains__(self, key):
                return key in self._mapping

        class _DomainData:
            def __init__(self, mapping: dict[str, Any]) -> None:
                self.devices = _Devices(mapping)

        # Keyed by config entry id, mirroring HA core's storage.
        return _DomainData({f"entry-{device.mac_address}": device for device in devices})

    @property
    def entity_registry(self) -> FakeEntityRegistry:
        """Read-only access to the fake entity registry."""
        return FakeEntityRegistry(self._entity_registry)


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
    enter_learning_called: int = 0

    async def enter_learning(self) -> None:
        self.enter_learning_called += 1

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


class _IrLearnOnlyAPI:
    """Stub API for an RM Mini — can learn IR, has no RF at all."""

    async def enter_learning(self) -> None:
        return None

    async def check_data(self) -> bytes:
        return b"\x26\x00\x04\x00\x01\x02\x03\x04"


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


def _hass_with_device(
    entity_id: str = "remote.broadlink",
    *,
    entity_registry_entries: dict[str, _FakeEntityEntry] | None = None,
) -> tuple[FakeHass, FakeBroadlinkDevice]:
    """Build a FakeHass with one Broadlink device + an entity registry.

    ``entity_registry_entries`` maps ``entity_id`` to the
    ``_FakeEntityEntry`` the registry returns. Pass it to model
    the modern Broadlink integration shape where entities live in
    the HA entity registry (not on ``device.entities``).
    """
    device = FakeBroadlinkDevice(
        mac_address="aa:bb:cc:dd:ee:ff", entity_id=entity_id
    )
    if entity_registry_entries is None:
        # Default: register the device's entity_id so the lookup works.
        entity_registry_entries = {
            entity_id: _FakeEntityEntry(
                entity_id=entity_id,
                config_entry_id=f"entry-{device.mac_address}",
            )
        }
    hass = FakeHass(
        devices=[device], entity_registry_entries=entity_registry_entries
    )
    return hass, device


@pytest.fixture
def installed_entity_registry(monkeypatch: pytest.MonkeyPatch):
    """Install a fake ``homeassistant.helpers.entity_registry`` module
    so the production :func:`find_rf_devices` walks the entity
    registry path. Without this fixture, the module isn't installed
    in the test environment and the lookup falls back to the
    legacy ``device.entities`` walk.

    Python resolves ``from homeassistant.helpers import entity_registry``
    by importing the parent packages first — we seed those too so
    the inner ``from homeassistant.helpers`` import inside the
    production function actually picks up our fake.
    """
    import sys
    import types

    homeassistant = types.ModuleType("homeassistant")
    helpers = types.ModuleType("homeassistant.helpers")
    fake = types.ModuleType("homeassistant.helpers.entity_registry")

    def async_get(hass: Any) -> FakeEntityRegistry:
        # The FakeHass exposes its registry as ``hass.entity_registry``.
        return hass.entity_registry

    fake.async_get = async_get
    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", helpers)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.entity_registry", fake)


class TestBroadlinkRFCaptureProvider:
    @pytest.mark.asyncio
    async def test_is_available_false_without_device(
        self, installed_entity_registry: None
    ) -> None:
        hass = FakeHass(devices=[])
        provider = BroadlinkRFCaptureProvider(hass, "remote.broadlink")
        assert provider.is_available is False

    @pytest.mark.asyncio
    async def test_is_available_true_with_device(
        self, installed_entity_registry: None
    ) -> None:
        hass, _device = _hass_with_device()
        provider = BroadlinkRFCaptureProvider(hass, "remote.broadlink")
        assert provider.is_available is True

    @pytest.mark.asyncio
    async def test_start_without_device_raises(
        self, installed_entity_registry: None
    ) -> None:
        hass = FakeHass(devices=[])
        provider = BroadlinkRFCaptureProvider(hass, "remote.broadlink")
        with pytest.raises(CaptureProviderUnavailableError) as info:
            await provider.async_start_capture(timeout_s=1.0)
        assert "Broadlink device" in str(info.value)
        assert "remote.broadlink" in str(info.value)

    @pytest.mark.asyncio
    async def test_wait_returns_captured_pulse_with_b64(
        self, installed_entity_registry: None
    ) -> None:
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
    async def test_wait_caches_result(
        self, installed_entity_registry: None
    ) -> None:
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
    async def test_wait_returns_none_when_sweep_fails(
        self, installed_entity_registry: None
    ) -> None:
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
    async def test_direct_capture_skips_sweep(
        self, installed_entity_registry: None
    ) -> None:
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
    async def test_stop_is_noop(
        self, installed_entity_registry: None
    ) -> None:
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

    def test_returns_empty_when_broadlink_not_loaded(
        self, installed_entity_registry: None
    ) -> None:
        hass = FakeHass(devices=[])
        assert find_rf_device_for_entity(hass, "remote.broadlink") is None

    def test_returns_device_for_matching_entity(
        self, installed_entity_registry: None
    ) -> None:
        # Modern Broadlink integrations don't populate
        # ``device.entities`` — they register every entity through the
        # ``infrared`` / ``radio_frequency`` platforms, which records
        # them in HA's entity_registry. The lookup must walk that
        # registry to find the entity → BroadlinkDevice mapping.
        hass, device = _hass_with_device("remote.broadlink")
        assert find_rf_device_for_entity(hass, "remote.broadlink") is device

    def test_ignores_ir_only_devices(
        self, installed_entity_registry: None
    ) -> None:
        """Devices whose API lacks ``sweep_frequency`` aren't RF —
        the lookup filters them out so the user never picks them."""
        device = FakeBroadlinkDevice(
            mac_address="aa:bb:cc:dd:ee:ff", entity_id="remote.broadlink"
        )
        # Replace the API with one that lacks ``sweep_frequency``
        # to simulate an IR-only unit.
        device.api = _IrOnlyAPI()
        hass = FakeHass(
            devices=[device],
            entity_registry_entries={
                "remote.broadlink": _FakeEntityEntry(
                    entity_id="remote.broadlink",
                    config_entry_id=f"entry-{device.mac_address}",
                )
            },
        )
        assert find_rf_device_for_entity(hass, "remote.broadlink") is None

    def test_returns_device_for_broadlink_ir_emitter(
        self, installed_entity_registry: None
    ) -> None:
        """Modern Broadlink integrations expose IR emitters under the
        ``infrared.*`` domain. The lookup must resolve them through
        the entity_registry's ``config_entry_id`` mapping — that's
        the only path from ``infrared.*`` entity → BroadlinkDevice.

        This is the exact case the user hit: a Broadlink device
        whose IR emitter is named ``infrared.remoto_emisor_ir`` and
        who wanted to learn an IR command via the RF capture path
        (which uses the Broadlink SDK directly)."""
        device = FakeBroadlinkDevice(
            mac_address="aa:bb:cc:dd:ee:ff",
            entity_id="infrared.remoto_emisor_ir",
        )
        # Pre-populate the entity_registry with TWO entities, both
        # owned by the same Broadlink config entry — the IR emitter
        # AND the RF transmitter.
        entry_id = f"entry-{device.mac_address}"
        hass = FakeHass(
            devices=[device],
            entity_registry_entries={
                "infrared.remoto_emisor_ir": _FakeEntityEntry(
                    entity_id="infrared.remoto_emisor_ir",
                    config_entry_id=entry_id,
                ),
                "radio_frequency.broadlink_tx": _FakeEntityEntry(
                    entity_id="radio_frequency.broadlink_tx",
                    config_entry_id=entry_id,
                ),
            },
        )
        # Both entities resolve to the same BroadlinkDevice — the WS
        # handler picks either to drive the sweep + capture flow.
        assert (
            find_rf_device_for_entity(hass, "infrared.remoto_emisor_ir")
            is device
        )
        assert (
            find_rf_device_for_entity(hass, "radio_frequency.broadlink_tx")
            is device
        )
        # But a non-Broadlink IR emitter does NOT resolve — the
        # domain match is only the first filter; Broadlink ownership
        # is what counts.
        assert (
            find_rf_device_for_entity(hass, "infrared.some_other_emitter")
            is None
        )

    def test_returns_none_for_empty_entity_id(
        self, installed_entity_registry: None
    ) -> None:
        hass = FakeHass(devices=[])
        assert find_rf_device_for_entity(hass, "") is None


class TestBroadlinkIRLearn:
    """The Broadlink SDK IR learn path.

    The HA Broadlink integration never exposes the hardware's IR
    receiver as an ``InfraredReceiverEntity``, so learning IR on a
    Broadlink always goes through ``enter_learning`` +
    ``check_data``. These tests lock that path in — it's the exact
    UX the user hit ("my infrared.* emitter should be able to learn").
    """

    @pytest.mark.asyncio
    async def test_ir_learn_returns_pulse_with_b64(
        self, installed_entity_registry: None
    ) -> None:
        hass, device = _hass_with_device("infrared.remoto_emisor_ir")
        provider = BroadlinkIRCaptureProvider(hass, "infrared.remoto_emisor_ir")
        await provider.async_start_capture(timeout_s=5.0)
        pulse = await provider.async_wait_for_signal(timeout_s=5.0)
        assert pulse is not None
        assert pulse.signal_category.transport is SignalTransport.IR
        assert pulse.b64_packet is not None
        assert pulse.raw_timings
        # The SDK learn flow was driven exactly once.
        assert device.api.enter_learning_called == 1
        assert device.api.check_data_calls >= 1
        # And the RF sweep was never touched.
        assert device.api.sweep_called == 0

    @pytest.mark.asyncio
    async def test_ir_learn_caches_result(
        self, installed_entity_registry: None
    ) -> None:
        """A re-entry from the orchestrator's loop must NOT re-arm
        the receiver — the user pressed the button once."""
        hass, device = _hass_with_device("infrared.remoto_emisor_ir")
        provider = BroadlinkIRCaptureProvider(hass, "infrared.remoto_emisor_ir")
        await provider.async_start_capture(timeout_s=5.0)
        first = await provider.async_wait_for_signal(timeout_s=5.0)
        second = await provider.async_wait_for_signal(timeout_s=5.0)
        assert first is second
        assert device.api.enter_learning_called == 1

    @pytest.mark.asyncio
    async def test_ir_learn_without_device_raises(
        self, installed_entity_registry: None
    ) -> None:
        hass = FakeHass(devices=[])
        provider = BroadlinkIRCaptureProvider(hass, "infrared.remoto_emisor_ir")
        with pytest.raises(CaptureProviderUnavailableError) as info:
            await provider.async_start_capture(timeout_s=1.0)
        assert "Broadlink device" in str(info.value)

    def test_ir_learn_lookup_includes_rm_mini(
        self, installed_entity_registry: None
    ) -> None:
        """IR-only units (RM Mini) have ``enter_learning`` but no
        ``sweep_frequency`` — the IR lookup must include them even
        though the RF one excludes them."""
        device = FakeBroadlinkDevice(
            mac_address="11:22:33:44:55:66", entity_id="infrared.rm_mini"
        )
        # Strip every RF capability from the API.
        device.api = _IrLearnOnlyAPI()
        hass = FakeHass(
            devices=[device],
            entity_registry_entries={
                "infrared.rm_mini": _FakeEntityEntry(
                    entity_id="infrared.rm_mini",
                    config_entry_id=f"entry-{device.mac_address}",
                )
            },
        )
        assert find_ir_learn_device_for_entity(hass, "infrared.rm_mini") is device
        assert find_rf_device_for_entity(hass, "infrared.rm_mini") is None
