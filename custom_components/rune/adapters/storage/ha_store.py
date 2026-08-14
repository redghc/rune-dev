"""Home Assistant Store adapters — production persistence.

Each adapter wraps a single ``homeassistant.helpers.storage.Store``
and exposes the same repository contract as :mod:`memory`. The Store
API is async and atomic per save, so the in-memory patterns translate
directly.

Three separate stores (matching the three ``STORAGE_KEY`` constants in
``const.py``):

- :class:`HAStoreDeviceRepository` → ``rune.devices``
- :class:`HAStoreActionRepository` → ``rune.actions``
- :class:`HAStoreSignalRepository` → ``rune.unknown_signals``

Why three stores instead of one combined doc?

- Corruption in one cannot damage the others (HAIR's signal-store
  failure mode).
- Per-store version bumps let us migrate independently — the unknown
  catalog evolves faster than the device catalog.
- Smaller files mean smaller atomic writes, less memory under
  ``Store.async_load`` (which holds the whole document in memory).
"""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from custom_components.rune.const import (
    ACTION_STORAGE_KEY,
    ACTION_STORAGE_VERSION,
    DEVICE_STORAGE_KEY,
    DEVICE_STORAGE_VERSION,
    UNKNOWN_SIGNAL_STORAGE_KEY,
    UNKNOWN_SIGNAL_STORAGE_VERSION,
)
from custom_components.rune.domain.errors import StorageError
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

_LOGGER = logging.getLogger(__name__)


def _records_to_dicts(items: list) -> list[dict]:
    return [item.to_dict() for item in items]


def _devices_from_dicts(records: list[dict]) -> list[RuneDevice]:
    devices: list[RuneDevice] = []
    for record in records:
        try:
            devices.append(RuneDevice.from_dict(record))
        except (TypeError, ValueError, KeyError) as err:
            _LOGGER.error(
                "rune: skipping malformed device record (id=%s): %s",
                record.get("id") if isinstance(record, dict) else None,
                err,
            )
    return devices


def _actions_from_dicts(records: list[dict]) -> list[ActionBinding]:
    actions: list[ActionBinding] = []
    for record in records:
        try:
            actions.append(ActionBinding.from_dict(record))
        except (TypeError, ValueError, KeyError) as err:
            _LOGGER.error(
                "rune: skipping malformed action record (id=%s): %s",
                record.get("id") if isinstance(record, dict) else None,
                err,
            )
    return actions


def _remotes_from_dicts(records: list[dict]) -> list[UnknownRemote]:
    remotes: list[UnknownRemote] = []
    for record in records:
        try:
            remotes.append(UnknownRemote.from_dict(record))
        except (TypeError, ValueError, KeyError) as err:
            _LOGGER.error(
                "rune: skipping malformed unknown remote record (id=%s): %s",
                record.get("id") if isinstance(record, dict) else None,
                err,
            )
    return remotes


# ---------------------------------------------------------------------------
# Device repository
# ---------------------------------------------------------------------------

class HAStoreDeviceRepository(DeviceRepository):
    """Device persistence backed by an HA Store."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store = Store[list[dict]](
            hass,
            DEVICE_STORAGE_VERSION,
            DEVICE_STORAGE_KEY,
        )

    async def load(self) -> list[RuneDevice]:
        records = await self._async_load_records()
        return _devices_from_dicts(records)

    async def save(self, devices: list[RuneDevice]) -> None:
        await self._store.async_save(_records_to_dicts(devices))

    async def get(self, device_id: str) -> RuneDevice | None:
        for device in await self.load():
            if device.id == device_id:
                return device
        return None

    async def upsert(self, device: RuneDevice) -> None:
        devices = await self.load()
        replaced = False
        for index, existing in enumerate(devices):
            if existing.id == device.id:
                devices[index] = device
                replaced = True
                break
        if not replaced:
            devices.append(device)
        await self.save(devices)

    async def delete(self, device_id: str) -> bool:
        devices = await self.load()
        filtered = [d for d in devices if d.id != device_id]
        if len(filtered) == len(devices):
            return False
        await self.save(filtered)
        return True

    async def _async_load_records(self) -> list[dict]:
        try:
            records = await self._store.async_load()
        except (OSError, ValueError) as err:
            raise StorageError(f"Failed to load rune.devices: {err}") from err
        if records is None:
            return []
        if not isinstance(records, list):
            raise StorageError(
                f"rune.devices expected a list, got {type(records).__name__}"
            )
        return records


# ---------------------------------------------------------------------------
# Action repository
# ---------------------------------------------------------------------------

class HAStoreActionRepository(ActionRepository):
    """Action persistence backed by an HA Store."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store = Store[list[dict]](
            hass,
            ACTION_STORAGE_VERSION,
            ACTION_STORAGE_KEY,
        )

    async def load(self) -> list[ActionBinding]:
        records = await self._async_load_records()
        return _actions_from_dicts(records)

    async def save(self, actions: list[ActionBinding]) -> None:
        await self._store.async_save(_records_to_dicts(actions))

    async def get(self, action_id: str) -> ActionBinding | None:
        for action in await self.load():
            if action.id == action_id:
                return action
        return None

    async def upsert(self, action: ActionBinding) -> None:
        actions = await self.load()
        replaced = False
        for index, existing in enumerate(actions):
            if existing.id == action.id:
                actions[index] = action
                replaced = True
                break
        if not replaced:
            actions.append(action)
        await self.save(actions)

    async def delete(self, action_id: str) -> bool:
        actions = await self.load()
        filtered = [a for a in actions if a.id != action_id]
        if len(filtered) == len(actions):
            return False
        await self.save(filtered)
        return True

    async def _async_load_records(self) -> list[dict]:
        try:
            records = await self._store.async_load()
        except (OSError, ValueError) as err:
            raise StorageError(f"Failed to load rune.actions: {err}") from err
        if records is None:
            return []
        if not isinstance(records, list):
            raise StorageError(
                f"rune.actions expected a list, got {type(records).__name__}"
            )
        return records


