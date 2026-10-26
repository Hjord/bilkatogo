from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from bilkatogo import MissingItem, OrderDetails

from .const import DOMAIN, EVENT_MISSING_ITEM

STORAGE_VERSION = 1


def missing_item_data(item: MissingItem) -> dict[str, Any]:
    return {
        "product": item.product,
        "article_number": item.article_number,
        "ordered_quantity": item.ordered_quantity,
        "missing_quantity": item.missing_quantity,
    }


class MissingItemAnnouncer:
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.missing_items"
        )
        self._announced: set[tuple[str, str]] = set()

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self._announced = {
            (item["order_number"], item["article_number"]) for item in data.get("announced", [])
        }

    async def async_announce(self, details: OrderDetails) -> None:
        new = [
            item
            for item in details.missing_items
            if (details.order_number, item.article_number) not in self._announced
        ]
        if not new:
            return
        for item in new:
            self._announced.add((details.order_number, item.article_number))
        await self._store.async_save(
            {
                "announced": [
                    {"order_number": order_number, "article_number": article_number}
                    for order_number, article_number in sorted(self._announced)
                ]
            }
        )
        for item in new:
            self._hass.bus.async_fire(
                EVENT_MISSING_ITEM,
                {"order_number": details.order_number, **missing_item_data(item)},
            )

    async def async_remove(self) -> None:
        await self._store.async_remove()
