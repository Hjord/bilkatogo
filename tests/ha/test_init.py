from typing import Any

import httpx
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.bilkatogo.const import DOMAIN
from tests.fake_bilka import EMAIL, FakeBilka
from tests.ha.conftest import SetupIntegration


def stored_session(hass_storage: dict[str, Any], entry_id: str) -> dict[str, Any]:
    return hass_storage[f"bilkatogo.{entry_id}.session"]["data"]


async def test_session_is_kept_in_home_assistant_storage(
    hass: HomeAssistant, setup_integration: SetupIntegration, hass_storage: dict[str, Any]
) -> None:
    entry = await setup_integration()

    session = stored_session(hass_storage, entry.entry_id)
    assert session["email"] == EMAIL
    assert session["jwt"] == "eyFake.jwt.token"


async def test_reload_reuses_the_stored_session(
    hass: HomeAssistant, setup_integration: SetupIntegration, bilka: FakeBilka
) -> None:
    entry = await setup_integration()

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert len(bilka.calls("gigya_login")) == 1
    assert len(bilka.calls("order_history")) == 2


async def test_setup_retries_when_bilka_is_unreachable(
    hass: HomeAssistant, setup_integration: SetupIntegration, bilka: FakeBilka
) -> None:
    bilka.script("gigya_login", httpx.ConnectError("down"))

    entry = await setup_integration()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_links_to_the_bilkatogo_website(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    entry = await setup_integration()

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})

    assert device is not None
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.configuration_url == "https://www.bilkatogo.dk"


async def test_unload_and_remove_entry(
    hass: HomeAssistant, setup_integration: SetupIntegration, hass_storage: dict[str, Any]
) -> None:
    entry = await setup_integration()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert f"bilkatogo.{entry.entry_id}.session" not in hass_storage
