"""Tests for the migration framework."""
from __future__ import annotations

import pytest

from custom_components.rune import migrations
from custom_components.rune.domain.errors import MigrationError
from custom_components.rune.migrations import (
    LATEST_DEVICE_VERSION,
    migrate_actions,
    migrate_devices,
    migrate_signals,
    register_device_migration,
    register_signal_migration,
)

# We test with a local chain so the v0→v1 pass-through already in the
# registry doesn't interfere.


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the migration registries between tests.

    The default v0→v1 step is fine, but tests that register v2 may
    conflict. We snapshot the registry on entry and restore on exit.
    """
    snapshots = {
        "device": dict(migrations.DEVICE_MIGRATIONS),
        "action": dict(migrations.ACTION_MIGRATIONS),
        "signal": dict(migrations.SIGNAL_MIGRATIONS),
    }
    yield
    migrations.DEVICE_MIGRATIONS.clear()
    migrations.ACTION_MIGRATIONS.clear()
    migrations.SIGNAL_MIGRATIONS.clear()
    migrations.DEVICE_MIGRATIONS.update(snapshots["device"])
    migrations.ACTION_MIGRATIONS.update(snapshots["action"])
    migrations.SIGNAL_MIGRATIONS.update(snapshots["signal"])


class TestDefaultRegistry:
    def test_device_v1_present(self) -> None:
        assert 1 in migrate_devices.__globals__["DEVICE_MIGRATIONS"]

    def test_latest_versions(self) -> None:
        # The shipped registry has only v1 today.
        assert LATEST_DEVICE_VERSION == 1


class TestMigrationChain:
    def test_passthrough_returns_records_unchanged(self) -> None:
        records = [{"id": "x"}, {"id": "y"}]
        result, version = migrate_devices(records, from_version=0)
        assert result == records
        assert version == 1

    def test_empty_input(self) -> None:
        result, version = migrate_devices([], from_version=0)
        assert result == []
        assert version == 1

    def test_chain_of_two_migrations(self) -> None:
        @register_device_migration(2, "Test: stamp version field.")
        def _stamp(records: list[dict]) -> list[dict]:
            return [{**r, "migrated": True} for r in records]

        records = [{"id": "a"}]
        result, version = migrate_devices(records, from_version=0)
        assert version == 2
        assert result == [{"id": "a", "migrated": True}]

    def test_skipping_version_raises(self) -> None:
        # Migrating from v3 when only v1 exists in the registry.
        with pytest.raises(MigrationError):
            migrate_devices([], from_version=3)

    def test_migration_exception_wrapped(self) -> None:
        @register_device_migration(2, "Test: always explode.")
        def _boom(records: list[dict]) -> list[dict]:
            raise ValueError("nope")

        with pytest.raises(MigrationError, match="nope"):
            migrate_devices([{}], from_version=0)


class TestActionAndSignalChains:
    def test_action_passthrough(self) -> None:
        records = [{"id": "a"}]
        result, version = migrate_actions(records, from_version=0)
        assert result == records
        assert version == 1

    def test_signal_passthrough(self) -> None:
        records = [{"id": "r"}]
        result, version = migrate_signals(records, from_version=0)
        assert result == records
        assert version == 1

    def test_signal_v2_via_decorator(self) -> None:
        @register_signal_migration(2, "Test: add schema_version field.")
        def _stamp(records: list[dict]) -> list[dict]:
            return [{**r, "schema_version": 2} for r in records]

        records = [{"id": "r"}]
        result, version = migrate_signals(records, from_version=0)
        assert version == 2
        assert result[0]["schema_version"] == 2
