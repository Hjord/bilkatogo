# bilkatogo

Track your [BilkaToGo](https://www.bilkatogo.dk) grocery orders: an async Python library, a
command line tool and a Home Assistant integration that follow your order from the moment it is
placed until you pick it up, including which products Bilka substituted.

> **Unofficial.** This project is not affiliated with or endorsed by Bilka or Salling Group. It
> uses the same private web API as the bilkatogo.dk website, logging in with your email and
> password. That API can change or break at any time.

The library, the CLI and the Home Assistant integration are released together and always share
the same version.

## Installation

Library only (its sole dependency is httpx):

```sh
pip install bilkatogo
```

With the command line tool:

```sh
pip install 'bilkatogo[cli]'
```

Or run the CLI without installing it:

```sh
uvx --from 'bilkatogo[cli]' bilkatogo --help
```

Home Assistant: add the integration from the Home Assistant Marketplace (HACS) by searching
for **BilkaToGo**, or add `https://github.com/nickknissen/bilkatogo` as a custom repository of
type Integration. Restart Home Assistant afterwards.

## Command line

```sh
bilkatogo login                 # log in and store the session
bilkatogo orders --limit 10     # list your most recent orders
bilkatogo order                 # show the Current Order with its details
bilkatogo order 900000000001    # show one order by Order Number
```

Every command accepts `--json` for machine-readable output.

Credentials are looked up in this order:

1. `--email` and `--password`
2. the `BILKATOGO_EMAIL` and `BILKATOGO_PASSWORD` environment variables
3. `config.json` (with `email` and `password` keys) in the user config directory
   (`~/.config/bilkatogo` on Linux, `%APPDATA%\bilkatogo` on Windows,
   `~/Library/Application Support/bilkatogo` on macOS); set `BILKATOGO_CONFIG_DIR` to use
   another directory
4. an interactive prompt

The session is stored as `session.json` in the same directory, so later commands don't log in
again.

The Current Order is the unfinished order with the earliest pickup slot or, when every order
is finished, the most recently finished one.

## Library

```python
import asyncio

from bilkatogo import BilkaToGoClient, FileTokenStorage


async def main() -> None:
    async with BilkaToGoClient(
        "you@example.com",
        "your-password",
        token_storage=FileTokenStorage("session.json"),
    ) as client:
        for order in await client.get_orders(limit=5):
            print(order.order_number, order.status, order.pickup_slot)

        current = await client.get_current_order()
        if current:
            if current.pickup_code:
                print("Pickup Code:", current.pickup_code.code)
            for substitution in current.substitutions:
                print(substitution.original_product, "->", substitution.replacement_product)


asyncio.run(main())
```

- `BilkaToGoClient(email, password, *, token_storage=None, httpx_client=None)` is an async
  context manager. Pass your own `httpx.AsyncClient` to control timeouts or proxies; the
  client only closes clients it created itself.
- `login()`, `get_orders(limit=5)`, `get_order(order_number)` and `get_current_order()` are the
  public operations. The client logs in on demand, refreshes the session before it expires and
  logs in again when Bilka rejects it.
- `token_storage` is any `TokenStorage` (async `load()` and `save(data)`). `FileTokenStorage`
  stores the session in a JSON file.
- Errors derive from `BilkaToGoError`: `InvalidCredentialsError`, `BilkaUnreachableError` and
  `UnexpectedResponseError`.
- `Order.status` is an `OrderStatus` (Processing, Received, Packed, Picked Up, Not Collected,
  Cancelled, Sold Out, Unknown), using the same words as the website. The raw Bilka status code
  is kept in `status_code`. The mapping is listed in [GLOSSARY.md](GLOSSARY.md).
- Prices are in øre.

## Home Assistant

1. Install the integration (see [Installation](#installation)) and restart Home Assistant.
2. Go to **Settings > Devices & services > Add integration** and pick **BilkaToGo**.
3. Sign in with the email and password you use on bilkatogo.dk. Add the integration once per
   account.

If the password changes, Home Assistant asks you to sign in again.

The integration polls Bilka every 60 minutes, and every 5 minutes from 3 hours before the
pickup slot starts until the order is picked up, not collected or cancelled.

### Entities

All entities describe the Current Order.

| Entity | State | Attributes |
|---|---|---|
| Order Status | Processing, Received, Packed, Picked Up, Not Collected, Cancelled, Sold Out or Unknown | Bilka status code |
| Substitutions | Number of substituted products | List of Original Product, Replacement Product and the Replacement Product's quantity |
| Pickup Slot | Start of the pickup slot (timestamp, Europe/Copenhagen) | Order Number, price (DKK), Pickup Slot end |
| Pickup Code | The code you enter at check-in | Order Number, price (DKK) |
| Pickup Point | The Bilka store you pick up from | Order Number, price (DKK) |

Substitutions and the Pickup Code are fetched once the order is packed.

An Order Status of Unknown (`unrecognized`) means Bilka sent a status code the integration does
not know yet; the code is in the attribute. Without any order the entities have no state.

### Event `bilkatogo_substitution`

Fired once for every new substitution, with this data:

| Field | Example |
|---|---|
| `order_number` | `900000000001` |
| `original_product` | `Arla minimælk 1 l` |
| `replacement_product` | `Øko minimælk 1 l` |
| `quantity` | `2` |

Substitutions that already fired are remembered across restarts and reloads. An automation
that sends a notification:

```yaml
automation:
  - alias: BilkaToGo substitution
    triggers:
      - trigger: event
        event_type: bilkatogo_substitution
    actions:
      - action: notify.notify
        data:
          message: >
            {{ trigger.event.data.original_product }} was replaced by
            {{ trigger.event.data.replacement_product }}
            ({{ trigger.event.data.quantity }}).
```

## Development

Library and CLI:

```sh
uv run ruff format --check . && uv run ruff check . && uv run ty check && uv run pytest
```

Home Assistant tests use their own dependency group, because
`pytest-homeassistant-custom-component` pins its own pytest and httpx. Keep them in a
separate virtual environment so the library environment stays untouched:

```sh
UV_PROJECT_ENVIRONMENT=.venv-ha uv run --no-default-groups --group ha pytest tests/ha
UV_PROJECT_ENVIRONMENT=.venv-ha uv run --no-default-groups --group ha ty check custom_components tests/ha
```

Home Assistant does not run on Windows; use Linux, WSL or CI for these.

The Home Assistant tests run the real library against the fake Bilka backend in
`tests/fake_bilka.py`. The integration creates its httpx client with Home Assistant's
`create_async_httpx_client`, and `tests/ha/conftest.py` routes every request at the
transport level to the fake backend with `respx`, so nothing in the integration is patched.

Releasing is described in [AGENTS.md](AGENTS.md#releasing).

## License

MIT
