"""Selettore potenza: spegne, accende e cambia potenza come il tasto del pannello."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import StoveConfigEntry
from .const import POWER_AUTO, REG_POWER
from .entity import StoveEntity

OPTIONS = ["off", "1", "2", "3", "4", "auto"]
TO_VALUE = {"off": 0, "1": 1, "2": 2, "3": 3, "4": 4, "auto": POWER_AUTO}
FROM_VALUE = {v: k for k, v in TO_VALUE.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: StoveConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([PowerSelect(entry.runtime_data, entry.entry_id)])


class PowerSelect(StoveEntity, SelectEntity):
    _attr_options = OPTIONS
    _attr_icon = "mdi:fire-circle"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "power")

    @property
    def current_option(self) -> str | None:
        return FROM_VALUE.get(self.reg(REG_POWER))

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_write(REG_POWER, TO_VALUE[option])
