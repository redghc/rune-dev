"""Tests for the in-memory repository adapters."""
from __future__ import annotations

import pytest

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


# ---------------------------------------------------------------------------
# Device repository
# ---------------------------------------------------------------------------

class TestInMemoryDeviceRepository:
    @pytest.mark.asyncio
    async def test_initial_load_is_empty(self) -> None:
        repo = InMemoryDeviceRepository()
        assert await repo.load() == []

    @pytest.mark.asyncio
    async def test_save_and_load_round_trip(self) -> None:
        repo = InMemoryDeviceRepository()
        devices = [_device("a"), _device("b")]
        await repo.save(devices)
        loaded = await repo.load()
        assert [d.id for d in loaded] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_get_existing(self) -> None:
        repo = InMemoryDeviceRepository()
        await repo.save([_device("x")])
        device = await repo.get("x")
        assert device is not None
        assert device.id == "x"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self) -> None:
        repo = InMemoryDeviceRepository()
        assert await repo.get("nope") is None

    @pytest.mark.asyncio
    async def test_upsert_inserts_new(self) -> None:
        repo = InMemoryDeviceRepository()
        await repo.upsert(_device("new"))
        assert (await repo.get("new")) is not None

    @pytest.mark.asyncio
    async def test_upsert_replaces_existing(self) -> None:
        repo = InMemoryDeviceRepository()
        await repo.upsert(_device("x"))
        updated = _device("x")
        updated.name = "Renamed"
        await repo.upsert(updated)
        loaded = await repo.get("x")
        assert loaded is not None
        assert loaded.name == "Renamed"

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self) -> None:
        repo = InMemoryDeviceRepository()
        await repo.upsert(_device("x"))
        assert await repo.delete("x") is True
        assert await repo.get("x") is None

    @pytest.mark.asyncio
    async def test_delete_missing_returns_false(self) -> None:
        repo = InMemoryDeviceRepository()
        assert await repo.delete("nope") is False

    @pytest.mark.asyncio
    async def test_save_replaces_entire_collection(self) -> None:
        repo = InMemoryDeviceRepository()
        await repo.upsert(_device("a"))
        await repo.upsert(_device("b"))
        await repo.save([_device("c")])
        loaded = await repo.load()
        assert [d.id for d in loaded] == ["c"]


# ---------------------------------------------------------------------------
# Action repository
# ---------------------------------------------------------------------------

class TestInMemoryActionRepository:
    @pytest.mark.asyncio
    async def test_round_trip(self) -> None:
        repo = InMemoryActionRepository()
        await repo.save([_action("a"), _action("b")])
        loaded = await repo.load()
        assert [a.id for a in loaded] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_upsert_replaces(self) -> None:
        repo = InMemoryActionRepository()
        await repo.upsert(_action("x"))
        updated = _action("x")
        updated.name = "Renamed"
        await repo.upsert(updated)
        loaded = await repo.get("x")
        assert loaded is not None
        assert loaded.name == "Renamed"

    @pytest.mark.asyncio
    async def test_delete_missing_returns_false(self) -> None:
        repo = InMemoryActionRepository()
        assert await repo.delete("nope") is False


# ---------------------------------------------------------------------------
# Signal repository
# ---------------------------------------------------------------------------

class TestInMemorySignalRepository:
    @pytest.mark.asyncio
    async def test_initial_load_empty(self) -> None:
        repo = InMemorySignalRepository()
        assert await repo.load_remotes() == []

    @pytest.mark.asyncio
    async def test_upsert_signal_creates_remote_if_missing(self) -> None:
        repo = InMemorySignalRepository()
        await repo.upsert_signal("r-1", _signal("s-1"))
        remotes = await repo.load_remotes()
        assert len(remotes) == 1
        assert remotes[0].id == "r-1"
        assert len(remotes[0].signals) == 1

    @pytest.mark.asyncio
    async def test_upsert_signal_replaces_existing(self) -> None:
        repo = InMemorySignalRepository()
        await repo.upsert_signal("r-1", _signal("s-1"))
        updated_signal = _signal("s-1")
        updated_signal.hit_count = 5
        await repo.upsert_signal("r-1", updated_signal)
        remotes = await repo.load_remotes()
        assert len(remotes) == 1
        assert len(remotes[0].signals) == 1  # not duplicated
        assert remotes[0].signals[0].hit_count == 5

    @pytest.mark.asyncio
    async def test_remove_signal_drops_remote_when_last_signal_removed(self) -> None:
        repo = InMemorySignalRepository()
        await repo.upsert_signal("r-1", _signal("s-1"))
        assert await repo.remove_signal("r-1", "s-1") is True
        assert await repo.load_remotes() == []

    @pytest.mark.asyncio
    async def test_remove_signal_keeps_remote_with_others(self) -> None:
        repo = InMemorySignalRepository()
        await repo.upsert_signal("r-1", _signal("s-1"))
        await repo.upsert_signal("r-1", _signal("s-2"))
        assert await repo.remove_signal("r-1", "s-1") is True
        remotes = await repo.load_remotes()
        assert len(remotes) == 1
        assert len(remotes[0].signals) == 1
        assert remotes[0].signals[0].id == "s-2"

    @pytest.mark.asyncio
    async def test_remove_missing_returns_false(self) -> None:
        repo = InMemorySignalRepository()
        assert await repo.remove_signal("missing", "x") is False

    @pytest.mark.asyncio
    async def test_upsert_remote_replaces(self) -> None:
        repo = InMemorySignalRepository()
        remote = UnknownRemote(
            id="r-1",
            label="Bedroom remote",
            protocol_label="NEC",
            device_address="0xFB04",
            signals=[_signal("s-1")],
        )
        await repo.upsert_remote(remote)
        loaded = await repo.load_remotes()
        assert loaded[0].label == "Bedroom remote"

    @pytest.mark.asyncio
    async def test_save_replaces_collection(self) -> None:
        repo = InMemorySignalRepository()
        await repo.upsert_signal("r-1", _signal("s-1"))
        new_remote = UnknownRemote(
            id="r-2",
            label=None,
            protocol_label=None,
            device_address=None,
            signals=[],
        )
        await repo.save_remotes([new_remote])
        loaded = await repo.load_remotes()
        assert [r.id for r in loaded] == ["r-2"]
