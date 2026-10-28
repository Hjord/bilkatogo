from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from bilkatogo import OrderStatus

from .coordinator import BilkaToGoConfigEntry
from .entity import BilkaToGoEntity

PARALLEL_UPDATES = 0

READY_FOR_PICKUP = BinarySensorEntityDescription(
    key="ready_for_pickup", translation_key="ready_for_pickup"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BilkaToGoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([BilkaToGoReadyForPickup(entry.runtime_data, READY_FOR_PICKUP)])


class BilkaToGoReadyForPickup(BilkaToGoEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool:
        order = self.coordinator.data.order
        return order is not None and order.status is OrderStatus.PACKED
