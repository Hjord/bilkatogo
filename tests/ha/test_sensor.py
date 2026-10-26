from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from bilkatogo import OrderStatus
from custom_components.bilkatogo.const import DOMAIN
from tests.fake_bilka import FakeBilka
from tests.ha.conftest import SetupIntegration


def order_status(hass: HomeAssistant, entry: MockConfigEntry) -> State:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_order_status"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def test_order_status_shows_the_current_order(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    entry = await setup_integration()

    state = order_status(hass, entry)
    assert state.state == "received"
    assert state.attributes["status_code"] == "Bestilt"
    assert state.attributes["options"] == [
        "processing",
        "received",
        "packed",
        "picked_up",
        "not_collected",
        "cancelled",
        "sold_out",
        "unknown",
    ]


async def test_order_status_follows_bilka_every_60_minutes(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    bilka: FakeBilka,
    freezer: FrozenDateTimeFactory,
) -> None:
    entry = await setup_integration()
    bilka.orders[0] = {**bilka.orders[0], "status": "Pakket"}

    freezer.tick(timedelta(minutes=59))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert order_status(hass, entry).state == "received"

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = order_status(hass, entry)
    assert state.state == "packed"
    assert state.attributes["status_code"] == "Pakket"


async def test_unknown_bilka_status_code_is_kept_as_attribute(
    hass: HomeAssistant, setup_integration: SetupIntegration, bilka: FakeBilka
) -> None:
    bilka.orders[0] = {**bilka.orders[0], "status": "Noget nyt"}

    entry = await setup_integration()

    state = order_status(hass, entry)
    assert state.state == STATE_UNKNOWN
    assert state.attributes["status_code"] == "Noget nyt"


async def test_order_status_is_unknown_without_orders(
    hass: HomeAssistant, setup_integration: SetupIntegration, bilka: FakeBilka
) -> None:
    bilka.orders = []

    entry = await setup_integration()

    state = order_status(hass, entry)
    assert state.state == STATE_UNKNOWN
    assert "status_code" not in state.attributes


async def test_order_status_states_are_translated_in_danish_and_english(
    hass: HomeAssistant, setup_integration: SetupIntegration
) -> None:
    await setup_integration()
    prefix = f"component.{DOMAIN}.entity.sensor.order_status.state."

    da = await async_get_translations(hass, "da", "entity", [DOMAIN])
    en = await async_get_translations(hass, "en", "entity", [DOMAIN])

    assert da[f"{prefix}packed"] == "Pakket"
    assert da[f"{prefix}received"] == "Modtaget"
    assert en[f"{prefix}picked_up"] == "Picked up"
    for translations in (da, en):
        assert {key.removeprefix(prefix) for key in translations if key.startswith(prefix)} == {
            status.value for status in OrderStatus
        }
