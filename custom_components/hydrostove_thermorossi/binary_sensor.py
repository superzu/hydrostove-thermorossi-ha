"""Sensori binari: stato generale della stufa e pompa di circolazione."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import StoveConfigEntry
from .const import BIT_PUMP, REG_POWER, REG_STATE
from .entity import StoveEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: StoveConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    c = entry.runtime_data
    async_add_entities([StoveOnSensor(c, entry.entry_id), PumpSensor(c, entry.entry_id)])


class StoveOnSensor(StoveEntity, BinarySensorEntity):
    """Stato generale: acceso con potenza 1-4 o Auto, spento con potenza 0."""

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "stove")

    @property
    def is_on(self) -> bool | None:
        power = self.reg(REG_POWER)
        return None if power is None else power != 0

    @property
    def icon(self) -> str:
        return "mdi:fire" if self.is_on else "mdi:fire-off"


class PumpSensor(StoveEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:pump"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "pump")

    @property
    def is_on(self) -> bool | None:
        raw = self.reg(REG_STATE)
        return None if raw is None else bool(raw & BIT_PUMP)
