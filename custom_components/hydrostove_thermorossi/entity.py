"""Entità base: tutte appartengono al dispositivo Idrostufa."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StoveCoordinator


class StoveEntity(CoordinatorEntity[StoveCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: StoveCoordinator, entry_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=coordinator.name,
            manufacturer="Thermorossi",
            model="Idrostufa con modulo WiNet",
        )

    def reg(self, register: int) -> int | None:
        return self.coordinator.data.registers.get(register) if self.coordinator.data else None
