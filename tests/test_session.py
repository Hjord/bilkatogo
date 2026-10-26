from datetime import UTC, datetime, timedelta

import httpx
import pytest

from bilkatogo import BilkaToGoClient, UnexpectedResponseError
from tests.conftest import MemoryTokenStorage
from tests.fake_bilka import EMAIL, PASSWORD, FakeBilka

UNAUTHORIZED = httpx.Response(401, json={"code": 401, "msg": "Unauthorized"})


async def log_in(bilka: FakeBilka, storage: MemoryTokenStorage) -> None:
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, token_storage=storage, httpx_client=http) as client,
    ):
        await client.login()


@pytest.mark.asyncio
async def test_unauthorized_shop_call_logs_in_again_and_retries_once(
    bilka: FakeBilka, storage: MemoryTokenStorage
) -> None:
    await log_in(bilka, storage)
    bilka.script("order_history", UNAUTHORIZED)

    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, token_storage=storage, httpx_client=http) as client,
    ):
        orders = await client.get_orders()

    assert len(orders) == 2
    assert len(bilka.calls("order_history")) == 2
    assert len(bilka.calls("gigya_login")) == 2
    assert len(bilka.calls("login_jwt")) == 2


@pytest.mark.asyncio
async def test_unauthorized_again_after_a_fresh_login_raises_instead_of_looping(
    bilka: FakeBilka, storage: MemoryTokenStorage
) -> None:
    await log_in(bilka, storage)
    bilka.script("order_history", UNAUTHORIZED, UNAUTHORIZED, UNAUTHORIZED)

    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, token_storage=storage, httpx_client=http) as client,
    ):
        with pytest.raises(UnexpectedResponseError):
            await client.get_orders()

    assert len(bilka.calls("order_history")) == 2
    assert len(bilka.calls("gigya_login")) == 2


@pytest.mark.asyncio
async def test_ok_answer_with_an_error_body_counts_as_an_expired_session(
    bilka: FakeBilka, storage: MemoryTokenStorage
) -> None:
    await log_in(bilka, storage)
    bilka.script("order_history", {"code": 1, "msg": "Du er ikke logget ind"})

    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, token_storage=storage, httpx_client=http) as client,
    ):
        orders = await client.get_orders()

    assert len(orders) == 2
    assert len(bilka.calls("gigya_login")) == 2


@pytest.mark.asyncio
async def test_stored_session_about_to_expire_is_renewed_before_the_shop_call(
    bilka: FakeBilka, storage: MemoryTokenStorage
) -> None:
    await log_in(bilka, storage)
    assert storage.data is not None
    soon = datetime.now(UTC) + timedelta(minutes=2)
    storage.data["jwt_expires_at"] = soon.isoformat()

    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, token_storage=storage, httpx_client=http) as client,
    ):
        await client.get_orders()

    assert len(bilka.calls("gigya_login")) == 2
    assert len(bilka.calls("order_history")) == 1
    assert datetime.fromisoformat(storage.data["jwt_expires_at"]) > soon + timedelta(hours=23)
