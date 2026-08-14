"""Repository ports — persistence contracts for the three aggregates.

RUNE persists three separate aggregates to three separate HA Stores so
corruption in one cannot damage the others (the HAIR lesson learned the
hard way):

- :class:`DeviceRepository` — :class:`~custom_components.rune.domain.models.RuneDevice`
- :class:`ActionRepository` — :class:`~custom_components.rune.domain.models.ActionBinding`
- :class:`SignalRepository` — :class:`~custom_components.rune.domain.models.UnknownRemote`

All three follow the same shape:

- ``load()`` returns the full collection (empty list on first boot).
- ``save(items)`` replaces the entire collection atomically.
- ``upsert(item)`` / ``get(id)`` / ``delete(id)`` for single-item
  operations.

The ``save`` semantics are deliberate: the on-disk format is a single
JSON document, so partial updates would require a read-modify-write
cycle inside the adapter. We sidestep that by always serializing the
full collection. For RUNE's payload sizes (tens of devices, hundreds
of commands) this is cheaper than the HAIR-style per-item store.
"""
from __future__ import annotations

from typing import Protocol

from custom_components.rune.domain.models import (
    ActionBinding,
    RuneDevice,
    UnknownRemote,
    UnknownSignal,
)


class DeviceRepository(Protocol):
    """Persistence for :class:`RuneDevice` aggregates."""

    async def load(self) -> list[RuneDevice]:
        """Return every persisted device, or ``[]`` if the store is empty."""
        ...

    async def save(self, devices: list[RuneDevice]) -> None:
        """Replace the entire collection atomically."""
        ...

    async def get(self, device_id: str) -> RuneDevice | None:
        """Return the device at ``device_id`` or ``None``."""
        ...

    async def upsert(self, device: RuneDevice) -> None:
        """Insert or replace one device."""
        ...

    async def delete(self, device_id: str) -> bool:
        """Remove one device. Returns ``True`` if it existed."""
        ...


class ActionRepository(Protocol):
    """Persistence for :class:`ActionBinding` aggregates."""

    async def load(self) -> list[ActionBinding]:
        ...

    async def save(self, actions: list[ActionBinding]) -> None:
        ...

    async def get(self, action_id: str) -> ActionBinding | None:
        ...

    async def upsert(self, action: ActionBinding) -> None:
        ...

    async def delete(self, action_id: str) -> bool:
        ...


class SignalRepository(Protocol):
    """Persistence for the unknown-signal catalog."""

    async def load_remotes(self) -> list[UnknownRemote]:
        """Return every persisted remote with its signals."""
        ...

    async def save_remotes(self, remotes: list[UnknownRemote]) -> None:
        """Replace the entire collection atomically."""
        ...

    async def upsert_signal(self, remote_id: str, signal: UnknownSignal) -> None:
        """Insert or replace a signal inside ``remote_id``.

        Creates the remote if it does not yet exist.
        """
        ...

    async def remove_signal(self, remote_id: str, signal_id: str) -> bool:
        """Remove a signal by id. Returns True if removed."""
        ...

    async def upsert_remote(self, remote: UnknownRemote) -> None:
        """Insert or replace an entire remote (used for aliasing / dismissal)."""
        ...
