"""Temperatura target dell'acqua (65-73 °C)."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import StoveConfigEntry
from .const import REG_TARGET, TARGET_MAX, TARGET_MIN
from .entity import StoveEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: StoveConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([TargetNumber(entry.runtime_data, entry.entry_id)])


class TargetNumber(StoveEntity, NumberEntity):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = TARGET_MIN
    _attr_native_max_value = TARGET_MAX
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:thermometer-water"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "water_target")

    @property
    def native_value(self) -> float | None:
        return self.reg(REG_TARGET)

    async def async_set_native_value(self, value: float) -> None:
        # Limite ribadito anche qui: mai valori fuori range verso la scheda.
        target = int(min(max(round(value), TARGET_MIN), TARGET_MAX))
        await self.coordinator.async_write(REG_TARGET, target)
