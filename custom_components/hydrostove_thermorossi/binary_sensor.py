"""Pompa di circolazione."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import StoveConfigEntry
from .const import BIT_PUMP, REG_STATE
from .entity import StoveEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: StoveConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([PumpSensor(entry.runtime_data, entry.entry_id)])


class PumpSensor(StoveEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:pump"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "pump")

    @property
    def is_on(self) -> bool | None:
        raw = self.reg(REG_STATE)
        return None if raw is None else bool(raw & BIT_PUMP)
