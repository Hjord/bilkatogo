from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from bilkatogo import BilkaToGoClient, BilkaToGoError, Order, current_order
from bilkatogo.const import CURRENT_ORDER_SCAN_LIMIT
from bilkatogo.models.order import FINISHED_STATUSES

from .const import DOMAIN, FAST_UPDATE_INTERVAL, FAST_UPDATE_LEAD_TIME, LOGGER, UPDATE_INTERVAL

BILKA_TIME_ZONE = ZoneInfo("Europe/Copenhagen")

type BilkaToGoConfigEntry = ConfigEntry[BilkaToGoCoordinator]


def polling_interval(order: Order | None, now: datetime) -> timedelta:
    if order is None or order.pickup_slot is None or order.status in FINISHED_STATUSES:
        return UPDATE_INTERVAL
    slot = order.pickup_slot
    slot_start = datetime.combine(slot.date, slot.start, BILKA_TIME_ZONE)
    until_fast = slot_start - FAST_UPDATE_LEAD_TIME - now
    if until_fast <= timedelta(0):
        return FAST_UPDATE_INTERVAL
    return min(UPDATE_INTERVAL, until_fast)


@dataclass
class BilkaToGoData:
    order: Order | None


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
        except BilkaToGoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        order = current_order(orders)
        self.update_interval = polling_interval(order, dt_util.utcnow())
        return BilkaToGoData(order=order)
