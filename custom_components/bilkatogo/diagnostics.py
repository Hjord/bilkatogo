import dataclasses
from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import BilkaToGoConfigEntry

TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    "title",
    "unique_id",
    "pickup_code",
    "order_pickup_code",
    "deliveryAddress",
    "address",
    "zipCode",
    "zip_code",
    "zipcity",
    "city",
    "phone",
    "uid",
    "UID",
    "tid",
    "customerId",
    "customer_id",
    "token",
    "id_token",
    "access_token",
    "refresh_token",
    "sessionToken",
    "sessionSecret",
    "login_token",
    "jwt",
    "cookies",
    "PHPSESSID",
    "jwt_validation",
}

CUSTOMER_NAME_PATHS = (("data", "order", "_raw", "name"),)


def _redact_paths(data: dict[str, Any], paths: tuple[tuple[str, ...], ...]) -> dict[str, Any]:
    for *parents, key in paths:
        node: Any = data
        for parent in parents:
            node = node.get(parent) if isinstance(node, dict) else None
        if isinstance(node, dict) and key in node:
            node[key] = REDACTED
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BilkaToGoConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data.data
    diagnostics = async_redact_data(
        {
            "entry": entry.as_dict(),
            "data": dataclasses.asdict(data) if data is not None else None,
        },
        TO_REDACT,
    )
    return _redact_paths(diagnostics, CUSTOMER_NAME_PATHS)
