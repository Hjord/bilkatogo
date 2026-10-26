from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from .base import BilkaDataClass
from .money import kroner


@dataclass
class Offer(BilkaDataClass):
    label: str
    price: Decimal
    unit_price: Decimal | None
    ends: date | None
    limit_per_customer: int | None


@dataclass
class Product(BilkaDataClass):
    article_number: str
    name: str
    brand: str
    store_id: str
    price: Decimal
    unit_price: Decimal | None
    unit: str | None
    in_stock: bool
    offer: Offer | None
    multibuy_offer: str | None
    _raw: dict[str, Any] | None = field(default=None, repr=False)

    @classmethod
    def from_hit(cls, hit: dict[str, Any], store_id: str) -> Product | None:
        store = (hit.get("storeData") or {}).get(store_id)
        if not store:
            return None
        unit = (store.get("unitsOfMeasurePriceUnit") or "").rstrip(".").lower()
        label = store.get("offerDescription") or ""
        multibuy = bool(store.get("multipromo"))
        offer = None
        if label and not multibuy:
            offer = Offer(
                label=label,
                price=kroner(store.get("price")),
                unit_price=kroner(store.get("unitsOfMeasureOfferPrice")) if unit else None,
                ends=_date(store.get("offerUntil")),
                limit_per_customer=store.get("offerMax") or None,
            )
        price = store.get("beforePrice") or hit.get("price") if offer else store.get("price")
        return cls(
            _raw=hit,
            article_number=str(hit["article"]),
            name=hit.get("name") or "",
            brand=hit.get("brand") or "",
            store_id=store_id,
            price=kroner(price),
            unit_price=kroner(store.get("unitsOfMeasurePrice")) if unit else None,
            unit=unit or None,
            in_stock=bool(store.get("inStock")),
            offer=offer,
            multibuy_offer=label if multibuy and label else None,
        )


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None
