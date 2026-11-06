"""Coordinator: una sola lettura per tutte le entità."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WinetClient, WinetError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class StoveData:
    registers: dict[int, int]
    rssi: int | None


class StoveCoordinator(DataUpdateCoordinator[StoveData]):
    """Interroga il modulo WiNet a intervalli regolari."""

    def __init__(self, hass: HomeAssistant, client: WinetClient, name: str) -> None:
        super().__init__(hass, _LOGGER, name=name, update_interval=DEFAULT_SCAN_INTERVAL)
        self.client = client

    async def _async_update_data(self) -> StoveData:
        try:
            regs, rssi = await self.client.get_registers(1)
        except WinetError as err:
            raise UpdateFailed(f"Modulo WiNet non raggiungibile: {err}") from err
        return StoveData(regs, rssi)

    async def async_write(self, register: int, value: int) -> None:
        """Scrive un registro e aggiorna subito i dati."""
        try:
            await self.client.set_register(register, value)
        except WinetError as err:
            raise HomeAssistantError(f"Comando non riuscito: {err}") from err
        await asyncio.sleep(1.5)
        await self.async_request_refresh()
