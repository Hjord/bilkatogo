import asyncio
import functools
import json
import sys
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

import httpx
import typer

from . import config
from .client import BilkaToGoClient
from .exceptions import BilkaToGoError, InvalidCredentialsError
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


def resolve_credentials(email: str | None, password: str | None) -> tuple[str, str]:
    saved = config.load_config()
    email = email or saved.get("email") or typer.prompt("Email")
    password = password or saved.get("password") or typer.prompt("Password", hide_input=True)
    return email, password


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


def main() -> None:
    app()
