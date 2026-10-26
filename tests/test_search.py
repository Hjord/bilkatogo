import json
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from bilkatogo import (
    BilkaToGoClient,
    BilkaToGoError,
    BilkaUnreachableError,
    Offer,
    Product,
    UnexpectedResponseError,
    UnknownPickupPointError,
)
from tests.fake_bilka import EMAIL, PASSWORD, FakeBilka, algolia_query


@pytest.mark.asyncio
async def test_search_finds_products_at_the_carts_store(bilka: FakeBilka) -> None:
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, httpx_client=http) as client,
    ):
        products = await client.search("skyr")

    [request] = bilka.calls("algolia")
    query = algolia_query(request)
    assert query["indexName"] == "prod_BILKATOGO_PRODUCTS"
    assert query["query"] == "skyr"
    assert query["filters"] == "isInAssortmentIn:1653 AND nonsearchable:false"
    assert "article" not in json.loads(query["attributesToRetrieve"])

    assert [product.article_number for product in products] == ["19753", "128298"]
    plain = products[0]
    assert plain.name == "Skyr m. vanilje 0,2% fedt u. tilsat sukker"
    assert plain.brand == "Cheasy"
    assert plain.store_id == "1653"
    assert plain.price == Decimal("30.95")
    assert plain.unit_price == Decimal("30.95")
    assert plain.unit == "kg"
    assert plain.in_stock is True
    assert plain.offer is None
    assert plain.multibuy_offer is None


async def search(bilka: FakeBilka, text: str, **kwargs: Any) -> list[Product]:
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, httpx_client=http) as client,
    ):
        return await client.search(text, **kwargs)


@pytest.mark.asyncio
async def test_skarp_pris_offer_lowers_the_price(bilka: FakeBilka) -> None:
    [_, product] = await search(bilka, "skyr")

    assert product.article_number == "128298"
    assert product.price == Decimal("39.31")
    assert product.unit_price == Decimal("49.14")
    assert product.offer == Offer(
        label="Skarp pris",
        price=Decimal("25.00"),
        unit_price=Decimal("31.25"),
        ends=None,
        limit_per_customer=None,
    )
    assert product.multibuy_offer is None


@pytest.mark.asyncio
async def test_dated_offer_keeps_the_price_from_before_it(bilka: FakeBilka) -> None:
    [product] = await search(bilka, "kyllingebrystfilet")

    assert product.price == Decimal("64.95")
    assert product.unit_price == Decimal("99.92")
    assert product.offer == Offer(
        label="Spar 4,95",
        price=Decimal("60.00"),
        unit_price=Decimal("92.31"),
        ends=date(2026, 10, 29),
        limit_per_customer=None,
    )


@pytest.mark.asyncio
async def test_multibuy_offer_is_bilkas_text_and_not_an_offer(bilka: FakeBilka) -> None:
    [product] = await search(bilka, "bananer")

    assert product.price == Decimal("2.75")
    assert product.unit_price == Decimal("2.75")
    assert product.unit == "stk"
    assert product.offer is None
    assert product.multibuy_offer == "Mix 10 for 25,00"


@pytest.mark.asyncio
async def test_product_out_of_stock_at_the_store(bilka: FakeBilka) -> None:
    [mozzarella] = await search(bilka, "mozzarella")
    [chicken] = await search(bilka, "kyllingebrystfilet")

    assert mozzarella.in_stock is False
    assert chicken.in_stock is False


@pytest.mark.asyncio
async def test_named_pickup_point_searches_its_store(bilka: FakeBilka) -> None:
    [product] = await search(bilka, "mozzarella", pickup_point="pickup fredericia")

    assert algolia_query(bilka.calls("algolia")[0])["filters"] == (
        "isInAssortmentIn:1662 AND nonsearchable:false"
    )
    assert bilka.calls("cart") == []
    assert product.store_id == "1662"
    assert product.in_stock is True


@pytest.mark.asyncio
async def test_unknown_pickup_point_does_not_search(bilka: FakeBilka) -> None:
    with pytest.raises(UnknownPickupPointError):
        await search(bilka, "skyr", pickup_point="Bilka Atlantis")

    assert bilka.calls("algolia") == []


@pytest.mark.asyncio
async def test_cart_without_a_pickup_point_asks_for_one(bilka: FakeBilka) -> None:
    bilka.cart_contents = {**bilka.cart_contents, "deliveryAddress": None}

    with pytest.raises(BilkaToGoError, match="Pickup Point"):
        await search(bilka, "skyr")

    assert bilka.calls("algolia") == []


@pytest.mark.asyncio
async def test_limit_caps_the_number_of_products(bilka: FakeBilka) -> None:
    products = await search(bilka, "skyr", limit=1)

    assert algolia_query(bilka.calls("algolia")[0])["hitsPerPage"] == "1"
    assert [product.article_number for product in products] == ["19753"]


@pytest.mark.asyncio
async def test_offer_with_a_limit_per_customer(bilka: FakeBilka) -> None:
    store = bilka.products[1]["storeData"]["1653"]
    store["offerMax"] = 3
    store["offerMaxDescription"] = "Max 3 stk. pr. kunde"

    [_, product] = await search(bilka, "skyr")

    assert product.offer is not None
    assert product.offer.limit_per_customer == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("offer_max", "limit"), [("3", 3), ("0", None), ("", None), ("lots", None), (None, None)]
)
async def test_limit_per_customer_is_a_whole_number_or_none(
    bilka: FakeBilka, offer_max: object, limit: int | None
) -> None:
    bilka.products[1]["storeData"]["1653"]["offerMax"] = offer_max

    [_, product] = await search(bilka, "skyr")

    assert product.offer is not None
    assert product.offer.limit_per_customer == limit


@pytest.mark.asyncio
async def test_unreachable_algolia_raises_unreachable(bilka: FakeBilka) -> None:
    bilka.script("algolia", httpx.ConnectError("no route to host"))

    with pytest.raises(BilkaUnreachableError, match="algolia"):
        await search(bilka, "skyr")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(403, json={"message": "Invalid Application-ID or API key"}),
        httpx.Response(200, text="<html>maintenance</html>"),
        httpx.Response(200, json={"message": "no results"}),
    ],
)
async def test_unexpected_algolia_answer_raises_unexpected_response(
    bilka: FakeBilka, answer: httpx.Response
) -> None:
    bilka.script("algolia", answer)

    with pytest.raises(UnexpectedResponseError, match="Product search"):
        await search(bilka, "skyr")
