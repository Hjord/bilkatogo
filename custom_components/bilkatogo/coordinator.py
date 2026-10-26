from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from bilkatogo import (
    BilkaToGoClient,
    BilkaToGoError,
    InvalidCredentialsError,
    Order,
    OrderDetails,
    OrderStatus,
    current_order,
)
from bilkatogo.const import CURRENT_ORDER_SCAN_LIMIT
from bilkatogo.models.order import FINISHED_STATUSES

from .const import DOMAIN, FAST_UPDATE_INTERVAL, FAST_UPDATE_LEAD_TIME, LOGGER, UPDATE_INTERVAL
from .substitutions import SubstitutionAnnouncer

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
        self.announcer = SubstitutionAnnouncer(hass, entry.entry_id)

    async def _async_setup(self) -> None:
        await self.announcer.async_load()

    async def _async_update_data(self) -> BilkaToGoData:
        try:
            order = current_order(await self.client.get_orders(limit=CURRENT_ORDER_SCAN_LIMIT))
            details = await self._async_fetch_details(order)
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except BilkaToGoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.update_interval = polling_interval(order, dt_util.utcnow())
        if details:
            await self.announcer.async_announce(details)
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
