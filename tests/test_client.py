import httpx
import pytest

from bilkatogo import BilkaToGoClient, BilkaToGoError, InvalidCredentialsError
from tests.conftest import MemoryTokenStorage
from tests.fake_bilka import EMAIL, PASSWORD, FakeBilka, form


@pytest.mark.asyncio
async def test_login_runs_gigya_and_shop_login_and_stores_the_session(
    bilka: FakeBilka, storage: MemoryTokenStorage
) -> None:
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, token_storage=storage, httpx_client=http) as client,
    ):
        await client.login()

    [login] = bilka.calls("gigya_login")
    assert form(login)["loginID"] == EMAIL
    assert form(login)["password"] == PASSWORD
    assert form(login)["httpStatusCodes"] == "true"
    [jwt] = bilka.calls("gigya_jwt")
    assert form(jwt)["login_token"] == "st2.fake-login-token"
    assert form(jwt)["expiration"] == "86400"
    assert form(jwt)["apiKey"] == form(login)["apiKey"]
    [shop_login] = bilka.calls("login_jwt")
    assert shop_login.headers["jwt_token"] == "eyFake.jwt.token"
    assert shop_login.url.params["u"] == "w"

    assert storage.data is not None
    assert storage.data["jwt"] == "eyFake.jwt.token"
    assert storage.data["cookies"]["PHPSESSID"] == "fake-phpsessid"


@pytest.mark.asyncio
async def test_wrong_password_raises_invalid_credentials_and_stores_nothing(
    bilka: FakeBilka, storage: MemoryTokenStorage
) -> None:
    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, "forkert", token_storage=storage, httpx_client=http) as client,
    ):
        with pytest.raises(InvalidCredentialsError):
            await client.login()

    assert bilka.calls("gigya_jwt") == []
    assert storage.data is None


@pytest.mark.asyncio
async def test_failed_shop_login_raises_and_stores_nothing(
    bilka: FakeBilka, storage: MemoryTokenStorage
) -> None:
    bilka.script("login_jwt", httpx.Response(500, text="Internal Server Error"))

    async with (
        bilka.client() as http,
        BilkaToGoClient(EMAIL, PASSWORD, token_storage=storage, httpx_client=http) as client,
    ):
        with pytest.raises(BilkaToGoError):
            await client.login()

    assert storage.data is None
