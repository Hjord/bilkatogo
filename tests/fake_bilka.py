import json
from collections import defaultdict, deque
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, parse_qsl

import httpx

FIXTURES = Path(__file__).parent / "fixtures"

EMAIL = "kunde@example.com"
PASSWORD = "hemmeligt-kodeord"
SESSION_COOKIES = {"PHPSESSID": "fake-phpsessid", "jwt_validation": "fake-jwt-validation"}
ALGOLIA_APP_ID = "F9VBJLR1BK"
ALGOLIA_SEARCH_KEY = "1deaf41c87e729779f7695c00f190cc9"
ALGOLIA_INDEX = "prod_BILKATOGO_PRODUCTS"

ROUTES: dict[tuple[str, str], str] = {
    ("POST", "https://accounts.eu1.gigya.com/accounts.login"): "gigya_login",
    ("POST", "https://accounts.eu1.gigya.com/accounts.getJWT"): "gigya_jwt",
    ("POST", "https://api.bilkatogo.dk/api/auth/LoginJWT"): "login_jwt",
    ("POST", "https://api.bilkatogo.dk/api/shop/v7/OrderHistory"): "order_history",
    ("GET", "https://api.bilkatogo.dk/api/shop/v7/OrderDetails"): "order_details",
    (
        "GET",
        "https://api.bilkatogo.dk/api/shop/v6/AvailableDeliveryAddresses",
    ): "available_delivery_addresses",
    ("GET", "https://api.bilkatogo.dk/api/shop/v6/Cart"): "cart",
    ("GET", "https://api.bilkatogo.dk/api/shop/v6/ChangeLineCount"): "change_line_count",
    ("GET", "https://api.bilkatogo.dk/api/shop/v6/EmptyCart"): "empty_cart",
    ("POST", "https://f9vbjlr1bk-dsn.algolia.net/1/indexes/*/queries"): "algolia",
}

type Handler = Callable[[httpx.Request], httpx.Response]
type Scripted = httpx.Response | dict[str, Any] | Exception | Handler


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def form(request: httpx.Request) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(request.content.decode()).items()}


def algolia_query(request: httpx.Request) -> dict[str, str]:
    [query] = json.loads(request.content)["requests"]
    return {"indexName": query["indexName"], **dict(parse_qsl(query["params"]))}


