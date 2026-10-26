from decimal import Decimal

import pytest

from bilkatogo import BilkaToGoClient, OrderDetails
from tests.fake_bilka import EMAIL, PASSWORD, FakeBilka

CAPTURED = "900000000004"


async def fetch(bilka: FakeBilka, order_number: str) -> OrderDetails:
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, httpx_client=http) as client,
    ):
        return await client.get_order(order_number)


@pytest.mark.asyncio
async def test_captured_order_total_and_breakdown_in_kroner(bilka: FakeBilka) -> None:
    details = await fetch(bilka, CAPTURED)

    assert str(details.order_total) == "793.80"
    assert str(details.service_fee) == "39.00"
    assert str(details.deposit) == "1.50"
    assert details.packaging == Decimal("0.00")
    assert details.delivery_fee == Decimal("0.00")
    assert details.discount == Decimal("0.00")


@pytest.mark.asyncio
async def test_discount_adds_offers_membership_personal_offers_and_vouchers(
    bilka: FakeBilka,
) -> None:
    bilka.details[CAPTURED]["order"]["stat"].update(
        {
            "promo": 1000,
            "membership_offer_discount": 250,
            "personalized_offer_discount": 125,
            "vouchers": [{"amount": 5000}, {"amount": 2000}],
            "packaging_price": 400,
            "delivery_price": 4900,
        }
    )

    details = await fetch(bilka, CAPTURED)

    assert str(details.discount) == "83.75"
    assert str(details.packaging) == "4.00"
    assert str(details.delivery_fee) == "49.00"


@pytest.mark.asyncio
async def test_order_without_a_stat_has_a_zero_breakdown(bilka: FakeBilka) -> None:
    del bilka.details[CAPTURED]["order"]["stat"]

    details = await fetch(bilka, CAPTURED)

    assert str(details.order_total) == "793.80"
    assert (details.deposit, details.service_fee, details.discount) == (0, 0, 0)


@pytest.mark.asyncio
async def test_ordered_total_comes_from_the_order_history(bilka: FakeBilka) -> None:
    details = await fetch(bilka, "900000000001")

    assert str(details.ordered_total) == "512.00"
    assert str(details.order_total) == "509.00"


@pytest.mark.asyncio
async def test_ordered_total_is_unknown_for_an_order_outside_the_history(
    bilka: FakeBilka,
) -> None:
    details = await fetch(bilka, CAPTURED)

    assert details.ordered_total is None


@pytest.mark.asyncio
async def test_current_order_carries_its_ordered_total(bilka: FakeBilka) -> None:
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, httpx_client=http) as client,
    ):
        details = await client.get_current_order()

    assert details is not None
    assert str(details.ordered_total) == "456.00"
    assert len(bilka.calls("order_history")) == 1


@pytest.mark.asyncio
async def test_get_order_with_a_known_order_skips_the_history(bilka: FakeBilka) -> None:
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, httpx_client=http) as client,
    ):
        [_, collected] = await client.get_orders()
        history_calls = len(bilka.calls("order_history"))
        details = await client.get_order(collected)

    assert str(details.ordered_total) == "512.00"
    assert len(bilka.calls("order_history")) == history_calls
