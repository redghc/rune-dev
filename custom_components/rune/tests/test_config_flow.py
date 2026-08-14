"""Tests for the config flow.

The config flow requires ``homeassistant.config_entries`` at import
time so HA's flow-discovery can find the handler class. In a pure-Python
dev environment without HA installed, the module can't import — these
tests skip automatically in that case.
"""
from __future__ import annotations

import pytest

homeassistant = pytest.importorskip("homeassistant")

from custom_components.rune.config_flow import CATEGORY_OPTIONS  # noqa: E402


class TestCategoryOptions:
    def test_includes_all_supported_categories(self) -> None:
        values = {option["value"] for option in CATEGORY_OPTIONS}
        assert "fan" in values
        assert "climate" in values
        assert "light" in values
        assert "cover" in values
        assert "media_player" in values
        assert "switch" in values
        assert "remote" in values

    def test_each_option_has_label(self) -> None:
        for option in CATEGORY_OPTIONS:
            assert "label" in option
            assert option["label"]  # non-empty


class TestModuleImports:
    def test_flow_classes_exported(self) -> None:
        from custom_components.rune.config_flow import (
            RuneConfigFlow,
            RuneOptionsFlow,
            async_get_options_flow,
        )

        assert RuneConfigFlow is not None
        assert RuneOptionsFlow is not None
        assert async_get_options_flow is not None

    def test_options_flow_callable(self) -> None:
        from custom_components.rune.config_flow import async_get_options_flow

        # Fake config entry.
        class _Entry:
            entry_id = "test"

        flow = async_get_options_flow(_Entry())  # type: ignore[arg-type]
        assert flow is not None
