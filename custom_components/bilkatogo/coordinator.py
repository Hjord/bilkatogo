from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from bilkatogo import (
    CURRENT_ORDER_SCAN_LIMIT,
    FINISHED_STATUSES,
    BilkaToGoClient,
    BilkaToGoError,
    InvalidCredentialsError,
    Order,
    OrderDetails,
    OrderStatus,
    current_order,
)

from .const import DOMAIN, FAST_UPDATE_INTERVAL, FAST_UPDATE_LEAD_TIME, LOGGER, UPDATE_INTERVAL
from .substitutions import SubstitutionAnnouncer

DETAILS_STATUSES = frozenset(
    {OrderStatus.PACKED, OrderStatus.NOT_COLLECTED, OrderStatus.CANCELLED, OrderStatus.SOLD_OUT}
)

type BilkaToGoConfigEntry = ConfigEntry[BilkaToGoCoordinator]


def polling_interval(order: Order | None, now: datetime) -> timedelta:
    if order is None or order.pickup_slot is None or order.status in FINISHED_STATUSES:
        return UPDATE_INTERVAL
    until_fast = order.pickup_slot.starts_at - FAST_UPDATE_LEAD_TIME - now
    if until_fast <= timedelta(0):
        return FAST_UPDATE_INTERVAL
    return min(UPDATE_INTERVAL, until_fast)


@dataclass
class BilkaToGoData:
    order: Order | None
    details: OrderDetails | None = None


class BilkaToGoCoordinator(DataUpdateCoordinator[BilkaToGoData]):
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
        """Fetch Order Details once the Current Order is Packed or later.

        Before Packed there is nothing to show yet. A Picked Up Order no longer changes, so
        its details are fetched only if none are kept for it yet (after a restart, or when
        Packed fell between two polls) and then kept.
        """
        if order is None:
            return None
        previous = self.data.details if self.data else None
        if order.status is OrderStatus.PICKED_UP:
            if previous and previous.order_number == order.order_number:
                return previous
            return await self.client.get_order(order.order_number)
        if order.status in DETAILS_STATUSES:
            return await self.client.get_order(order.order_number)
        return None
