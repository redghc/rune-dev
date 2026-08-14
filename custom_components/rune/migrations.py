"""Schema migrations for rune.devices / rune.actions / rune.unknown_signals.

RUNE's stores use HA's ``Store`` version-bump mechanism. Bumping the
version constant in ``const.py`` triggers ``Store.async_load`` to
return the data as-is and ``async_save`` to re-write with the new
version. Between load and save, RUNE's ``async_migrate_entry`` calls
into :func:`run_migrations` with the loaded data; the chain of pure
migration functions transforms it from the old schema to the new one.

Each migration is a pure function ``list[dict] -> list[dict]`` that
records its delta in the logger. The runner executes them in order
and refuses to skip a version.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from custom_components.rune.domain.errors import MigrationError

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Migration registry
# ---------------------------------------------------------------------------

# A migration is a pure dict-list transformer plus a one-line description.
Migration = Callable[[list[dict]], list[dict]]

# Target versions (the schema after each migration step).
# Each migration bumps the version by 1; running v0->v1->v2 brings
# records from v0 to v2.
DEVICE_MIGRATIONS: dict[int, tuple[Migration, str]] = {}
ACTION_MIGRATIONS: dict[int, tuple[Migration, str]] = {}
SIGNAL_MIGRATIONS: dict[int, tuple[Migration, str]] = {}


def register_device_migration(
    target_version: int, description: str
) -> Callable[[Migration], Migration]:
    """Decorator that registers a device-store migration step."""

    def decorator(func: Migration) -> Migration:
        if target_version in DEVICE_MIGRATIONS:
            raise RuntimeError(
                f"Duplicate device migration for v{target_version}"
            )
        DEVICE_MIGRATIONS[target_version] = (func, description)
        return func

    return decorator


def register_action_migration(
    target_version: int, description: str
) -> Callable[[Migration], Migration]:
    def decorator(func: Migration) -> Migration:
        if target_version in ACTION_MIGRATIONS:
            raise RuntimeError(
                f"Duplicate action migration for v{target_version}"
            )
        ACTION_MIGRATIONS[target_version] = (func, description)
        return func

    return decorator


def register_signal_migration(
    target_version: int, description: str
) -> Callable[[Migration], Migration]:
    def decorator(func: Migration) -> Migration:
        if target_version in SIGNAL_MIGRATIONS:
            raise RuntimeError(
                f"Duplicate signal migration for v{target_version}"
            )
        SIGNAL_MIGRATIONS[target_version] = (func, description)
        return func

    return decorator


# ---------------------------------------------------------------------------
# Migration steps
# ---------------------------------------------------------------------------

@register_device_migration(
    1,
    "Initial v0→v1: pass-through (no schema changes yet).",
)
def _device_migrate_v0_to_v1(records: list[dict]) -> list[dict]:
    return list(records)


@register_action_migration(
    1,
    "Initial v0→v1: pass-through (no schema changes yet).",
)
def _action_migrate_v0_to_v1(records: list[dict]) -> list[dict]:
    return list(records)


@register_signal_migration(
    1,
    "Initial v0→v1: pass-through (no schema changes yet).",
)
def _signal_migrate_v0_to_v1(records: list[dict]) -> list[dict]:
    return list(records)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run(
    records: list[dict],
    table: dict[int, tuple[Migration, str]],
    *,
    store_label: str,
    from_version: int,
) -> tuple[list[dict], int]:
    """Walk ``table`` from ``from_version`` upward, transforming records.

    Returns the migrated records and the final version reached.

    Raises :class:`MigrationError` when ``from_version`` exceeds the
    latest registered migration (data is newer than this build knows
    how to handle — refuse rather than silently downgrade).
    """
    current_records = list(records)
    current_version = from_version
    latest = max(table) if table else 0
    if current_version > latest:
        raise MigrationError(
            f"{store_label}: data is at v{current_version}, but this build "
            f"only knows up to v{latest}. Upgrade rune."
        )
    next_version = current_version + 1
    while next_version in table:
        migration, description = table[next_version]
        try:
            current_records = migration(current_records)
        except (TypeError, ValueError, KeyError) as err:
            raise MigrationError(
                f"{store_label}: v{current_version}→v{next_version} "
                f"({description}) failed: {err}"
            ) from err
        _LOGGER.info(
            "rune: %s migrated v%d→v%d (%s); %d record(s)",
            store_label,
            current_version,
            next_version,
            description,
            len(current_records),
        )
        current_version = next_version
        next_version = current_version + 1
    return current_records, current_version


def migrate_devices(records: list[dict], *, from_version: int = 0) -> tuple[list[dict], int]:
    """Run the device-store migration chain."""
    return _run(records, DEVICE_MIGRATIONS, store_label="rune.devices", from_version=from_version)


def migrate_actions(records: list[dict], *, from_version: int = 0) -> tuple[list[dict], int]:
    return _run(records, ACTION_MIGRATIONS, store_label="rune.actions", from_version=from_version)


def migrate_signals(
    records: list[dict], *, from_version: int = 0
) -> tuple[list[dict], int]:
    return _run(
        records,
        SIGNAL_MIGRATIONS,
        store_label="rune.unknown_signals",
        from_version=from_version,
    )


# ---------------------------------------------------------------------------
# HA integration entry-point helper
# ---------------------------------------------------------------------------

LATEST_DEVICE_VERSION = max(DEVICE_MIGRATIONS) if DEVICE_MIGRATIONS else 0
LATEST_ACTION_VERSION = max(ACTION_MIGRATIONS) if ACTION_MIGRATIONS else 0
LATEST_SIGNAL_VERSION = max(SIGNAL_MIGRATIONS) if SIGNAL_MIGRATIONS else 0
