"""Client per l'API HTTP locale del modulo WiNet."""
from __future__ import annotations

import aiohttp


class WinetError(Exception):
    """Errore di comunicazione con il modulo WiNet."""


class WinetClient:
    """Legge e scrive i registri del modulo WiNet in LAN."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        host = host.strip().rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = f"http://{host}"
        self._base = host
        self._session = session

    async def _post(self, path: str, data: dict[str, str]) -> dict:
        try:
            async with self._session.post(
                f"{self._base}{path}",
                data=data,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise WinetError(str(err)) from err

    async def get_registers(self, category: int = 1) -> tuple[dict[int, int], int | None]:
        """Restituisce {registro: valore} e la potenza del segnale Wi-Fi."""
        data = await self._post(
            "/ajax/get-registers", {"key": "020", "category": str(category)}
        )
        try:
            regs = {int(r): int(v) for r, v in data["registers"]}
        except (KeyError, TypeError, ValueError) as err:
            raise WinetError(f"Risposta non valida: {data!r}") from err
        return regs, data.get("rssi")

    async def set_register(self, register: int, value: int) -> None:
        """Scrive un registro; solleva WinetError se il modulo rifiuta."""
        data = await self._post(
            "/ajax/set-register",
            {"key": "002", "memory": "1", "regId": str(register), "value": str(value)},
        )
        if data.get("result") is not True:
            raise WinetError(f"Scrittura rifiutata: {data!r}")