class FakeBilka:
    """Fake Bilka backend: Gigya login, the shop API and the Algolia product index, served
    through httpx.MockTransport.

    Each request is matched against ROUTES to a route name. If a script was queued for that
    route with `script()`, the next scripted response is used; otherwise the default handler
    method of the same name answers, which behaves like the real backend for one account.
    """

    def __init__(self, email: str = EMAIL, password: str = PASSWORD) -> None:
        self.email = email
        self.password = password
        self.requests: list[httpx.Request] = []
        self.orders: list[dict[str, Any]] = load_fixture("order_history.json")["orders"]
        self.details: dict[str, dict[str, Any]] = {
            details["order"]["orderId"]: details
            for details in map(
                load_fixture,
                [
                    "order_details_substituted.json",
                    "order_details_plain.json",
                    "order_details_missing.json",
                    "order_details_captured.json",
                ],
            )
        }
        self.delivery_addresses: dict[str, Any] = load_fixture("available_delivery_addresses.json")
        self.cart_contents: dict[str, Any] = load_fixture("cart.json")
        self.products: list[dict[str, Any]] = load_fixture("algolia_products.json")["hits"]
        self.change_answer: dict[str, Any] = load_fixture("change_line_count.json")
        self.max_quantity: int | None = None
        self._scripts: dict[str, deque[Scripted]] = defaultdict(deque)
        self.transport = httpx.MockTransport(self._handle)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self.transport)

    def script(self, route: str, *responses: Scripted) -> None:
        if route not in ROUTES.values():
            raise ValueError(f"Unknown route {route!r}")
        self._scripts[route].extend(responses)

    def calls(self, route: str) -> list[httpx.Request]:
        return [r for r in self.requests if self._route_of(r) == route]

    def _route_of(self, request: httpx.Request) -> str | None:
        url = request.url.copy_with(query=None)
        return ROUTES.get((request.method, str(url)))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        route = self._route_of(request)
        if route is None:
            return httpx.Response(404, json={"error": f"fake: no route for {request.url}"})
        if self._scripts[route]:
            return self._play(self._scripts[route].popleft(), request)
        return getattr(self, route)(request)

    @staticmethod
    def _play(scripted: Scripted, request: httpx.Request) -> httpx.Response:
        if isinstance(scripted, Exception):
            raise scripted
        if isinstance(scripted, httpx.Response):
            return scripted
        if isinstance(scripted, dict):
            return httpx.Response(200, json=scripted)
        return scripted(request)

    def has_shop_session(self, request: httpx.Request) -> bool:
        sent = request.headers.get("cookie", "")
        return (
            request.headers.get("jwt_token") == load_fixture("gigya_jwt.json")["id_token"]
            and request.url.params.get("u") == "w"
            and f"PHPSESSID={SESSION_COOKIES['PHPSESSID']}" in sent
        )

    def gigya_login(self, request: httpx.Request) -> httpx.Response:
        data = form(request)
        if data.get("loginID") != self.email or data.get("password") != self.password:
            return httpx.Response(403, json=load_fixture("gigya_login_invalid.json"))
        return httpx.Response(200, json=load_fixture("gigya_login.json"))

    def gigya_jwt(self, request: httpx.Request) -> httpx.Response:
        login_token = load_fixture("gigya_login.json")["sessionInfo"]["cookieValue"]
        if form(request).get("login_token") != login_token:
            return httpx.Response(
                403, json={"statusCode": 403, "errorCode": 403005, "errorMessage": "Unauthorized"}
            )
        return httpx.Response(200, json=load_fixture("gigya_jwt.json"))

    def login_jwt(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("jwt_token") != load_fixture("gigya_jwt.json")["id_token"]:
            return httpx.Response(401, json={"code": 401, "msg": "Unauthorized"})
        headers = [("set-cookie", f"{k}={v}; path=/") for k, v in SESSION_COOKIES.items()]
        return httpx.Response(200, json=load_fixture("login_jwt.json"), headers=headers)

    def order_history(self, request: httpx.Request) -> httpx.Response:
        if not self.has_shop_session(request):
            return httpx.Response(401, json={"code": 401, "msg": "Unauthorized"})
        limit = int(request.url.params["limit"])
        offset = int(request.url.params["offset"])
        page = self.orders[offset : offset + limit]
        return httpx.Response(200, json={"total": len(self.orders), "orders": page})

    def order_details(self, request: httpx.Request) -> httpx.Response:
        if not self.has_shop_session(request):
            return httpx.Response(401, json={"code": 401, "msg": "Unauthorized"})
        details = self.details.get(request.url.params.get("orderId", ""))
        if details is None:
            return httpx.Response(404, json={"code": 404, "msg": "Not found"})
        return httpx.Response(200, json=details)

    def available_delivery_addresses(self, request: httpx.Request) -> httpx.Response:
        if not self.has_shop_session(request):
            return httpx.Response(401, json={"code": 401, "msg": "Unauthorized"})
        return httpx.Response(200, json=self.delivery_addresses)

    def cart(self, request: httpx.Request) -> httpx.Response:
        if not self.has_shop_session(request):
            return httpx.Response(401, json={"code": 401, "msg": "Unauthorized"})
        return httpx.Response(200, json=self.cart_contents)

    def change_line_count(self, request: httpx.Request) -> httpx.Response:
        if not self.has_shop_session(request):
            return httpx.Response(401, json={"code": 401, "msg": "Unauthorized"})
        article_number = request.url.params["productId"]
        count = int(request.url.params["count"])
        if self.max_quantity is not None:
            count = min(count, self.max_quantity)
        self._set_line(article_number, count)
        answer = dict(self.change_answer)
        answer.update(productId=article_number, productAmount=count)
        return httpx.Response(200, json=answer)

    def _set_line(self, article_number: str, count: int) -> None:
        for group in self.cart_contents["lines"]:
            for block in group["lines"]:
                for line in block["orderlines"]:
                    if str(line["product"]["objectID"]) == article_number:
                        line.update(quantity=count, amount=count * line["unitprice"])
                        if count == 0:
                            block["orderlines"].remove(line)
                        return
        if count == 0:
            return
        [hit] = [hit for hit in self.products if hit["objectID"] == article_number]
        line = {
            "product": {
                "objectID": int(article_number),
                "name": hit["name"],
                "price": hit["price"],
            },
            "quantity": count,
            "unitprice": hit["price"],
            "amount": count * hit["price"],
        }
        self.cart_contents["lines"].append(
            {"headline": "Andet", "type": "products", "lines": [{"orderlines": [line]}]}
        )

    def empty_cart(self, request: httpx.Request) -> httpx.Response:
        if not self.has_shop_session(request):
            return httpx.Response(401, json={"code": 401, "msg": "Unauthorized"})
        self.cart_contents["lines"] = [
            group
            for group in self.cart_contents["lines"]
            if group["headline"] in ("Emballage", "Services")
        ]
        return httpx.Response(200, json=self.cart_contents)

    def algolia(self, request: httpx.Request) -> httpx.Response:
        if (
            request.headers.get("x-algolia-application-id") != ALGOLIA_APP_ID
            or request.headers.get("x-algolia-api-key") != ALGOLIA_SEARCH_KEY
        ):
            return httpx.Response(403, json={"message": "Invalid Application-ID or API key"})
        query = algolia_query(request)
        if query["indexName"] != ALGOLIA_INDEX:
            return httpx.Response(404, json={"message": "Index does not exist"})
        filters = dict(
            term.split(":", 1) for term in query.get("filters", "").split(" AND ") if term
        )
        if filters.get("nonsearchable") != "false" or "isInAssortmentIn" not in filters:
            return httpx.Response(400, json={"message": "fake: unexpected filters"})
        store = int(filters["isInAssortmentIn"])
        words = query.get("query", "").casefold().split()
        hits = [
            hit
            for hit in self.products
            if store in hit["isInAssortmentIn"]
            and all(word in f"{hit['name']} {hit['brand']}".casefold() for word in words)
        ][: int(query.get("hitsPerPage", 20))]
        attributes = json.loads(query.get("attributesToRetrieve", "[]"))
        hits = [retrieve(hit, attributes) for hit in hits]
        return httpx.Response(
            200, json={"results": [{"hits": hits, "nbHits": len(hits), "index": ALGOLIA_INDEX}]}
        )


def retrieve(hit: dict[str, Any], attributes: list[str]) -> dict[str, Any]:
    """The real index returns only objectID unless attributesToRetrieve names more."""
    if "*" in attributes:
        return hit
    picked: dict[str, Any] = {"objectID": hit["objectID"]}
    for attribute in attributes:
        name, _, key = attribute.partition(".")
        if name not in hit:
            continue
        if key:
            if key in hit[name]:
                picked.setdefault(name, {})[key] = hit[name][key]
        else:
            picked[name] = hit[name]
    return picked
