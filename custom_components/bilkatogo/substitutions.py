from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from bilkatogo import OrderDetails

from .const import DOMAIN, EVENT_SUBSTITUTION

STORAGE_VERSION = 1


class SubstitutionAnnouncer:
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.substitutions"
        )
        self._announced: set[tuple[str, str]] = set()

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self._announced = {
            (item["order_number"], item["original_product"]) for item in data.get("announced", [])
        }

    async def async_announce(self, details: OrderDetails) -> None:
        new = [
            substitution
            for substitution in details.substitutions
            if (details.order_number, substitution.original_product) not in self._announced
        ]
        if not new:
            return
        for substitution in new:
            self._announced.add((details.order_number, substitution.original_product))
        await self._store.async_save(
            {
                "announced": [
                    {"order_number": order_number, "original_product": original_product}
                    for order_number, original_product in sorted(self._announced)
                ]
            }
        )
        for substitution in new:
            self._hass.bus.async_fire(
                EVENT_SUBSTITUTION,
                {
                    "order_number": details.order_number,
                    "original_product": substitution.original_product,
                    "replacement_product": substitution.replacement_product,
                    "quantity": substitution.quantity,
                },
            )

    async def async_remove(self) -> None:
        await self._store.async_remove()
