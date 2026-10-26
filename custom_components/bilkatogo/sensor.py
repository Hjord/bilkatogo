from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from bilkatogo import OrderStatus

from .const import DOMAIN
from .coordinator import BilkaToGoConfigEntry, BilkaToGoCoordinator, BilkaToGoData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BilkaToGoSensorDescription(SensorEntityDescription):
    value_fn: Callable[[BilkaToGoData], StateType | datetime]
    attributes_fn: Callable[[BilkaToGoData], Mapping[str, Any] | None] = lambda _: None


SENSORS: tuple[BilkaToGoSensorDescription, ...] = (
    BilkaToGoSensorDescription(
        key="order_status",
        translation_key="order_status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in OrderStatus],
        value_fn=lambda data: data.order.status.value if data.order else None,
        attributes_fn=lambda data: {"status_code": data.order.status_code} if data.order else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BilkaToGoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(BilkaToGoSensor(entry.runtime_data, description) for description in SENSORS)


class BilkaToGoSensor(CoordinatorEntity[BilkaToGoCoordinator], SensorEntity):
    entity_description: BilkaToGoSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: BilkaToGoCoordinator, description: BilkaToGoSensorDescription
    ) -> None:
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

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return self.entity_description.attributes_fn(self.coordinator.data)
