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
            order = current_order(await self.client.get_orders(limit=CURRENT_ORDER_SCAN_LIMIT))
            details = await self._async_fetch_details(order)
        except BilkaToGoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return BilkaToGoData(order=order, details=details)

    async def _async_fetch_details(self, order: Order | None) -> OrderDetails | None:
        """Fetch Order Details while the Current Order is Packed.

        Earlier there is nothing to show yet, and once it is Picked Up nothing changes,
        so the details last fetched for the same Order are kept instead.
        """
        if order is None:
            return None
        if order.status is OrderStatus.PACKED:
            return await self.client.get_order(order.order_number)
        previous = self.data.details if self.data else None
        if previous and previous.order_number == order.order_number:
            return previous
        return None
