from collections.abc import Callable, Sequence
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from bilkatogo import MissingItem, OrderDetails, Substitution

from .const import DOMAIN

STORAGE_VERSION = 1


def substitution_data(substitution: Substitution) -> dict[str, Any]:
    return {
        "original_product": substitution.original_product,
        "original_article_number": substitution.original_article_number,
        "replacement_product": substitution.replacement_product,
        "replacement_article_number": substitution.replacement_article_number,
        "quantity": substitution.quantity,
    }


def missing_item_data(item: MissingItem) -> dict[str, Any]:
    return {
        "product": item.product,
        "article_number": item.article_number,
        "ordered_quantity": item.ordered_quantity,
        "missing_quantity": item.missing_quantity,
    }


class Announcer[T]:
    """Announce each item of an Order once, remembering what was announced across restarts.

    Each new item fires the bus event `bilkatogo_<event_type>` and is returned, so the event
    entity of the same event type can fire it too.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        *,
        storage_suffix: str,
        event_type: str,
        key_field: str,
        items: Callable[[OrderDetails], Sequence[T]],
        data: Callable[[T], dict[str, Any]],
    ) -> None:
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.{storage_suffix}"
        )
        self.event_type = event_type
        self._key_field = key_field
        self._items = items
        self._data = data
        self._announced: set[tuple[str, str]] = set()

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self._announced = {
            (item["order_number"], item[self._key_field]) for item in data.get("announced", [])
        }

    async def async_announce(self, details: OrderDetails) -> list[dict[str, Any]]:
        new = [
            item
            for item in self._items(details)
            if (details.order_number, getattr(item, self._key_field)) not in self._announced
        ]
        if not new:
            return []
        for item in new:
            self._announced.add((details.order_number, getattr(item, self._key_field)))
        await self._store.async_save(
            {
                "announced": [
                    {"order_number": order_number, self._key_field: key}
                    for order_number, key in sorted(self._announced)
                ]
            }
        )
        announced = [{"order_number": details.order_number, **self._data(item)} for item in new]
        for data in announced:
            self._hass.bus.async_fire(f"{DOMAIN}_{self.event_type}", data)
        return announced

    async def async_remove(self) -> None:
        await self._store.async_remove()


def announcers(hass: HomeAssistant, entry_id: str) -> tuple[Announcer[Any], ...]:
    return (
        Announcer(
            hass,
            entry_id,
            storage_suffix="substitutions",
            event_type="substitution",
            key_field="original_product",
            items=lambda details: details.substitutions,
            data=substitution_data,
        ),
        Announcer(
            hass,
            entry_id,
            storage_suffix="missing_items",
            event_type="missing_item",
            key_field="article_number",
            items=lambda details: details.missing_items,
            data=missing_item_data,
        ),
    )
