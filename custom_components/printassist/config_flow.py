"""Config flow for PrintAssist integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import DOMAIN, CONF_PRINTER_ENTITY


class PrintAssistConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PrintAssist."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="PrintAssist",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Optional(CONF_PRINTER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }),
            description_placeholders={
                "description": "Configure PrintAssist to manage your 3D printing queue."
            },
        )
