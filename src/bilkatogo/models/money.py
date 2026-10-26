from decimal import Decimal
from typing import Any


def kroner(ore: Any) -> Decimal:
    return Decimal(int(ore or 0)).scaleb(-2)


DISCOUNT_KEYS = ("promo", "membership_offer_discount", "personalized_offer_discount")


def discount(stat: dict[str, Any]) -> Decimal:
    return kroner(
        sum(int(stat.get(key) or 0) for key in DISCOUNT_KEYS)
        + sum(int(voucher.get("amount") or 0) for voucher in stat.get("vouchers") or [])
    )