# ---------------------------------------------------------------------------
# Signal repository
# ---------------------------------------------------------------------------

class HAStoreSignalRepository(SignalRepository):
    """Unknown-signal persistence backed by an HA Store."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store = Store[list[dict]](
            hass,
            UNKNOWN_SIGNAL_STORAGE_VERSION,
            UNKNOWN_SIGNAL_STORAGE_KEY,
        )

    async def load_remotes(self) -> list[UnknownRemote]:
        records = await self._async_load_records()
        return _remotes_from_dicts(records)

    async def save_remotes(self, remotes: list[UnknownRemote]) -> None:
        await self._store.async_save(_records_to_dicts(remotes))

    async def upsert_signal(self, remote_id: str, signal: UnknownSignal) -> None:
        remotes = await self.load_remotes()
        target_index = next(
            (i for i, r in enumerate(remotes) if r.id == remote_id),
            None,
        )
        if target_index is None:
            remotes.append(
                UnknownRemote(
                    id=remote_id,
                    label=None,
                    protocol_label=signal.protocol_label,
                    device_address=signal.device_address,
                    signals=[signal],
                    first_seen=signal.first_seen,
                    last_seen=signal.last_seen,
                )
            )
            await self.save_remotes(remotes)
            return
        existing = remotes[target_index]
        updated_signals = [s for s in existing.signals if s.id != signal.id]
        updated_signals.append(signal)
        remotes[target_index] = UnknownRemote(
            id=existing.id,
            label=existing.label,
            protocol_label=existing.protocol_label,
            device_address=existing.device_address,
            signals=updated_signals,
            dismissed=existing.dismissed,
            first_seen=existing.first_seen,
            last_seen=signal.last_seen,
            hit_count=existing.hit_count,
            source=existing.source,
        )
        await self.save_remotes(remotes)

    async def remove_signal(self, remote_id: str, signal_id: str) -> bool:
        remotes = await self.load_remotes()
        target_index = next(
            (i for i, r in enumerate(remotes) if r.id == remote_id),
            None,
        )
        if target_index is None:
            return False
        existing = remotes[target_index]
        if not existing.remove_signal(signal_id):
            return False
        if existing.signals:
            remotes[target_index] = existing
        else:
            remotes.pop(target_index)
        await self.save_remotes(remotes)
        return True

    async def upsert_remote(self, remote: UnknownRemote) -> None:
        remotes = await self.load_remotes()
        replaced = False
        for index, existing in enumerate(remotes):
            if existing.id == remote.id:
                remotes[index] = remote
                replaced = True
                break
        if not replaced:
            remotes.append(remote)
        await self.save_remotes(remotes)

    async def _async_load_records(self) -> list[dict]:
        try:
            records = await self._store.async_load()
        except (OSError, ValueError) as err:
            raise StorageError(f"Failed to load rune.unknown_signals: {err}") from err
        if records is None:
            return []
        if not isinstance(records, list):
            raise StorageError(
                f"rune.unknown_signals expected a list, got {type(records).__name__}"
            )
        return records
