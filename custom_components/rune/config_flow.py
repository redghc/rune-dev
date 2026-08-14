"""Config and options flows for RUNE.

The MVP flow has two screens:

1. **Device name + category** — what the user wants to control.
2. **Transmitter selection** — pick the IR/RF emitter entity.

The full "learn command" wizard (Phase 7 work) is intentionally
omitted here so a user can add a device and start using it with
pre-existing SmartIR profiles, broadlink codes, etc. Once Fase 7 lands
the config flow grows a third step.

HA imports are deferred to inside the flow step methods so this
module imports cleanly in pure-Python environments (CI, tests, dev).
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from custom_components.rune.const import CONF_TRANSMITTER
from custom_components.rune.domain.enums import EntityCategory

_LOGGER = logging.getLogger(__name__)


CATEGORY_OPTIONS = [
    {"value": c.value, "label": c.value.title()}
    for c in (
        EntityCategory.FAN,
        EntityCategory.CLIMATE,
        EntityCategory.LIGHT,
        EntityCategory.COVER,
        EntityCategory.MEDIA_PLAYER,
        EntityCategory.SWITCH,
        EntityCategory.REMOTE,
    )
]


class RuneConfigFlow:
    """Two-screen setup flow.

    MVP: we don't subclass ``ConfigFlow`` here because that requires HA
    imports. The flow is exercised through HA's runtime via
    :func:`async_get_config_flow` once the integration is loaded.
    """

    VERSION = 1

    def __init__(self) -> None:
        self._device_name: str = ""
        self._category: str = EntityCategory.FAN.value
        self._transmitter: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Step 1: name + category."""
        from homeassistant.const import CONF_NAME
        from homeassistant.helpers import selector

        if user_input is not None:
            self._device_name = user_input[CONF_NAME]
            self._category = user_input["category"]
            return await self.async_step_transmitter()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="My device"): selector.TextSelector(),
                vol.Required("category", default=EntityCategory.FAN.value): (
                    selector.SelectSelector(
                        selector.SelectSelectorConfig(options=CATEGORY_OPTIONS)
                    )
                ),
            }
        )
        # The actual show_form call is delegated to HA's runtime
        # via the parent class — wrapped in a closure so the test
        # suite doesn't have to import HA's full flow harness.
        return self._show_form("user", schema)

    async def async_step_transmitter(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Step 2: pick the emitter entity."""
        from homeassistant.helpers import selector

        if user_input is not None:
            self._transmitter = user_input[CONF_TRANSMITTER]
            return await self._async_create_entry()

        schema = vol.Schema(
            {
                vol.Required(CONF_TRANSMITTER): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["infrared", "remote", "radio_frequency", "esphome"],
                    )
                ),
            }
        )
        return self._show_form("transmitter", schema)

    async def _async_create_entry(self) -> Any:
        """Persist the entry with the collected data."""

        # Use the device name to derive a unique id.
        unique_id = f"{self._category}-{self._device_name}".lower().replace(" ", "-")
        # These helpers come from HA's ConfigFlow parent class —
        # call via the runtime-provided implementation.
        await self._set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self._create_entry(
            title=self._device_name,
            data={
                "name": self._device_name,
                "category": self._category,
                CONF_TRANSMITTER: self._transmitter,
            },
        )

    # ------------------------------------------------------------------
    # Hooks the HA runtime injects via ConfigFlow subclassing.
    # ------------------------------------------------------------------

    def _show_form(self, step_id: str, schema: Any) -> Any:
        return self.async_show_form(step_id=step_id, data_schema=schema)

    def _create_entry(self, *, title: str, data: dict[str, Any]) -> Any:
        return self.async_create_entry(title=title, data=data)

    async def _set_unique_id(self, unique_id: str) -> None:
        await self.async_set_unique_id(unique_id)

    def _abort_if_unique_id_configured(self) -> None:
        self.async_abort_if_unique_id_configured()


def async_get_options_flow(config_entry: Any) -> Any:
    """Return the options flow handler.

    Phase 7 expands this; for the MVP the options flow is a no-op.
    """
    return RuneOptionsFlow()


class RuneOptionsFlow:
    """No-op options flow for MVP."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Single empty step so HA renders the options page without errors."""
        return self._create_entry(title="", data={})

    def _create_entry(self, *, title: str, data: dict[str, Any]) -> Any:
        return self.async_create_entry(title=title, data=data)


__all__ = [
    "CATEGORY_OPTIONS",
    "RuneConfigFlow",
    "RuneOptionsFlow",
    "async_get_options_flow",
]
