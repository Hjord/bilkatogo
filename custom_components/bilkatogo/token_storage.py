from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from bilkatogo import TokenStorage

from .const import DOMAIN

STORAGE_VERSION = 1


class HomeAssistantTokenStorage(TokenStorage):
    """Keeps the Bilka session of one config entry in Home Assistant's storage."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.session", private=True
        )

    async def load(self) -> dict[str, Any] | None:
        return await self._store.async_load()

    async def save(self, data: dict[str, Any]) -> None:
        await self._store.async_save(data)

    async def async_remove(self) -> None:
        await self._store.async_remove()
