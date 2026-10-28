from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from bilkatogo import Order, OrderStatus, PickupSlot

from .const import DOMAIN
from .coordinator import BilkaToGoConfigEntry
from .entity import BilkaToGoEntity, status_option

PARALLEL_UPDATES = 0

PICKUP_SLOTS = EntityDescription(key="pickup_slots", translation_key="pickup_slots")

LEFT_OUT_STATUSES = frozenset({OrderStatus.CANCELLED, OrderStatus.SOLD_OUT})

TRANSLATIONS = f"component.{DOMAIN}.entity"
ATTRIBUTES = f"{TRANSLATIONS}.calendar.pickup_slots.state_attributes"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BilkaToGoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([BilkaToGoCalendar(entry.runtime_data, PICKUP_SLOTS)])


class BilkaToGoCalendar(BilkaToGoEntity, CalendarEntity):
    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        return next((event for event in self._events() if event.end > now), None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [
            event for event in self._events() if event.end > start_date and event.start < end_date
        ]

    def _events(self) -> list[CalendarEvent]:
        events = [
            self._event(order, order.pickup_slot)
            for order in self.coordinator.data.orders
            if order.pickup_slot is not None and order.status not in LEFT_OUT_STATUSES
        ]
        return sorted(events, key=lambda event: event.start_datetime_local)

    def _event(self, order: Order, slot: PickupSlot) -> CalendarEvent:
        kind = "delivery" if order.home_delivery else "pickup"
        order_number = self._translate(
            f"{TRANSLATIONS}.sensor.order_total.state_attributes.order_number.name"
        )
        status_label = self._translate(f"{TRANSLATIONS}.sensor.order_status.name")
        status = self._translate(
            f"{TRANSLATIONS}.sensor.order_status.state.{status_option(order.status)}"
        )
        return CalendarEvent(
            start=slot.starts_at,
            end=slot.ends_at,
            summary=self._translate(f"{ATTRIBUTES}.message.state.{kind}"),
            description=f"{order_number}: {order.order_number}\n{status_label}: {status}",
            location=None if order.home_delivery else self._pickup_point_name(order),
            uid=order.order_number,
        )

    @staticmethod
    def _pickup_point_name(order: Order) -> str | None:
        return order.pickup_point.name if order.pickup_point else None

    def _translate(self, key: str) -> str:
        return self.platform_data.platform_translations.get(
            key, self.platform_data.default_language_platform_translations.get(key, key)
        )
