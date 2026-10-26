# bilkatogo

Async Python client and CLI for tracking BilkaToGo orders.

```sh
uvx --from 'bilkatogo[cli]' bilkatogo login
```

The Home Assistant integration lives in `custom_components/bilkatogo/`.

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
