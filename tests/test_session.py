from datetime import UTC, datetime, timedelta

import httpx
import pytest

from bilkatogo import BilkaToGoClient, BilkaUnreachableError, UnexpectedResponseError
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("route", "failure"),
    [
        ("order_history", httpx.ConnectError("fake: connection refused")),
        ("order_history", httpx.ReadTimeout("fake: read timed out")),
        ("gigya_login", httpx.ConnectTimeout("fake: connect timed out")),
        ("login_jwt", httpx.ConnectError("fake: connection reset")),
    ],
)
async def test_connection_failures_raise_bilka_unreachable(
    bilka: FakeBilka, route: str, failure: Exception
) -> None:
    bilka.script(route, failure)

    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, httpx_client=http) as client,
    ):
        with pytest.raises(BilkaUnreachableError):
            await client.get_orders()


HTML_ERROR = "<html><body>Bad Gateway</body></html>"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("route", "response"),
    [
        ("order_history", httpx.Response(200, text=HTML_ERROR)),
        ("order_history", httpx.Response(500, json={"error": "fake"})),
        ("order_history", httpx.Response(200, json=["not", "an", "object"])),
        ("gigya_login", httpx.Response(502, text=HTML_ERROR)),
        ("gigya_login", httpx.Response(200, json={"errorCode": 0})),
        ("gigya_jwt", httpx.Response(500, json={"errorCode": 500001, "errorMessage": "fake"})),
        ("login_jwt", httpx.Response(500, text="Internal Server Error")),
    ],
)
async def test_unexpected_answers_raise_unexpected_response(
    bilka: FakeBilka, route: str, response: httpx.Response
) -> None:
    bilka.script(route, response)

    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, httpx_client=http) as client,
    ):
        with pytest.raises(UnexpectedResponseError):
            await client.get_orders()
