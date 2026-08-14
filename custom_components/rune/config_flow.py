"""Config and options flows for RUNE.

The MVP flow has two screens:

1. **Device name + category** — what the user wants to control.
2. **Transmitter selection** — pick the IR/RF emitter entity.

The full "learn command" wizard (Phase 7 work) is intentionally
omitted here so a user can add a device and start using it with
pre-existing SmartIR profiles, broadlink codes, etc. Once Fase 7 lands
the config flow grows a third step.

HA imports live at module level — HA's config-flow discovery requires
the handler class to be a ``ConfigFlow`` subclass with a ``domain``
class attribute set to :data:`DOMAIN`. Deferring the import would
break that discovery.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from custom_components.rune.const import CONF_TRANSMITTER, DOMAIN
from custom_components.rune.domain.enums import EntityCategory

_LOGGER = logging.getLogger(__name__)


CATEGORY_OPTIONS = [
    selector.SelectOptionDict(value=c.value, label=c.value.title())
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


class RuneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Two-screen setup flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._device_name: str = ""
        self._category: str = EntityCategory.FAN.value
        self._transmitter: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: name + category."""
        if user_input is not None:
            self._device_name = user_input["name"]
            self._category = user_input["category"]
            return await self.async_step_transmitter()

        schema = vol.Schema(
            {
                vol.Required("name", default="My device"): selector.TextSelector(),
                vol.Required("category", default=EntityCategory.FAN.value): (
                    selector.SelectSelector(
                        selector.SelectSelectorConfig(options=CATEGORY_OPTIONS)
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_transmitter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: pick the emitter entity."""
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
        return self.async_show_form(step_id="transmitter", data_schema=schema)

    async def _async_create_entry(self) -> ConfigFlowResult:
        """Persist the entry with the collected data."""
        # Use the device name to derive a unique id.
        unique_id = f"{self._category}-{self._device_name}".lower().replace(" ", "-")
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self._device_name,
            data={
                "name": self._device_name,
                "category": self._category,
                CONF_TRANSMITTER: self._transmitter,
            },
        )


@callback
def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
    """Return the options flow handler.

    Phase 7 expands this; for the MVP the options flow is a no-op.
    """
    return RuneOptionsFlow()


class RuneOptionsFlow(OptionsFlow):
    """No-op options flow for MVP."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single empty step so HA renders the options page without errors."""
        return self.async_create_entry(title="", data={})
