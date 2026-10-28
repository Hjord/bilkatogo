from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import create_async_httpx_client
from homeassistant.helpers.typing import ConfigType

from bilkatogo import BilkaToGoClient

from .announcer import announcers
from .const import DOMAIN, PLATFORMS
from .coordinator import BilkaToGoConfigEntry, BilkaToGoCoordinator
from .services import async_setup_services
from .token_storage import HomeAssistantTokenStorage

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BilkaToGoConfigEntry) -> bool:
    client = BilkaToGoClient(
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        token_storage=HomeAssistantTokenStorage(hass, entry.entry_id),
        httpx_client=create_async_httpx_client(hass),
    )
    coordinator = BilkaToGoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BilkaToGoConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: BilkaToGoConfigEntry) -> None:
    await HomeAssistantTokenStorage(hass, entry.entry_id).async_remove()
    for announcer in announcers(hass, entry.entry_id):
        await announcer.async_remove()
