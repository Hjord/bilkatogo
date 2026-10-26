import asyncio
import functools
import json
import sys
from collections.abc import Callable, Coroutine
from datetime import date, datetime, time
from typing import Annotated, Any

import httpx
import typer

from . import config
from .client import BilkaToGoClient
from .exceptions import BilkaToGoError, InvalidCredentialsError
from .models import BilkaDataClass, Order
from .token_storage import FileTokenStorage

app = typer.Typer(no_args_is_help=True, help="Track your BilkaToGo orders.")

EmailOption = Annotated[
    str | None, typer.Option("--email", envvar="BILKATOGO_EMAIL", help="BilkaToGo account email.")
]
PasswordOption = Annotated[
    str | None,
    typer.Option("--password", envvar="BILKATOGO_PASSWORD", help="BilkaToGo account password."),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Output JSON.")]


def run_async[**P, R](func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
        return asyncio.run(func(*args, **kwargs), loop_factory=loop_factory)

    return wrapper


def known_credentials(email: str | None, password: str | None) -> tuple[str | None, str | None]:
    saved = config.load_config()
    return email or saved.get("email"), password or saved.get("password")


def resolve_credentials(email: str | None, password: str | None) -> tuple[str, str]:
    email, password = known_credentials(email, password)
    return email or typer.prompt("Email"), password or prompt_password()


def prompt_password() -> str:
    return typer.prompt("Password", hide_input=True)


def to_json(data: Any) -> str:
    def default(obj: Any) -> Any:
        if isinstance(obj, BilkaDataClass):
            return dict(obj)
        if isinstance(obj, datetime | date | time):
            return obj.isoformat()
        raise TypeError(f"Cannot serialise {type(obj).__name__}")

    return json.dumps(data, default=default, ensure_ascii=False)


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [max(len(cell) for cell in column) for column in zip(headers, *rows, strict=True)]
    for row in [headers, *rows]:
        typer.echo("  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)))


def http_client(ctx: typer.Context) -> httpx.AsyncClient | None:
    factory = ctx.obj
    return factory() if callable(factory) else None


def fail(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(code=1)


@app.callback()
def main_callback() -> None:
    pass


@app.command()
@run_async
async def login(
    ctx: typer.Context,
    email: EmailOption = None,
    password: PasswordOption = None,
    as_json: JsonOption = False,
) -> None:
    """Log in and store the session for later commands."""
    email, password = resolve_credentials(email, password)
    storage = FileTokenStorage(config.session_file())
    http = http_client(ctx)
    try:
        async with BilkaToGoClient(
            email, password, token_storage=storage, httpx_client=http
        ) as client:
            await client.login()
    except InvalidCredentialsError:
        raise fail("Login failed: Wrong email or password.") from None
    except BilkaToGoError as err:
        raise fail(f"Login failed: {err}") from None
    finally:
        if http is not None:
            await http.aclose()

    if as_json:
        typer.echo(json.dumps({"email": email, "logged_in": True}))
    else:
        typer.echo(f"Logged in as {email}.")


LimitOption = Annotated[int, typer.Option("--limit", min=1, help="Number of orders to show.")]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@app.command()
@run_async
async def orders(
    ctx: typer.Context,
    limit: LimitOption = 5,
    email: EmailOption = None,
    password: PasswordOption = None,
    as_json: JsonOption = False,
) -> None:
    """Show your Orders with their Pickup Slot and Order Status."""
    storage = FileTokenStorage(config.session_file())
    email, password = known_credentials(email, password)
    if email is None:
        session = await storage.load()
        email = (session or {}).get("email") or typer.prompt("Email")
    http = http_client(ctx)
    try:
        try:
            async with BilkaToGoClient(
                email, password, token_storage=storage, httpx_client=http
            ) as client:
                found = await client.get_orders(limit=limit)
        except InvalidCredentialsError:
            if password is not None:
                raise
            async with BilkaToGoClient(
                email, prompt_password(), token_storage=storage, httpx_client=http
            ) as client:
                found = await client.get_orders(limit=limit)
    except InvalidCredentialsError:
        raise fail("Login failed: Wrong email or password.") from None
    except BilkaToGoError as err:
        raise fail(f"Could not fetch orders: {err}") from None
    finally:
        if http is not None:
            await http.aclose()

    if as_json:
        typer.echo(to_json(found))
    elif not found:
        typer.echo("No orders.")
    else:
        print_table(
            ["Order", "Ordered", "Pickup Slot", "Pickup Point", "Status"],
            [order_row(order) for order in found],
        )


def order_row(order: Order) -> list[str]:
    slot = order.pickup_slot
    point = order.pickup_point
    return [
        order.order_number,
        order.ordered_at.strftime("%Y-%m-%d %H:%M") if order.ordered_at else "",
        f"{WEEKDAYS[slot.date.weekday()]} {slot.date:%d/%m} {slot.start:%H:%M}-{slot.end:%H:%M}"
        if slot
        else "",
        "Home Delivery" if order.home_delivery else (point.name if point else ""),
        order.status.name.replace("_", " ").title(),
    ]


def main() -> None:
    app()
