from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Any, Self

import httpx

from .const import (
    API_BASE_URL,
    API_HOST,
    CURRENT_ORDER_SCAN_LIMIT,
    GIGYA_API_KEY,
    GIGYA_BASE_URL,
    GIGYA_INVALID_LOGIN_ID,
    JWT_LIFETIME_SECONDS,
    JWT_RENEWAL_MARGIN,
    ORDER_HISTORY_PAGE_SIZE,
    ORDER_HISTORY_PARAMS,
    WEB_PARAMS,
)
from .exceptions import (
    BilkaToGoError,
    BilkaUnreachableError,
    InvalidCredentialsError,
    UnexpectedResponseError,
)
from .models import Order, OrderDetails, current_order
from .token_storage import TokenStorage


class BilkaToGoClient:
    def __init__(
        self,
        email: str,
        password: str | None = None,
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
        self._jwt_expires_at: datetime | None = None

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
        await self._login()

    async def _login(self) -> str:
        if self._password is None:
            raise InvalidCredentialsError("A password is needed to log in")
        login_token = await self._gigya_login(self._password)
        jwt = await self._gigya_jwt(login_token)
        expires_at = datetime.now(UTC) + timedelta(seconds=JWT_LIFETIME_SECONDS)
        response = await self._request(
            "POST", f"{API_BASE_URL}/auth/LoginJWT", params=WEB_PARAMS, headers={"jwt_token": jwt}
        )
        if response.status_code != 200:
            raise UnexpectedResponseError(f"Shop login failed with HTTP {response.status_code}")
        self._jwt = jwt
        self._jwt_expires_at = expires_at
        if self._token_storage is not None:
            await self._token_storage.save(
                {
                    "email": self._email,
                    "jwt": jwt,
                    "jwt_expires_at": expires_at.isoformat(),
                    "cookies": dict(response.cookies),
                }
            )
        return jwt

    async def get_orders(self, limit: int = 5, offset: int = 0) -> list[Order]:
        orders: list[Order] = []
        while len(orders) < limit:
            page_size = min(ORDER_HISTORY_PAGE_SIZE, limit - len(orders))
            data = await self._shop(
                "POST",
                "shop/v7/OrderHistory",
                {"limit": page_size, "offset": offset + len(orders), **ORDER_HISTORY_PARAMS},
            )
            page = [Order.from_dict(order) for order in data.get("orders") or []]
            orders.extend(page)
            if len(page) < page_size:
                break
        return orders

    async def get_order(self, order_number: str) -> OrderDetails:
        data = await self._shop("GET", "shop/v7/OrderDetails", {"orderId": order_number})
        order = data.get("order")
        if not order:
            raise BilkaToGoError(f"Order {order_number} was not found")
        return OrderDetails.from_dict(order)

    async def get_current_order(self) -> OrderDetails | None:
        order = current_order(await self.get_orders(limit=CURRENT_ORDER_SCAN_LIMIT))
        return await self.get_order(order.order_number) if order else None

    async def _shop(self, method: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
        jwt = self._valid_jwt() or await self._restore_session() or await self._login()
        data = await self._shop_request(method, path, params, jwt)
        if data is None:
            data = await self._shop_request(method, path, params, await self._login())
        if data is None:
            raise UnexpectedResponseError(f"{path} rejected a fresh session")
        return data

    async def _shop_request(
        self, method: str, path: str, params: dict[str, Any], jwt: str
    ) -> dict[str, Any] | None:
        response = await self._request(
            method,
            f"{API_BASE_URL}/{path}",
            params={**WEB_PARAMS, **params},
            headers={"jwt_token": jwt},
        )
        if response.status_code == 401:
            return None
        if response.status_code != 200:
            raise UnexpectedResponseError(f"{path} failed with HTTP {response.status_code}")
        data = self._json(response, path)
        if "code" in data and "msg" in data:
            return None
        return data

    async def _restore_session(self) -> str | None:
        if self._token_storage is None:
            return None
        session = await self._token_storage.load()
        if not session or session.get("email") != self._email:
            return None
        try:
            expires_at = datetime.fromisoformat(session["jwt_expires_at"])
            jwt = session["jwt"]
        except KeyError, TypeError, ValueError:
            return None
        for name, value in (session.get("cookies") or {}).items():
            self._http.cookies.set(name, value, domain=API_HOST)
        self._jwt = jwt
        self._jwt_expires_at = expires_at
        return self._valid_jwt()

    def _valid_jwt(self) -> str | None:
        if self._jwt_expires_at is None:
            return None
        if self._jwt_expires_at - JWT_RENEWAL_MARGIN <= datetime.now(UTC):
            return None
        return self._jwt

    async def _gigya_login(self, password: str) -> str:
        data = await self._gigya(
            "accounts.login",
            {
                "loginID": self._email,
                "password": password,
                "apiKey": GIGYA_API_KEY,
                "httpStatusCodes": "true",
            },
        )
        try:
            return data["sessionInfo"]["cookieValue"]
        except KeyError, TypeError:
            raise UnexpectedResponseError("Gigya login answered without a login token") from None

    async def _gigya_jwt(self, login_token: str) -> str:
        data = await self._gigya(
            "accounts.getJWT",
            {
                "apiKey": GIGYA_API_KEY,
                "login_token": login_token,
                "expiration": str(JWT_LIFETIME_SECONDS),
            },
        )
        try:
            return data["id_token"]
        except KeyError:
            raise UnexpectedResponseError("Gigya answered without a JWT") from None

    async def _gigya(self, method: str, form: dict[str, str]) -> dict[str, Any]:
        response = await self._request("POST", f"{GIGYA_BASE_URL}/{method}", data=form)
        data = self._json(response, f"Gigya {method}")
        error_code = data.get("errorCode", 0)
        if error_code == GIGYA_INVALID_LOGIN_ID:
            raise InvalidCredentialsError(data.get("errorMessage", "Invalid email or password"))
        if error_code != 0 or response.status_code != 200:
            raise UnexpectedResponseError(
                f"Gigya {method} failed: {data.get('errorMessage', error_code)}"
            )
        return data

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self._http.request(method, url, **kwargs)
        except httpx.TransportError as err:
            raise BilkaUnreachableError(f"Could not reach {httpx.URL(url).host}: {err}") from err

    @staticmethod
    def _json(response: httpx.Response, what: str) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            raise UnexpectedResponseError(
                f"{what} answered HTTP {response.status_code} without JSON"
            ) from None
        if not isinstance(data, dict):
            raise UnexpectedResponseError(f"{what} answered JSON that is not an object")
        return data
