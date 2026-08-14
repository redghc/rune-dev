"""Contract tests — exercise every repository adapter against the same cases.

These tests run against any object that implements the repository
ports. We use them to verify both the in-memory adapter AND a fake
HA-Store-backed adapter stay consistent in behavior. (The real HA
adapter requires HA core running; the fake here mirrors its
load/save protocol so we can assert the same contract.)

If a future adapter is added (e.g. SQLite), add it to ``ADAPTERS``
below and it gets the full contract suite for free.

The HA-store contract tests are skipped when ``homeassistant`` is not
importable — in pure dev environments, only the in-memory adapter is
exercised. CI installs HA via ``pytest-homeassistant-custom-component``
to enable the full contract.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

from custom_components.rune.adapters.storage.memory import (
    InMemoryActionRepository,
    InMemoryDeviceRepository,
    InMemorySignalRepository,
)
from custom_components.rune.domain.enums import EntityCategory, SignalCategory
from custom_components.rune.domain.models import (
    ActionBinding,
    ActionTarget,
    RuneDevice,
    UnknownRemote,
    UnknownSignal,
)

try:
    from custom_components.rune.adapters.storage.ha_store import (
        HAStoreActionRepository,
        HAStoreDeviceRepository,
        HAStoreSignalRepository,
    )

    _HA_STORE_AVAILABLE = True
except ImportError:  # homeassistant not installed in this env
    _HA_STORE_AVAILABLE = False

    class HAStoreDeviceRepository:  # type: ignore[no-redef]
        pass

    class HAStoreActionRepository:  # type: ignore[no-redef]
        pass

    class HAStoreSignalRepository:  # type: ignore[no-redef]
        pass


_HA_STORE_SKIP = pytest.mark.skipif(
    not _HA_STORE_AVAILABLE,
    reason="homeassistant not installed; HA-Store contract skipped",
)


# ---------------------------------------------------------------------------
# Fake HA Store (mirrors homeassistant.helpers.storage.Store)
# ---------------------------------------------------------------------------


class FakeHAStore:
    """In-process stand-in for ``homeassistant.helpers.storage.Store``.

    Implements the subset HA's Store uses:

    - ``async_load()`` returns the persisted dict or ``None``.
    - ``async_save(data)`` writes through.
    - A ``_listeners`` array for HA's "storage updated" bus (not used
      here but kept to mirror the real interface).

    The real adapter calls these two methods; that's all we need.
    """

    def __init__(self) -> None:
        self._data: Any = None

    async def async_load(self) -> Any:
        return self._data

    async def async_save(self, data: Any) -> None:
        self._data = data


class FakeHass:
    """Minimal stand-in for HomeAssistant — only what Store() needs."""

    def __init__(self, store: FakeHAStore) -> None:
        self._store = store

    def async_create_task(self, coro: Any) -> Any:  # pragma: no cover - never called
        return coro

    @property
    def data(self) -> dict[str, Any]:  # pragma: no cover - never called
        return {}


@pytest_asyncio.fixture
async def fake_hass() -> AsyncIterator[FakeHass]:
    store = FakeHAStore()
    yield FakeHass(store)


def _ha_store_device_repo(hass: FakeHass) -> HAStoreDeviceRepository:
    """Build a HAStoreDeviceRepository pointed at a fresh fake Store."""
    repo = HAStoreDeviceRepository.__new__(HAStoreDeviceRepository)
    repo._store = FakeHAStore()
    return repo


def _ha_store_action_repo(hass: FakeHass) -> HAStoreActionRepository:
    repo = HAStoreActionRepository.__new__(HAStoreActionRepository)
    repo._store = FakeHAStore()
    return repo


def _ha_store_signal_repo(hass: FakeHass) -> HAStoreSignalRepository:
    repo = HAStoreSignalRepository.__new__(HAStoreSignalRepository)
    repo._store = FakeHAStore()
    return repo


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _device(device_id: str = "dev-1") -> RuneDevice:
    return RuneDevice(
        id=device_id,
        name="Test fan",
        category=EntityCategory.FAN,
    )


def _action(action_id: str = "act-1") -> ActionBinding:
    return ActionBinding(
        id=action_id,
        name="Toggle power",
        signal_id="sig-1",
        target=ActionTarget(kind="press_button", device_id="dev-1", command_key="power"),
    )


def _signal(signal_id: str = "sig-1") -> UnknownSignal:
    return UnknownSignal(
        id=signal_id,
        fingerprint="LLLS",
        signal_category=SignalCategory.default_ir(),
        raw_timings=(),
        first_seen="2026-08-12T20:00:00Z",
        last_seen="2026-08-12T20:00:00Z",
        hit_count=1,
    )


DEVICE_REPOS = [
    pytest.param(lambda: InMemoryDeviceRepository(), id="memory"),
    pytest.param(
        _ha_store_device_repo,
        id="ha_store",
        marks=_HA_STORE_SKIP,
    ),
]

ACTION_REPOS = [
    pytest.param(lambda: InMemoryActionRepository(), id="memory"),
    pytest.param(
        _ha_store_action_repo,
        id="ha_store",
        marks=_HA_STORE_SKIP,
    ),
]

SIGNAL_REPOS = [
    pytest.param(lambda: InMemorySignalRepository(), id="memory"),
    pytest.param(
        _ha_store_signal_repo,
        id="ha_store",
        marks=_HA_STORE_SKIP,
    ),
]


# ---------------------------------------------------------------------------
# Device contract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("factory", DEVICE_REPOS)
@pytest.mark.asyncio
class TestDeviceContract:
    async def test_initial_load_empty(self, factory: Any, fake_hass: FakeHass) -> None:
        repo = factory(fake_hass) if factory is _ha_store_device_repo else factory()
        assert await repo.load() == []

    async def test_save_and_load(self, factory: Any, fake_hass: FakeHass) -> None:
        repo = factory(fake_hass) if factory is _ha_store_device_repo else factory()
        devices = [_device("a"), _device("b")]
        await repo.save(devices)
        loaded = await repo.load()
        assert [d.id for d in loaded] == ["a", "b"]

    async def test_upsert_replace(self, factory: Any, fake_hass: FakeHass) -> None:
        repo = factory(fake_hass) if factory is _ha_store_device_repo else factory()
        await repo.upsert(_device("x"))
        updated = _device("x")
        updated.name = "Renamed"
        await repo.upsert(updated)
        loaded = await repo.get("x")
        assert loaded is not None
        assert loaded.name == "Renamed"

    async def test_delete(self, factory: Any, fake_hass: FakeHass) -> None:
        repo = factory(fake_hass) if factory is _ha_store_device_repo else factory()
        await repo.upsert(_device("x"))
        assert await repo.delete("x") is True
        assert await repo.get("x") is None

    async def test_delete_missing(self, factory: Any, fake_hass: FakeHass) -> None:
        repo = factory(fake_hass) if factory is _ha_store_device_repo else factory()
        assert await repo.delete("nope") is False


# ---------------------------------------------------------------------------
# Action contract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("factory", ACTION_REPOS)
@pytest.mark.asyncio
class TestActionContract:
    async def test_round_trip(self, factory: Any, fake_hass: FakeHass) -> None:
        repo = factory(fake_hass) if factory is _ha_store_action_repo else factory()
        await repo.save([_action("a")])
        loaded = await repo.load()
        assert len(loaded) == 1
        assert loaded[0].target.kind == "press_button"

    async def test_delete_missing(self, factory: Any, fake_hass: FakeHass) -> None:
        repo = factory(fake_hass) if factory is _ha_store_action_repo else factory()
        assert await repo.delete("nope") is False


# ---------------------------------------------------------------------------
# Signal contract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("factory", SIGNAL_REPOS)
@pytest.mark.asyncio
class TestSignalContract:
    async def test_upsert_creates_remote(self, factory: Any, fake_hass: FakeHass) -> None:
        repo = factory(fake_hass) if factory is _ha_store_signal_repo else factory()
        await repo.upsert_signal("r-1", _signal("s-1"))
        remotes = await repo.load_remotes()
        assert len(remotes) == 1
        assert remotes[0].signals[0].id == "s-1"

    async def test_remove_drops_empty_remote(self, factory: Any, fake_hass: FakeHass) -> None:
        repo = factory(fake_hass) if factory is _ha_store_signal_repo else factory()
        await repo.upsert_signal("r-1", _signal("s-1"))
        assert await repo.remove_signal("r-1", "s-1") is True
        assert await repo.load_remotes() == []

    async def test_remove_missing_signal(self, factory: Any, fake_hass: FakeHass) -> None:
        repo = factory(fake_hass) if factory is _ha_store_signal_repo else factory()
        assert await repo.remove_signal("missing", "x") is False

    async def test_save_round_trip_with_remote(self, factory: Any, fake_hass: FakeHass) -> None:
        repo = factory(fake_hass) if factory is _ha_store_signal_repo else factory()
        remote = UnknownRemote(
            id="r-1",
            label="Bedroom",
            protocol_label="NEC",
            device_address="0xFB04",
            signals=[_signal("s-1")],
        )
        await repo.save_remotes([remote])
        loaded = await repo.load_remotes()
        assert loaded[0].label == "Bedroom"
        assert loaded[0].device_address == "0xFB04"
