import pytest

from bilkatogo import BilkaToGoClient
from tests.fake_bilka import EMAIL, PASSWORD, FakeBilka


@pytest.mark.asyncio
async def test_pickup_points_have_name_address_and_store(bilka: FakeBilka) -> None:
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, httpx_client=http) as client,
    ):
        points = await client.get_pickup_points()

    [request] = bilka.calls("available_delivery_addresses")
    assert request.method == "GET"
    assert dict(request.url.params) == {"u": "w", "orderByZipcode": "1"}

    assert len(points) == 22
    by_name = {point.name: point for point in points}
    fredericia = by_name["Pickup Fredericia"]
    assert fredericia.address == "Strandvejen 220"
    assert fredericia.zip_code == "7000"
    assert fredericia.city == "Fredericia"
    assert fredericia.store_id == "1662"
    assert by_name["Bilka Kolding"].store_id == "1662"
    assert by_name["PickUp Skejby"].store_id == "1651"
    assert by_name["Bilka Tilst"].store_id == "1651"
    assert by_name["Bilka Vejle"].store_id == "1661"
    assert by_name["Bilka Odense"].address == "Niels Bohrs Alle 150"
