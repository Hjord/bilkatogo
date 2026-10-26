import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .base import BilkaDataClass
from .money import discount, kroner
from .order import OrderStatus, PickupPoint, PickupSlot


@dataclass
class PickupCode(BilkaDataClass):
    code: str
    _raw: dict[str, Any] | None = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PickupCode | None:
        code = data.get("order_pickup_code")
        if not code:
            return None
        return cls(_raw={"order_pickup_code": code}, code=str(code))


_LOGGER = logging.getLogger(__name__)

SUBSTITUTED_TAGLINE = "erstattet"


@dataclass
class Substitution(BilkaDataClass):
    original_product: str
    replacement_product: str
    quantity: int
    _raw: dict[str, Any] | None = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Substitution | None:
        if not data.get("strikethrough") or data.get("tagline") != SUBSTITUTED_TAGLINE:
            return None
        children = data.get("children") or []
        if not children:
            return None
        replacement = children[0]
        return cls(
            _raw=data,
            original_product=_product_name(data),
            replacement_product=_product_name(replacement),
            quantity=int(replacement.get("quantity") or 0),
        )


@dataclass
class MissingItem(BilkaDataClass):
    product: str
    article_number: str
    ordered_quantity: int
    missing_quantity: int
    _raw: dict[str, Any] | None = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MissingItem | None:
        if not data.get("unavailable_reason") or data.get("replacement") or data.get("children"):
            return None
        if Substitution.from_dict(data) is not None:
            return None
        ordered = int(data.get("quantity") or 0)
        missing = _quantity(data.get("unavailable_quantity"))
        return cls(
            _raw=data,
            product=_product_name(data),
            article_number=str((data.get("product") or {}).get("objectID") or ""),
            ordered_quantity=ordered,
            missing_quantity=missing if 0 < missing < ordered else ordered,
        )


@dataclass
class OrderLine(BilkaDataClass):
    category: str
    product_id: int | None
    name: str
    quantity: int
    amount: Decimal
    substituted: bool
    unavailable_reason: str
    _raw: dict[str, Any] | None = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any], category: str = "") -> OrderLine:
        product_id = (data.get("product") or {}).get("objectID")
        return cls(
            _raw=data,
            category=category,
            product_id=int(product_id) if product_id is not None else None,
            name=_product_name(data),
            quantity=int(data.get("quantity") or 0),
            amount=kroner(data.get("amount")),
            substituted=Substitution.from_dict(data) is not None,
            unavailable_reason=data.get("unavailable_reason") or "",
        )


@dataclass
class OrderDetails(BilkaDataClass):
    order_number: str
    status: OrderStatus
    status_code: str
    pickup_slot: PickupSlot | None
    pickup_point: PickupPoint | None
    home_delivery: bool
    pickup_code: PickupCode | None
    order_total: Decimal
    ordered_total: Decimal | None
    deposit: Decimal
    service_fee: Decimal
    packaging: Decimal
    delivery_fee: Decimal
    discount: Decimal
    lines: list[OrderLine]
    substitutions: list[Substitution]
    missing_items: list[MissingItem]
    _raw: dict[str, Any] | None = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any], ordered_total: Decimal | None = None) -> OrderDetails:
        status_code = data.get("status") or ""
        address = data.get("deliveryAddress")
        stat = data.get("stat") or {}
        raw_lines = [
            (group.get("headline") or "", line)
            for group in data.get("lines") or []
            for block in group.get("lines") or []
            for line in block.get("orderlines") or []
        ]
        lines = [OrderLine.from_dict(line, category) for category, line in raw_lines]
        order_number = str(data["orderId"])
        for line in lines:
            if line.unavailable_reason and not line.substituted:
                _LOGGER.warning(
                    "Order %s: %s is unavailable (%s) and not substituted: %s",
                    order_number,
                    line.name,
                    line.unavailable_reason,
                    json.dumps(line._raw, ensure_ascii=False, default=str),
                )
        return cls(
            _raw=data,
            order_number=order_number,
            status=OrderStatus.from_code(status_code),
            status_code=status_code,
            pickup_slot=PickupSlot.from_dict(data),
            pickup_point=PickupPoint.from_order(address) if address else None,
            home_delivery=bool((address or {}).get("home_delivery", False)),
            pickup_code=PickupCode.from_dict(address or {}),
            order_total=kroner(data.get("price")),
            ordered_total=ordered_total,
            deposit=kroner(stat.get("deposit")),
            service_fee=kroner(stat.get("packing")),
            packaging=kroner(stat.get("packaging_price")),
            delivery_fee=kroner(stat.get("delivery_price")),
            discount=discount(stat),
            lines=lines,
            substitutions=[
                substitution
                for _, line in raw_lines
                if (substitution := Substitution.from_dict(line)) is not None
            ],
            missing_items=[
                item for _, line in raw_lines if (item := MissingItem.from_dict(line)) is not None
            ],
        )


def _product_name(data: dict[str, Any]) -> str:
    return (data.get("product") or {}).get("name") or ""


def _quantity(value: Any) -> int:
    try:
        return int(value or 0)
    except TypeError, ValueError:
        return 0
