import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
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
    "location",
    "name",
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


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BilkaToGoConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data.data
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "data": dataclasses.asdict(data) if data is not None else None,
        },
        TO_REDACT,
    )
