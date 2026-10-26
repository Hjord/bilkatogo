from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from bilkatogo import (
    BilkaToGoClient,
    BilkaToGoError,
    Order,
    OrderDetails,
    OrderStatus,
    current_order,
)
from bilkatogo.const import CURRENT_ORDER_SCAN_LIMIT

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL

type BilkaToGoConfigEntry = ConfigEntry[BilkaToGoCoordinator]

DETAILS_STATUSES = frozenset({OrderStatus.PACKED})


@dataclass
class BilkaToGoData:
    order: Order | None
    details: OrderDetails | None = None


class BilkaToGoCoordinator(DataUpdateCoordinator[BilkaToGoData]):
    """Fetches the Order list once per update and keeps the Current Order."""

    config_entry: BilkaToGoConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: BilkaToGoConfigEntry, client: BilkaToGoClient
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> BilkaToGoData:
        try:
            orders = await self.client.get_orders(limit=CURRENT_ORDER_SCAN_LIMIT)
            order = current_order(orders)
            details = None
            if order and order.status in DETAILS_STATUSES:
                details = await self.client.get_order(order.order_number)
        except BilkaToGoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return BilkaToGoData(order=order, details=details)
