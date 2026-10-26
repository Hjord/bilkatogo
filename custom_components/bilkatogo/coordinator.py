from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from bilkatogo import (
    BilkaToGoClient,
    BilkaToGoError,
    InvalidCredentialsError,
    Order,
    current_order,
)
from bilkatogo.const import CURRENT_ORDER_SCAN_LIMIT

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL

type BilkaToGoConfigEntry = ConfigEntry[BilkaToGoCoordinator]


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
        return BilkaToGoData(order=current_order(orders))
