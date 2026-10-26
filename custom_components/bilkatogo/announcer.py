from collections.abc import Callable, Sequence
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from bilkatogo import MissingItem, OrderDetails, Substitution

from .const import DOMAIN, EVENT_MISSING_ITEM, EVENT_SUBSTITUTION

STORAGE_VERSION = 1


def substitution_data(substitution: Substitution) -> dict[str, Any]:
    return {
        "original_product": substitution.original_product,
        "replacement_product": substitution.replacement_product,
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
    """Fire an event once per item of an Order, remembering what was announced across restarts."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        *,
        storage_suffix: str,
        event: str,
        key_field: str,
        items: Callable[[OrderDetails], Sequence[T]],
        data: Callable[[T], dict[str, Any]],
    ) -> None:
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.{storage_suffix}"
        )
        self._event = event
        self._key_field = key_field
        self._items = items
        self._data = data
        self._announced: set[tuple[str, str]] = set()

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self._announced = {
            (item["order_number"], item[self._key_field]) for item in data.get("announced", [])
        }

    async def async_announce(self, details: OrderDetails) -> None:
        new = [
            item
            for item in self._items(details)
            if (details.order_number, getattr(item, self._key_field)) not in self._announced
        ]
        if not new:
            return
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
        for item in new:
            self._hass.bus.async_fire(
                self._event, {"order_number": details.order_number, **self._data(item)}
            )

    async def async_remove(self) -> None:
        await self._store.async_remove()


def announcers(hass: HomeAssistant, entry_id: str) -> tuple[Announcer[Any], ...]:
    return (
        Announcer(
            hass,
            entry_id,
            storage_suffix="substitutions",
            event=EVENT_SUBSTITUTION,
            key_field="original_product",
            items=lambda details: details.substitutions,
            data=substitution_data,
        ),
        Announcer(
            hass,
            entry_id,
            storage_suffix="missing_items",
            event=EVENT_MISSING_ITEM,
            key_field="article_number",
            items=lambda details: details.missing_items,
            data=missing_item_data,
        ),
    )
