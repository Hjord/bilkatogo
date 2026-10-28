from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from bilkatogo import OrderStatus

from .const import DOMAIN
from .coordinator import BilkaToGoCoordinator

UNRECOGNIZED_STATUS = "unrecognized"


def status_option(status: OrderStatus) -> str:
    return UNRECOGNIZED_STATUS if status is OrderStatus.UNKNOWN else status.value


class BilkaToGoEntity(CoordinatorEntity[BilkaToGoCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: BilkaToGoCoordinator, description: EntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Bilka",
            model="BilkaToGo",
            entry_type=DeviceEntryType.SERVICE,
        )
