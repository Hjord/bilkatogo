import json
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from bilkatogo import Order, OrderDetails
from tests.fake_bilka import EMAIL, PASSWORD, FakeBilka
from tests.ha.conftest import SetupIntegration

VOLATILE = props("entry_id", "created_at", "modified_at")

PERSONAL_DATA = [EMAIL, PASSWORD, "Test Kunde", "Testvej 1", "Eksempelby", "9999", "87654321"]


@dataclass
class DataWithDetails:
    order: Order | None
    details: OrderDetails | None


def assert_no_personal_data(diagnostics: dict[str, Any]) -> None:
    dumped = json.dumps(diagnostics, ensure_ascii=False)
    leaked = [value for value in PERSONAL_DATA if value in dumped]
    assert leaked == []


async def test_diagnostics_show_the_current_order_with_personal_data_redacted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: SetupIntegration,
    snapshot: SnapshotAssertion,
) -> None:
    entry = await setup_integration()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert_no_personal_data(diagnostics)
    assert diagnostics == snapshot(exclude=VOLATILE)


async def test_diagnostics_redact_the_pickup_code_and_address_of_order_details(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: SetupIntegration,
    bilka: FakeBilka,
    snapshot: SnapshotAssertion,
) -> None:
    entry = await setup_integration()
    coordinator = entry.runtime_data
    coordinator.data = DataWithDetails(
        order=coordinator.data.order,
        details=OrderDetails.from_dict(bilka.details["900000000002"]["order"]),
    )

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert_no_personal_data(diagnostics)
    assert diagnostics == snapshot(exclude=VOLATILE)
