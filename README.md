# bilkatogo

Track your [BilkaToGo](https://www.bilkatogo.dk) grocery orders: an async Python library, a
command line tool and a Home Assistant integration that follow your order from the moment it is
placed until you pick it up, including which products Bilka substituted.

> **Unofficial.** This project is not affiliated with or endorsed by Bilka or Salling Group. It
> uses the same private web API as the bilkatogo.dk website, logging in with your email and
> password. That API can change or break at any time.

The library, the CLI and the Home Assistant integration are released together and always share
the same version.

- [Library](#library): an async Python client for your orders, Pickup Points and product search.
- [Command line](#command-line): the same from your terminal or a script.
- [Home Assistant](#home-assistant): sensors and events for your Current Order.

## Library

```sh
pip install bilkatogo
```

It depends on httpx, plus tzdata on Windows.

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
- `PickupSlot.starts_at` and `ends_at` are timezone-aware datetimes in Europe/Copenhagen.
- Amounts are `Decimal` kroner.
- `OrderDetails.order_total` is the Order Total, broken down into `deposit`, `service_fee`,
  `packaging`, `delivery_fee` and `discount`. `ordered_total` is what the Order cost when it was
  placed, looked up in the order history (`None` when it is not among the latest 20 Orders).
  Pass an `Order` to `get_order` instead of its number to skip that lookup.
- `get_cart()` returns your `Cart`: its `lines` (each a `CartLine` with `product`,
  `article_number`, `quantity`, `price` and `line_total`, with any Multibuy Offer already
  applied in the line total), the Cart `total` broken down into `deposit`, `service_fee`,
  `packaging` and `discount`, and the chosen `pickup_point`. Bilka's bag and Pakkeservice lines
  are not Cart Lines; they show up as `packaging` and `service_fee`.

## Command line

```sh
pip install 'bilkatogo[cli]'
```

Or run it without installing:

```sh
uvx --from 'bilkatogo[cli]' bilkatogo --help
```

```sh
bilkatogo login                 # log in and store the session
bilkatogo orders --limit 10     # list your most recent orders
bilkatogo order                 # show the Current Order with its details
bilkatogo order 900000000001    # show one order by Order Number
bilkatogo pickup-points         # list Pickup Points and their Store, * marks your Cart's
bilkatogo search skyr           # Products with Price, stock and Offer at your Cart's Store
bilkatogo search skyr --pickup-point "Bilka Vejle" --limit 5
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

## Home Assistant

1. Add the integration from the Home Assistant Marketplace (HACS) by searching for
   **BilkaToGo**, or add `https://github.com/nickknissen/bilkatogo` as a custom repository of
   type Integration. Restart Home Assistant afterwards.
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
| Missing Items | Number of products packed short without a replacement | List of Product, Article Number, ordered and missing quantity |
| Order Total | What you pay for the order now (DKK) | Order Number, Ordered Total, difference from the Ordered Total (negative when you pay less), Deposit, Service Fee, Packaging, Delivery Fee, Discount |
| Pickup Slot | Start of the pickup slot (timestamp, Europe/Copenhagen) | Order Number, Order Total (DKK), Pickup Slot end |
| Pickup Code | The code you enter at check-in | Order Number, Order Total (DKK) |
| Pickup Point | The Bilka store you pick up from | Order Number, Order Total (DKK) |

Substitutions, Missing Items, the Pickup Code and the Order Total breakdown (Deposit, Service
Fee, Packaging, Delivery Fee, Discount) are fetched once the order is packed. Before that the
Order Total is Bilka's estimate from the order history.

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

### Event `bilkatogo_missing_item`

Fired once for every new Missing Item, with this data:

| Field | Example |
|---|---|
| `order_number` | `900000000003` |
| `product` | `Skyr` |
| `article_number` | `932058` |
| `ordered_quantity` | `4` |
| `missing_quantity` | `2` |

Missing Items that already fired are remembered across restarts and reloads. An automation
that sends a notification:

```yaml
automation:
  - alias: BilkaToGo missing item
    triggers:
      - trigger: event
        event_type: bilkatogo_missing_item
    actions:
      - action: notify.notify
        data:
          message: >
            {{ trigger.event.data.product }}: {{ trigger.event.data.missing_quantity }}
            of {{ trigger.event.data.ordered_quantity }} missing.
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

Home Assistant does not run on Windows. There, `scripts/ha-test.sh` runs both commands in WSL:

```sh
wsl.exe -e bash scripts/ha-test.sh
```

The Home Assistant tests run the real library against the fake Bilka backend in
`tests/fake_bilka.py`. The integration creates its httpx client with Home Assistant's
`create_async_httpx_client`, and `tests/ha/conftest.py` routes every request at the
transport level to the fake backend with `respx`, so nothing in the integration is patched.

Releasing is described in [AGENTS.md](AGENTS.md#releasing).

## License

MIT
