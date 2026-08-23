"""Config and options flows for RUNE.

Two distinct surfaces, matching the HAIR pattern:

- :class:`RuneConfigFlow` — *integration* setup. Runs once when the
  user adds the integration from **Settings → Devices & Services**.
  Just creates the integration entry; it does NOT create any device.
- :class:`RuneOptionsFlow` — *device* management. Runs every time the
  user opens **Configure** on the integration entry. Provides a menu
  with "Add device" (the wizard that builds a new RuneDevice) and
  "Manage devices" (read-only listing for the MVP; CRUD arrives in
  Phase 7).

Devices are independent from the integration entry: they live in
their own HA Store under :data:`DEVICE_STORAGE_KEY`, so removing and
re-adding the integration preserves the user's catalog.

HA imports live at module level — HA's flow-discovery requires the
handler class to be a :class:`ConfigFlow` subclass with a ``domain``
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

from custom_components.rune.const import (
    CONF_CATEGORY,
    CONF_NAME,
    CONF_TRANSMITTER,
    DOMAIN,
)
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


# ---------------------------------------------------------------------------
# Integration entry flow
# ---------------------------------------------------------------------------


class RuneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-screen setup flow that creates the integration entry.

    HA's "Add Integration" UI calls this. The only step collects the
    integration's display name (default: "RUNE") and then immediately
    persists the entry — no device data is gathered at this stage.
    Devices are added afterwards through the options flow.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single step: confirm the integration is added."""
        if user_input is not None:
            # Use the user-supplied name (or default) as the entry title.
            title = user_input.get("name") or "RUNE"
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=title, data={})

        schema = vol.Schema(
            {
                vol.Optional("name", default="RUNE"): selector.TextSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)


# ---------------------------------------------------------------------------
# Device management (options flow)
# ---------------------------------------------------------------------------


@callback
def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
    """Return the per-entry options flow for device management."""
    return RuneOptionsFlow()


class RuneOptionsFlow(OptionsFlow):
    """Per-integration options flow.

    Menu:

    - **Add device** — wizard that adds a new RuneDevice to the store.
    - **Manage devices** — read-only listing (full CRUD lands in
      Phase 7 once the WebSocket ``rune.device/create`` path is wired
      end-to-end and the SPA panel ships).

    The flow reads the live device list on each step so changes made
    outside the UI (via service calls or WebSocket) reflect immediately.
    """

    def __init__(self) -> None:
        # Populated by the framework before each step.
        self._devices: list[Any] = []
        # Stashed by the add-device wizard between steps.
        self._pending_name: str = ""
        self._pending_category: str = EntityCategory.FAN.value

    async def _load_devices(self) -> list[Any]:
        """Pull the current device list from the entry's cache."""
        return self._devices

    def _empty_state_message(self) -> str:
        """Localized empty-state copy for the manage-devices step.

        Kept inline (not in ``translations/{en,es}.json``) because the
        description-placeholder values are not translated by HA's
        translation machinery — only the surrounding ``description``
        template is. The strings match ``config.step.manage_devices``
        semantically; if you add a real translation key for them later,
        route this through :func:`translation.async_get_translations`.
        """
        language = getattr(self.hass.config, "language", "en")
        messages = {
            "es": "_Aún no hay dispositivos. Usa **Añadir dispositivo** para crear uno._",
            "en": "_No devices yet. Use **Add device** to create one._",
        }
        return messages.get(language, messages["en"])

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Main menu."""
        if user_input is not None:
            selection = user_input.get("action")
            if selection == "add_device":
                return await self.async_step_add_device_name()
            if selection == "manage_devices":
                return await self.async_step_manage_devices()

            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required("action"): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                translation_key="menu",
                                options=[
                                    {"value": "add_device"},
                                    {"value": "manage_devices"},
                                ],
                            )
                        ),
                    }
                ),
            )

    # ------------------------------------------------------------------
    # Add device wizard
    # ------------------------------------------------------------------

    async def async_step_add_device_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: name + category."""
        if user_input is not None:
            # Stash for the next step.
            self._pending_name = user_input[CONF_NAME]
            self._pending_category = user_input[CONF_CATEGORY]
            return await self.async_step_add_device_transmitter()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Required(
                    CONF_CATEGORY, default=EntityCategory.FAN.value
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=CATEGORY_OPTIONS)
                ),
            }
        )
        return self.async_show_form(
            step_id="add_device_name", data_schema=schema
        )

    async def async_step_add_device_transmitter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: pick the IR/RF transmitter entity."""
        if user_input is not None:
            transmitter = user_input[CONF_TRANSMITTER]
            # Persist via the WebSocket-side handler. The SPA and the
            # WebSocket API both delegate to this same code path so
            # the YAML-style config flow and the panel create devices
            # identically.
            from custom_components.rune.websocket_api import (
                RuneWebSocketContext,
                _ws_device_create,
            )

            ctx = RuneWebSocketContext(
                hass=self.hass,
                connection_id=None,
            )
            try:
                payload = {
                    "name": self._pending_name,
                    "category": self._pending_category,
                    CONF_TRANSMITTER: transmitter,
                }
                # _ws_device_create returns the device dict on success.
                # We call it from the flow context so any exception
                # surfaces as a form error rather than crashing HA.
                created = await _ws_device_create(ctx, payload)
            except Exception as err:
                _LOGGER.warning("rune add-device: %s", err)
                return self.async_show_form(
                    step_id="add_device_transmitter",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_TRANSMITTER): selector.EntitySelector(
                                selector.EntitySelectorConfig(
                                    domain=[
                                        "infrared",
                                        "remote",
                                        "radio_frequency",
                                        "esphome",
                                    ],
                                )
                            ),
                        }
                    ),
                    errors={"base": str(err)},
                )

            # Refresh the cached device list for the menu.
            entry_data = self.hass.data.get(DOMAIN, {}).get(
                self.config_entry.entry_id, {}
            )
            self._devices = entry_data.get("_flow_devices_cache", [])

            return self.async_create_entry(
                title="",
                data={
                    "created_device_id": created.get("device", {}).get("id", ""),
                    "action": "device_added",
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_TRANSMITTER): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["infrared", "remote", "radio_frequency", "esphome"],
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="add_device_transmitter", data_schema=schema
        )

    # ------------------------------------------------------------------
    # Manage devices (read-only MVP)
    # ------------------------------------------------------------------

    async def async_step_manage_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Read-only listing of every RuneDevice in the store."""
        # Pull the live list — we don't store anything on the entry.
        from custom_components.rune.adapters.storage.ha_store import (
            HAStoreDeviceRepository,
        )

        repo = HAStoreDeviceRepository(self.hass)
        devices = await repo.load()

        # Per-device lines stay as data (the user picked these names); the
        # surrounding prose is owned by ``translations/{en,es}.json`` via
        # the ``device_list`` and ``empty_message`` placeholders so the
        # whole block can be translated.
        empty_message = self._empty_state_message() if not devices else ""

        if devices:
            device_list = "\n".join(
                f"• **{d.name}** ({d.category.value}, {len(d.commands)})"
                for d in devices
            )
        else:
            device_list = ""

        return self.async_show_form(
            step_id="manage_devices",
            data_schema=vol.Schema({}),
            description_placeholders={
                "device_count": str(len(devices)),
                "device_list": device_list,
                "empty_message": empty_message,
            },
        )
