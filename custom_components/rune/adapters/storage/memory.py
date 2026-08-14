"""In-memory repository adapters — for tests and the integration's
boot-before-store-loads state.

These are full implementations of the repository ports with no
Home Assistant dependency. They are the canonical contract tests
verify against, and the factory uses them as a fallback when a Store
hasn't loaded yet.
"""
from __future__ import annotations

import asyncio

from custom_components.rune.domain.models import (
    ActionBinding,
    RuneDevice,
    UnknownRemote,
    UnknownSignal,
)
from custom_components.rune.ports.repository import (
    ActionRepository,
    DeviceRepository,
    SignalRepository,
)


class InMemoryDeviceRepository(DeviceRepository):
    """In-process :class:`DeviceRepository`.

    Thread-safe enough for HA's single-threaded event loop. Uses an
    ``asyncio.Lock`` so concurrent ``upsert`` / ``delete`` calls from
    multiple coroutines don't race.
    """

    def __init__(self) -> None:
        self._devices: dict[str, RuneDevice] = {}
        self._lock = asyncio.Lock()

    async def load(self) -> list[RuneDevice]:
        async with self._lock:
            return list(self._devices.values())

    async def save(self, devices: list[RuneDevice]) -> None:
        async with self._lock:
            self._devices = {d.id: d for d in devices}

    async def get(self, device_id: str) -> RuneDevice | None:
        async with self._lock:
            return self._devices.get(device_id)

    async def upsert(self, device: RuneDevice) -> None:
        async with self._lock:
            self._devices[device.id] = device

    async def delete(self, device_id: str) -> bool:
        async with self._lock:
            return self._devices.pop(device_id, None) is not None


class InMemoryActionRepository(ActionRepository):
    """In-process :class:`ActionRepository`."""

    def __init__(self) -> None:
        self._actions: dict[str, ActionBinding] = {}
        self._lock = asyncio.Lock()

    async def load(self) -> list[ActionBinding]:
        async with self._lock:
            return list(self._actions.values())

    async def save(self, actions: list[ActionBinding]) -> None:
        async with self._lock:
            self._actions = {a.id: a for a in actions}

    async def get(self, action_id: str) -> ActionBinding | None:
        async with self._lock:
            return self._actions.get(action_id)

    async def upsert(self, action: ActionBinding) -> None:
        async with self._lock:
            self._actions[action.id] = action

    async def delete(self, action_id: str) -> bool:
        async with self._lock:
            return self._actions.pop(action_id, None) is not None


class InMemorySignalRepository(SignalRepository):
    """In-process :class:`SignalRepository`.

    Stores remotes keyed by ``remote.id``. Signals inside each remote
    are stored as ``list[UnknownSignal]`` and identified by ``signal.id``.
    """

    def __init__(self) -> None:
        self._remotes: dict[str, UnknownRemote] = {}
        self._lock = asyncio.Lock()

    async def load_remotes(self) -> list[UnknownRemote]:
        async with self._lock:
            return list(self._remotes.values())

    async def save_remotes(self, remotes: list[UnknownRemote]) -> None:
        async with self._lock:
            self._remotes = {r.id: r for r in remotes}

    async def upsert_signal(self, remote_id: str, signal: UnknownSignal) -> None:
        async with self._lock:
            remote = self._remotes.get(remote_id)
            if remote is None:
                remote = UnknownRemote(
                    id=remote_id,
                    label=None,
                    protocol_label=signal.protocol_label,
                    device_address=None,
                    signals=[],
                )
                self._remotes[remote_id] = remote
            updated_signals = [s for s in remote.signals if s.id != signal.id]
            updated_signals.append(signal)
            self._remotes[remote_id] = UnknownRemote(
                id=remote.id,
                label=remote.label,
                protocol_label=remote.protocol_label,
                device_address=remote.device_address,
                signals=updated_signals,
                dismissed=remote.dismissed,
                first_seen=remote.first_seen,
                last_seen=signal.last_seen,
                hit_count=remote.hit_count,
                source=remote.source,
            )

    async def remove_signal(self, remote_id: str, signal_id: str) -> bool:
        async with self._lock:
            remote = self._remotes.get(remote_id)
            if remote is None:
                return False
            if not remote.remove_signal(signal_id):
                return False
            if remote.signals:
                self._remotes[remote_id] = remote
            else:
                # Remote has no more signals — drop it.
                self._remotes.pop(remote_id, None)
            return True

    async def upsert_remote(self, remote: UnknownRemote) -> None:
        async with self._lock:
            self._remotes[remote.id] = remote
