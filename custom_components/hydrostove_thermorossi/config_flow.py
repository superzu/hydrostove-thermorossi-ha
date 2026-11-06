"""Configurazione da interfaccia: si chiede solo l'indirizzo del modulo."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WinetClient, WinetError
from .const import DOMAIN, REG_POWER, REG_STATE, REG_WATER


class HydroStoveConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(host.lower())
            self._abort_if_unique_id_configured()
            client = WinetClient(async_get_clientsession(self.hass), host)
            try:
                regs, _ = await client.get_registers(1)
            except WinetError:
                errors["base"] = "cannot_connect"
            else:
                if not {REG_STATE, REG_POWER, REG_WATER} <= regs.keys():
                    errors["base"] = "unsupported"
                else:
                    name = user_input.get(CONF_NAME) or "Idrostufa"
                    return self.async_create_entry(
                        title=name, data={CONF_HOST: host, CONF_NAME: name}
                    )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
                vol.Optional(CONF_NAME, default=(user_input or {}).get(CONF_NAME, "Idrostufa")): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
