from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.bilkatogo.const import DOMAIN
from tests.fake_bilka import FakeBilka
from tests.ha.conftest import SetupIntegration

ORDER_NUMBER = "900000000001"

SUBSTITUTIONS = [
    {"original_product": "Æbler", "replacement_product": "Pærer", "quantity": 4},
    {"original_product": "Letmælk", "replacement_product": "Minimælk", "quantity": 2},
]


def substitutions(hass: HomeAssistant, entry: MockConfigEntry) -> State:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_substitutions"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state


def set_status(bilka: FakeBilka, status_code: str) -> None:
    order = next(o for o in bilka.orders if o["orderId"] == ORDER_NUMBER)
    bilka.orders = [{**order, "status": status_code}]
    details = bilka.details[ORDER_NUMBER]
    bilka.details[ORDER_NUMBER] = {"order": {**details["order"], "status": status_code}}


async def next_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(timedelta(minutes=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_substitutions_are_shown_once_the_order_is_packed(
    hass: HomeAssistant, setup_integration: SetupIntegration, bilka: FakeBilka
) -> None:
    set_status(bilka, "Pakket")

    entry = await setup_integration()

    state = substitutions(hass, entry)
    assert state.state == "2"
    assert state.attributes["substitutions"] == SUBSTITUTIONS


async def test_details_are_fetched_only_while_packed_and_kept_after_pickup(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    bilka: FakeBilka,
    freezer: FrozenDateTimeFactory,
) -> None:
    set_status(bilka, "Ubehandlet")
    entry = await setup_integration()
    set_status(bilka, "Bestilt")
    await next_update(hass, freezer)
    assert substitutions(hass, entry).state == STATE_UNKNOWN
    assert bilka.calls("order_details") == []

    set_status(bilka, "Pakket")
    await next_update(hass, freezer)
    assert substitutions(hass, entry).state == "2"
    assert len(bilka.calls("order_details")) == 1

    set_status(bilka, "Faktureret")
    await next_update(hass, freezer)
    await next_update(hass, freezer)
    state = substitutions(hass, entry)
    assert state.state == "2"
    assert state.attributes["substitutions"] == SUBSTITUTIONS
    assert len(bilka.calls("order_details")) == 1


async def test_a_new_current_order_drops_the_previous_substitutions(
    hass: HomeAssistant,
    setup_integration: SetupIntegration,
    bilka: FakeBilka,
    freezer: FrozenDateTimeFactory,
) -> None:
    set_status(bilka, "Pakket")
    entry = await setup_integration()

    bilka.orders = [{**bilka.orders[0], "orderId": "900000000003", "status": "Bestilt"}]
    await next_update(hass, freezer)

    state = substitutions(hass, entry)
    assert state.state == STATE_UNKNOWN
    assert "substitutions" not in state.attributes
