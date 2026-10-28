from collections.abc import Awaitable, Callable, Generator

import httpx
import pytest
import respx
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion

from custom_components.bilkatogo.const import DOMAIN
from tests.fake_bilka import EMAIL, PASSWORD, FakeBilka

type SetupIntegration = Callable[[], Awaitable[MockConfigEntry]]


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    return None


@pytest.fixture(autouse=True)
def bilka_backend(bilka: FakeBilka) -> Generator[FakeBilka]:
    """Route every HTTP request Home Assistant's httpx clients send to the fake Bilka backend.

    The integration builds its own httpx client as in production; only the transport
    boundary is replaced, so the real bilkatogo library code runs in these tests.
    """

    def handle(request: httpx.Request) -> httpx.Response:
        return bilka.transport.handle_request(request)

    with respx.mock(assert_all_called=False) as router:
        router.route().mock(side_effect=handle)
        yield bilka


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=EMAIL,
        unique_id=EMAIL,
        minor_version=2,
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> SetupIntegration:
    async def setup() -> MockConfigEntry:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return config_entry

    return setup
