"""Hydro Stove Thermorossi: controllo locale delle idrostufe con modulo WiNet."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WinetClient
from .coordinator import StoveCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SELECT, Platform.SENSOR]

type StoveConfigEntry = ConfigEntry[StoveCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: StoveConfigEntry) -> bool:
    client = WinetClient(async_get_clientsession(hass), entry.data[CONF_HOST])
    coordinator = StoveCoordinator(hass, client, entry.data.get(CONF_NAME) or entry.title)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: StoveConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
