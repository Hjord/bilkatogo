import logging
from datetime import date, time

import pytest

from bilkatogo import BilkaToGoClient, BilkaToGoError, OrderDetails, OrderStatus
from tests.fake_bilka import EMAIL, PASSWORD, FakeBilka


async def fetch(bilka: FakeBilka, order_number: str) -> OrderDetails:
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, httpx_client=http) as client,
    ):
        return await client.get_order(order_number)


@pytest.mark.asyncio
async def test_get_order_fetches_one_order_with_pickup_code(bilka: FakeBilka) -> None:
    details = await fetch(bilka, "900000000001")

    [request] = bilka.calls("order_details")
    assert request.method == "GET"
    assert dict(request.url.params) == {"u": "w", "orderId": "900000000001"}

    assert details.order_number == "900000000001"
    assert details.status is OrderStatus.PICKED_UP
    assert details.status_code == "Faktureret"
    assert details.pickup_slot is not None
    assert details.pickup_slot.date == date(2026, 10, 27)
    assert details.pickup_slot.start == time(12, 0)
    assert details.pickup_slot.end == time(14, 0)
    assert details.pickup_point is not None
    assert details.pickup_point.name == "Bilka Eksempelby"
    assert details.home_delivery is False
    assert details.pickup_code is not None
    assert details.pickup_code.code == "12345678"
    assert details.price == 50900


@pytest.mark.asyncio
async def test_order_lines_are_flattened_across_categories(bilka: FakeBilka) -> None:
    details = await fetch(bilka, "900000000001")

    assert [(line.category, line.name, line.quantity, line.amount) for line in details.lines] == [
        ("Frugt & grønt", "Æbler", 4, 1200),
        ("Frugt & grønt", "Rugbrød", 1, 2500),
        ("Mejeri", "Letmælk", 2, 1100),
    ]
    assert details.lines[1].product_id == 1003
    assert details.lines[1].substituted is False
    assert (
        details.lines[1]._raw
        == bilka.details["900000000001"]["order"]["lines"][0]["lines"][0]["orderlines"][1]
    )


@pytest.mark.asyncio
async def test_substitutions_pair_original_and_replacement_product(bilka: FakeBilka) -> None:
    details = await fetch(bilka, "900000000001")

    assert [
        (s.original_product, s.replacement_product, s.quantity, s.replacement_quantity)
        for s in details.substitutions
    ] == [("Æbler", "Pærer", 4, 4), ("Letmælk", "Minimælk", 2, 2)]
    assert details.lines[0].substituted is True
    assert details.substitutions[0]._raw == details.lines[0]._raw


@pytest.mark.asyncio
async def test_order_without_substitutions_has_none(bilka: FakeBilka) -> None:
    details = await fetch(bilka, "900000000002")

    assert details.substitutions == []
    assert [line.name for line in details.lines] == ["Æbler", "Havregryn"]
    assert not any(line.substituted for line in details.lines)


def orderlines(bilka: FakeBilka, order_number: str) -> list[dict]:
    return [
        line
        for group in bilka.details[order_number]["order"]["lines"]
        for block in group["lines"]
        for line in block["orderlines"]
    ]


@pytest.mark.asyncio
async def test_unavailable_line_that_is_not_a_substitution_is_logged(
    bilka: FakeBilka, caplog: pytest.LogCaptureFixture
) -> None:
    orderlines(bilka, "900000000002")[1]["unavailable_reason"] = "Udsolgt"

    with caplog.at_level(logging.WARNING, logger="bilkatogo"):
        details = await fetch(bilka, "900000000002")

    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert "Havregryn" in record.getMessage()
    assert "900000000002" in record.getMessage()
    assert details.lines[1].unavailable_reason == "Udsolgt"
    assert details.substitutions == []


@pytest.mark.asyncio
async def test_unavailable_reason_on_a_substitution_is_not_logged(
    bilka: FakeBilka, caplog: pytest.LogCaptureFixture
) -> None:
    orderlines(bilka, "900000000001")[0]["unavailable_reason"] = "Udsolgt"

    with caplog.at_level(logging.WARNING, logger="bilkatogo"):
        details = await fetch(bilka, "900000000001")

    assert caplog.records == []
    assert len(details.substitutions) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("scripted", [None, {"code": 200, "msg": "ok"}])
async def test_unknown_order_number_raises_bilka_to_go_error(
    bilka: FakeBilka, scripted: dict | None
) -> None:
    if scripted is not None:
        bilka.script("order_details", scripted)

    with pytest.raises(BilkaToGoError):
        await fetch(bilka, "900000000099")
