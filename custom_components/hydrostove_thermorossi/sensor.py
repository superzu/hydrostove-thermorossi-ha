"""Sensori: stato, potenza, temperature, segnale Wi-Fi."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import StoveConfigEntry
from .const import (
    COOLING_FLUE_THRESHOLD,
    PHASE_OFF,
    PHASE_START,
    PHASE_WORK,
    POWER_AUTO,
    REG_POWER,
    REG_FLUE,
    REG_STATE,
    REG_TARGET,
    REG_WATER,
)
from .entity import StoveEntity

STATES = ["off", "cooling", "starting", "working", "unknown"]


async def async_setup_entry(
    hass: HomeAssistant, entry: StoveConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    c = entry.runtime_data
    eid = entry.entry_id
    async_add_entities(
        [
            StateSensor(c, eid),
            PowerStateSensor(c, eid),
            TemperatureSensor(c, eid, "water_temperature", REG_WATER, measurement=True),
            TemperatureSensor(c, eid, "flue_temperature", REG_FLUE, measurement=True),
            TemperatureSensor(c, eid, "target_temperature", REG_TARGET, measurement=False),
            PhaseCodeSensor(c, eid),
            RssiSensor(c, eid),
        ]
    )


class StateSensor(StoveEntity, SensorEntity):
    """Stato leggibile: spenta, raffreddamento, accensione, lavoro."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATES
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "state")

    @property
    def native_value(self) -> str | None:
        raw = self.reg(REG_STATE)
        if raw is None:
            return None
        phase = raw % 256
        if phase == PHASE_OFF:
            flue = self.reg(REG_FLUE) or 0
            return "cooling" if flue > COOLING_FLUE_THRESHOLD else "off"
        return {PHASE_START: "starting", PHASE_WORK: "working"}.get(phase, "unknown")

    @property
    def extra_state_attributes(self):
        raw = self.reg(REG_STATE)
        return {"phase": raw % 256} if raw is not None else None


class PowerStateSensor(StoveEntity, SensorEntity):
    """Potenza attuale in sola lettura: spenta, 1, 2, 3, 4, auto."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["off", "1", "2", "3", "4", "auto"]
    _attr_icon = "mdi:fire-circle"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "power_state")

    @property
    def native_value(self) -> str | None:
        value = self.reg(REG_POWER)
        if value is None:
            return None
        if value == 0:
            return "off"
        if value == POWER_AUTO:
            return "auto"
        return str(value) if 1 <= value <= 4 else None


class TemperatureSensor(StoveEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    # La stufa fornisce solo gradi interi: niente decimali in interfaccia.
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator, entry_id, key, register, measurement):
        super().__init__(coordinator, entry_id, key)
        self._register = register
        if measurement:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        return self.reg(self._register)


class PhaseCodeSensor(StoveEntity, SensorEntity):
    """Valore grezzo del registro di stato, utile per segnalare fasi non ancora mappate."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "state_raw")

    @property
    def native_value(self) -> int | None:
        return self.reg(REG_STATE)


class RssiSensor(StoveEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "wifi_signal")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.rssi if self.coordinator.data else None
