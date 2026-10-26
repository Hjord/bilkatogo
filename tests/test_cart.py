from decimal import Decimal

import pytest

from bilkatogo import BilkaToGoClient, Cart
from tests.fake_bilka import EMAIL, PASSWORD, FakeBilka, load_fixture


async def fetch(bilka: FakeBilka) -> Cart:
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, httpx_client=http) as client,
    ):
        return await client.get_cart()


@pytest.mark.asyncio
async def test_cart_lines_have_product_article_number_quantity_price_and_line_total(
    logged_in_cart: FakeBilka,
) -> None:
    cart = await fetch(logged_in_cart)

    [request] = logged_in_cart.calls("cart")
    assert dict(request.url.params) == {"u": "w", "extra": "deliveryAddress,deliveryDate"}
    assert [
        (line.product, line.article_number, line.quantity, line.price, line.line_total)
        for line in cart.lines
    ] == [
        ("Bananer", "18381", 10, Decimal("2.75"), Decimal("25.00")),
        ("Agurk", "18364", 1, Decimal("7.00"), Decimal("7.00")),
        ("Yoghurt m. pære og banan 1,4% fedt", "19789", 1, Decimal("17.00"), Decimal("17.00")),
        (
            "Flydende smør og rapsolie til madlavning",
            "185370",
            1,
            Decimal("12.00"),
            Decimal("10.00"),
        ),
        ("Mini Mix", "75191", 1, Decimal("29.00"), Decimal("29.00")),
    ]


@pytest.mark.asyncio
async def test_cart_total_and_breakdown_in_kroner(logged_in_cart: FakeBilka) -> None:
    cart = await fetch(logged_in_cart)

    assert "Papirpose" not in [line.product for line in cart.lines]
    assert "Pakkeservice" not in [line.product for line in cart.lines]
    assert str(cart.total) == "127.00"
    assert str(cart.service_fee) == "39.00"
    assert str(cart.packaging) == "0.00"
    assert str(cart.deposit) == "0.00"
    assert str(cart.discount) == "9.50"


@pytest.mark.asyncio
async def test_cart_discount_adds_offers_membership_personal_offers_and_vouchers(
    logged_in_cart: FakeBilka,
) -> None:
    logged_in_cart.cart_contents["stat"].update(
        {
            "promo": 1000,
            "membership_offer_discount": 250,
            "personalized_offer_discount": 125,
            "vouchers": [{"amount": 5000}],
            "deposit": 150,
            "packaging_price": 400,
        }
    )

    cart = await fetch(logged_in_cart)

    assert str(cart.discount) == "63.75"
    assert str(cart.deposit) == "1.50"
    assert str(cart.packaging) == "4.00"


@pytest.mark.asyncio
async def test_cart_has_the_chosen_pickup_point(logged_in_cart: FakeBilka) -> None:
    cart = await fetch(logged_in_cart)

    assert cart.pickup_point is not None
    assert cart.pickup_point.name == "Bilka Vejle"
    assert cart.pickup_point.store_id == "1661"


@pytest.mark.asyncio
async def test_cart_without_a_pickup_point_has_none(logged_in_cart: FakeBilka) -> None:
    logged_in_cart.cart_contents["deliveryAddress"] = None

    cart = await fetch(logged_in_cart)

    assert cart.pickup_point is None


@pytest.mark.asyncio
async def test_empty_cart_has_no_cart_lines(bilka: FakeBilka) -> None:
    bilka.cart_contents = load_fixture("cart.json")

    cart = await fetch(bilka)

    assert cart.lines == []
    assert cart.total == Decimal("0.00")
    assert cart.service_fee == Decimal("0.00")
