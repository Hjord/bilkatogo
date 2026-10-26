from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
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

from bilkatogo import Order, OrderStatus

from .announcer import missing_item_data, substitution_data
from .const import CURRENCY, DOMAIN
from .coordinator import BilkaToGoConfigEntry, BilkaToGoCoordinator, BilkaToGoData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BilkaToGoSensorDescription(SensorEntityDescription):
    value_fn: Callable[[BilkaToGoData], StateType | datetime]
    attributes_fn: Callable[[BilkaToGoData], Mapping[str, Any] | None] = lambda _: None


def _slot_time(order: Order | None, *, start: bool) -> datetime | None:
    slot = order.pickup_slot if order else None
    if slot is None:
        return None
    return slot.starts_at if start else slot.ends_at


UNRECOGNIZED_STATUS = "unrecognized"


def _status_option(status: OrderStatus) -> str:
    return UNRECOGNIZED_STATUS if status is OrderStatus.UNKNOWN else status.value


def _order_price(order: Order) -> Decimal:
    return order.packed_price or order.ordered_price


def _order_attributes(data: BilkaToGoData) -> dict[str, Any] | None:
    order = data.order
    if order is None:
        return None
    return {"order_number": order.order_number, "order_total": float(_order_price(order))}


def _slot_attributes(data: BilkaToGoData) -> dict[str, Any] | None:
    attributes = _order_attributes(data)
    if attributes is None:
        return None
    end = _slot_time(data.order, start=False)
    return attributes | {"pickup_slot_end": end.isoformat() if end else None}


def _order_total(data: BilkaToGoData) -> Decimal | None:
    if data.details:
        return data.details.order_total
    if data.order:
        return _order_price(data.order)
    return None


def _order_total_attributes(data: BilkaToGoData) -> dict[str, Any] | None:
    order, details, total = data.order, data.details, _order_total(data)
    if order is None or total is None:
        return None
    attributes = {
        "order_number": order.order_number,
        "ordered_total": float(order.ordered_price),
        "difference": float(total - order.ordered_price),
    }
    if details:
        attributes |= {
            "deposit": float(details.deposit),
            "service_fee": float(details.service_fee),
            "packaging": float(details.packaging),
            "delivery_fee": float(details.delivery_fee),
            "discount": float(details.discount),
        }
    return attributes


SENSORS: tuple[BilkaToGoSensorDescription, ...] = (
    BilkaToGoSensorDescription(
        key="order_status",
        translation_key="order_status",
        device_class=SensorDeviceClass.ENUM,
        options=[_status_option(status) for status in OrderStatus],
        value_fn=lambda data: _status_option(data.order.status) if data.order else None,
        attributes_fn=lambda data: {"status_code": data.order.status_code} if data.order else None,
    ),
    BilkaToGoSensorDescription(
        key="order_total",
        translation_key="order_total",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value_fn=_order_total,
        attributes_fn=_order_total_attributes,
    ),
    BilkaToGoSensorDescription(
        key="pickup_slot",
        translation_key="pickup_slot",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: _slot_time(data.order, start=True),
        attributes_fn=_slot_attributes,
    ),
    BilkaToGoSensorDescription(
        key="pickup_point",
        translation_key="pickup_point",
        value_fn=lambda data: (
            data.order.pickup_point.name if data.order and data.order.pickup_point else None
        ),
        attributes_fn=_order_attributes,
    ),
    BilkaToGoSensorDescription(
        key="pickup_code",
        translation_key="pickup_code",
        value_fn=lambda data: (
            data.details.pickup_code.code if data.details and data.details.pickup_code else None
        ),
        attributes_fn=_order_attributes,
    ),
    BilkaToGoSensorDescription(
        key="substitutions",
        translation_key="substitutions",
        value_fn=lambda data: len(data.details.substitutions) if data.details else None,
        attributes_fn=lambda data: (
            {
                "substitutions": [
                    substitution_data(substitution) for substitution in data.details.substitutions
                ]
            }
            if data.details
            else None
        ),
    ),
    BilkaToGoSensorDescription(
        key="missing_items",
        translation_key="missing_items",
        value_fn=lambda data: len(data.details.missing_items) if data.details else None,
        attributes_fn=lambda data: (
            {"missing_items": [missing_item_data(item) for item in data.details.missing_items]}
            if data.details
            else None
        ),
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
