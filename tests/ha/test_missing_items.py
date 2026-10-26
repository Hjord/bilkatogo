from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.bilkatogo.const import DOMAIN
from tests.fake_bilka import FakeBilka
from tests.ha.conftest import SetupIntegration

ORDER_NUMBER = "900000000003"

MISSING_ITEMS = [
    {"product": "Skyr", "article_number": "932058", "ordered_quantity": 4, "missing_quantity": 2},
    {
        "product": "Havregryn",
        "article_number": "1006",
        "ordered_quantity": 1,
        "missing_quantity": 1,
    },
]


def missing_items(hass: HomeAssistant, entry: MockConfigEntry) -> State:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_missing_items"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state


def set_status(bilka: FakeBilka, status_code: str) -> None:
    bilka.orders = [{**bilka.orders[0], "orderId": ORDER_NUMBER, "status": status_code}]
    details = bilka.details[ORDER_NUMBER]
    bilka.details[ORDER_NUMBER] = {"order": {**details["order"], "status": status_code}}


async def next_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(timedelta(minutes=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_missing_items_are_shown_once_the_order_is_packed(
    hass: HomeAssistant, setup_integration: SetupIntegration, bilka: FakeBilka
) -> None:
    set_status(bilka, "Pakket")

    entry = await setup_integration()

    state = missing_items(hass, entry)
    assert state.state == "2"
    assert state.attributes["missing_items"] == MISSING_ITEMS


async def test_each_missing_item_is_announced_once_from_received_to_picked_up(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    bilka: FakeBilka,
    freezer: FrozenDateTimeFactory,
) -> None:
    events = async_capture_events(hass, "bilkatogo_missing_item")
    set_status(bilka, "Bestilt")
    entry = await setup_integration()
    assert events == []

    set_status(bilka, "Pakket")
    await next_update(hass, freezer)
    assert [event.data for event in events] == [
        {
            "order_number": ORDER_NUMBER,
            "product": "Skyr",
            "article_number": "932058",
            "ordered_quantity": 4,
            "missing_quantity": 2,
        },
        {
            "order_number": ORDER_NUMBER,
            "product": "Havregryn",
            "article_number": "1006",
            "ordered_quantity": 1,
            "missing_quantity": 1,
        },
    ]

    await next_update(hass, freezer)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert missing_items(hass, entry).state == "2"

    set_status(bilka, "Faktureret")
    await next_update(hass, freezer)
    assert missing_items(hass, entry).state == "2"
    assert len(events) == 2


async def test_announced_missing_items_survive_a_restart(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    bilka: FakeBilka,
    hass_storage: dict[str, Any],
    config_entry: MockConfigEntry,
) -> None:
    hass_storage[f"bilkatogo.{config_entry.entry_id}.missing_items"] = {
        "version": 1,
        "key": f"bilkatogo.{config_entry.entry_id}.missing_items",
        "data": {"announced": [{"order_number": ORDER_NUMBER, "article_number": "932058"}]},
    }
    events = async_capture_events(hass, "bilkatogo_missing_item")
    set_status(bilka, "Pakket")

    await setup_integration()

    assert [event.data["product"] for event in events] == ["Havregryn"]


async def test_removing_the_entry_forgets_announced_missing_items(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    bilka: FakeBilka,
    hass_storage: dict[str, Any],
) -> None:
    set_status(bilka, "Pakket")
    entry = await setup_integration()
    assert f"bilkatogo.{entry.entry_id}.missing_items" in hass_storage

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert f"bilkatogo.{entry.entry_id}.missing_items" not in hass_storage
