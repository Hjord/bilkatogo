from datetime import date, datetime, time

import pytest

from bilkatogo import BilkaToGoClient, Order, OrderStatus
from tests.conftest import MemoryTokenStorage
from tests.fake_bilka import EMAIL, PASSWORD, FakeBilka, load_fixture


async def fetch_one(bilka: FakeBilka, order: dict) -> Order:
    bilka.orders = [order]
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, httpx_client=http) as client,
    ):
        [fetched] = await client.get_orders()
    return fetched


def synthetic_order(**overrides) -> dict:
    return {**load_fixture("order_history.json")["orders"][0], **overrides}


@pytest.mark.asyncio
async def test_get_orders_logs_in_and_returns_typed_orders(
    bilka: FakeBilka, storage: MemoryTokenStorage
) -> None:
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, token_storage=storage, httpx_client=http) as client,
    ):
        orders = await client.get_orders()

    [request] = bilka.calls("order_history")
    assert request.content == b""
    assert dict(request.url.params) == {
        "u": "w",
        "limit": "5",
        "offset": "0",
        "muah": "1",
        "ordertype": "dibs,pgw",
    }

    upcoming, collected = orders
    assert upcoming.order_number == "900000000002"
    assert upcoming.status is OrderStatus.RECEIVED
    assert upcoming.status_code == "Bestilt"
    assert upcoming.ordered_at == datetime(2026, 11, 1, 20, 15)
    assert upcoming.pickup_slot is not None
    assert upcoming.pickup_slot.date == date(2026, 11, 3)
    assert upcoming.pickup_slot.start == time(16, 0)
    assert upcoming.pickup_slot.end == time(18, 0)
    assert upcoming.pickup_point is not None
    assert upcoming.pickup_point.name == "Bilka Eksempelby"
    assert upcoming.pickup_point.address == "Testvej 1"
    assert upcoming.pickup_point.zip_code == "9999"
    assert upcoming.pickup_point.city == "Eksempelby"
    assert upcoming.home_delivery is False
    assert upcoming.ordered_price == 45600
    assert upcoming.packed_price == 0
    assert upcoming.content == "Æbler, Havregryn, Letmælk"

    assert collected.order_number == "900000000001"
    assert collected.status is OrderStatus.PICKED_UP
    assert collected.delivered is True
    assert collected.packed_price == 50900


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("Ubehandlet", OrderStatus.PROCESSING),
        ("Capture igang", OrderStatus.PROCESSING),
        ("Bestilt", OrderStatus.RECEIVED),
        ("Pakket", OrderStatus.PACKED),
        ("Leveret", OrderStatus.PICKED_UP),
        ("Faktureret", OrderStatus.PICKED_UP),
        ("Uafhentet", OrderStatus.NOT_COLLECTED),
        ("Annulleret", OrderStatus.CANCELLED),
        ("Fuldt udsolgt", OrderStatus.SOLD_OUT),
        ("  capture IGANG ", OrderStatus.PROCESSING),
        ("FULDT_UDSOLGT", OrderStatus.SOLD_OUT),
        ("Ny ukendt status", OrderStatus.UNKNOWN),
        ("", OrderStatus.UNKNOWN),
    ],
)
async def test_bilka_status_code_maps_to_order_status_and_is_kept(
    bilka: FakeBilka, code: str, status: OrderStatus
) -> None:
    order = await fetch_one(bilka, synthetic_order(status=code))

    assert order.status is status
    assert order.status_code == code


@pytest.mark.asyncio
async def test_unknown_keys_are_tolerated_and_kept_in_raw(bilka: FakeBilka) -> None:
    raw = synthetic_order(organisation={"id": 1}, deliveryMessage="Ring på")

    order = await fetch_one(bilka, raw)

    assert order._raw == raw
    assert "organisation" not in dict(order)


@pytest.mark.asyncio
async def test_home_delivery_flag_is_on_the_order(bilka: FakeBilka) -> None:
    raw = synthetic_order()
    raw["pickupzone"] = {**raw["pickupzone"], "home_delivery": True}

    order = await fetch_one(bilka, raw)

    assert order.home_delivery is True


@pytest.mark.asyncio
async def test_order_with_missing_optional_fields_still_parses(bilka: FakeBilka) -> None:
    order = await fetch_one(bilka, {"orderId": "900000000003", "status": "Pakket"})

    assert order.order_number == "900000000003"
    assert order.status is OrderStatus.PACKED
    assert order.pickup_slot is None
    assert order.pickup_point is None
    assert order.ordered_at is None
    assert order.home_delivery is False
    assert order.ordered_price == 0
