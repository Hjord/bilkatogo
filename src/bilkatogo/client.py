from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Any, Self

import httpx

from .const import (
    API_BASE_URL,
    GIGYA_API_KEY,
    GIGYA_BASE_URL,
    GIGYA_INVALID_LOGIN_ID,
    JWT_LIFETIME_SECONDS,
    WEB_PARAMS,
)
from .exceptions import BilkaToGoError, InvalidCredentialsError
from .token_storage import TokenStorage


class BilkaToGoClient:
    def __init__(
        self,
        email: str,
        password: str,
        *,
        token_storage: TokenStorage | None = None,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._token_storage = token_storage
        self._owns_http = httpx_client is None
        self._http = httpx_client or httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        self._jwt: str | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def login(self) -> None:
        login_token = await self._gigya_login()
        jwt = await self._gigya_jwt(login_token)
        expires_at = datetime.now(UTC) + timedelta(seconds=JWT_LIFETIME_SECONDS)
        response = await self._http.post(
            f"{API_BASE_URL}/auth/LoginJWT", params=WEB_PARAMS, headers={"jwt_token": jwt}
        )
        if response.status_code != 200:
            raise BilkaToGoError(f"Shop login failed with HTTP {response.status_code}")
        self._jwt = jwt
        if self._token_storage is not None:
            await self._token_storage.save(
                {
                    "email": self._email,
                    "jwt": jwt,
                    "jwt_expires_at": expires_at.isoformat(),
                    "cookies": dict(response.cookies),
                }
            )

    async def _gigya_login(self) -> str:
        data = await self._gigya(
            "accounts.login",
            {
                "loginID": self._email,
                "password": self._password,
                "apiKey": GIGYA_API_KEY,
                "httpStatusCodes": "true",
            },
        )
        return data["sessionInfo"]["cookieValue"]

    async def _gigya_jwt(self, login_token: str) -> str:
        data = await self._gigya(
            "accounts.getJWT",
            {
                "apiKey": GIGYA_API_KEY,
                "login_token": login_token,
                "expiration": str(JWT_LIFETIME_SECONDS),
            },
        )
        return data["id_token"]

    async def _gigya(self, method: str, form: dict[str, str]) -> dict[str, Any]:
        response = await self._http.post(f"{GIGYA_BASE_URL}/{method}", data=form)
        data = response.json()
        error_code = data.get("errorCode", 0)
        if error_code == GIGYA_INVALID_LOGIN_ID:
            raise InvalidCredentialsError(data.get("errorMessage", "Invalid email or password"))
        if error_code != 0 or response.status_code != 200:
            raise BilkaToGoError(f"Gigya {method} failed: {data.get('errorMessage', error_code)}")
        return data
