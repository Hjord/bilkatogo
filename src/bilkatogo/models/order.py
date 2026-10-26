from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from enum import StrEnum
from typing import Any

from ..const import BILKA_TIME_ZONE
from .base import BilkaDataClass


class OrderStatus(StrEnum):
    PROCESSING = "processing"
    RECEIVED = "received"
    PACKED = "packed"
    PICKED_UP = "picked_up"
    NOT_COLLECTED = "not_collected"
    CANCELLED = "cancelled"
    SOLD_OUT = "sold_out"
    UNKNOWN = "unknown"

    @classmethod
    def from_code(cls, code: str) -> OrderStatus:
        return _STATUS_BY_CODE.get(code.strip().replace(" ", "_").upper(), cls.UNKNOWN)


_STATUS_BY_CODE = {
    "UBEHANDLET": OrderStatus.PROCESSING,
    "CAPTURE_IGANG": OrderStatus.PROCESSING,
    "BESTILT": OrderStatus.RECEIVED,
    "PAKKET": OrderStatus.PACKED,
    "LEVERET": OrderStatus.PICKED_UP,
    "FAKTURERET": OrderStatus.PICKED_UP,
    "UAFHENTET": OrderStatus.NOT_COLLECTED,
    "ANNULLERET": OrderStatus.CANCELLED,
    "FULDT_UDSOLGT": OrderStatus.SOLD_OUT,
}


@dataclass
class PickupSlot(BilkaDataClass):
    date: date
    start: time
    end: time
    _raw: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def starts_at(self) -> datetime:
        return datetime.combine(self.date, self.start, BILKA_TIME_ZONE)

    @property
    def ends_at(self) -> datetime:
        return datetime.combine(self.date, self.end, BILKA_TIME_ZONE)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PickupSlot | None:
        interval = data.get("deliveryInterval") or {}
        try:
            return cls(
                _raw={"deliveryDate": data.get("deliveryDate"), "deliveryInterval": interval},
                date=date.fromisoformat(data["deliveryDate"]),
                start=time.fromisoformat(interval["start"]),
                end=time.fromisoformat(interval["end"]),
            )
        except KeyError, TypeError, ValueError:
            return None


@dataclass
class PickupPoint(BilkaDataClass):
    name: str
    address: str
    zip_code: str
    city: str
    _raw: dict[str, Any] | None = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PickupPoint:
        return cls(
            _raw=data,
            name=data.get("location") or "",
            address=data.get("address") or "",
            zip_code=str(data.get("zipCode") or ""),
            city=data.get("city") or "",
        )


@dataclass
class Order(BilkaDataClass):
    order_number: str
    status: OrderStatus
    status_code: str
    ordered_at: datetime | None
    pickup_slot: PickupSlot | None
    pickup_point: PickupPoint | None
    home_delivery: bool
    delivered: bool
    ordered_price: int
    packed_price: int
    content: str
    _raw: dict[str, Any] | None = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Order:
        status_code = data.get("status") or ""
        pickupzone = data.get("pickupzone")
        return cls(
            _raw=data,
            order_number=str(data["orderId"]),
            status=OrderStatus.from_code(status_code),
            status_code=status_code,
            ordered_at=_ordered_at(data.get("ordered")),
            pickup_slot=PickupSlot.from_dict(data),
            pickup_point=PickupPoint.from_dict(pickupzone) if pickupzone else None,
            home_delivery=bool((pickupzone or {}).get("home_delivery", False)),
            delivered=bool(data.get("delivered", False)),
            ordered_price=int(data.get("orderedPrice") or 0),
            packed_price=int(data.get("packedPrice") or 0),
            content=data.get("content") or "",
        )


def _ordered_at(ordered: dict[str, Any] | None) -> datetime | None:
    if not ordered:
        return None
    try:
        return datetime.fromisoformat(f"{ordered['date']}T{ordered.get('time') or '00:00:00'}")
    except KeyError, TypeError, ValueError:
        return None


FINISHED_STATUSES = frozenset(
    {OrderStatus.PICKED_UP, OrderStatus.NOT_COLLECTED, OrderStatus.CANCELLED, OrderStatus.SOLD_OUT}
)


def current_order(orders: Iterable[Order]) -> Order | None:
    history = list(orders)
    unfinished = [order for order in history if order.status not in FINISHED_STATUSES]
    if unfinished:
        return min(unfinished, key=lambda order: _slot_start(order, _LATEST))
    if not history:
        return None
    return max(history, key=lambda order: _slot_start(order, _EARLIEST))


_EARLIEST = datetime.min.replace(tzinfo=UTC)
_LATEST = datetime.max.replace(tzinfo=UTC)


def _slot_start(order: Order, missing: datetime) -> datetime:
    return order.pickup_slot.starts_at if order.pickup_slot else missing
