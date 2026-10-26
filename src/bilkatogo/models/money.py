from decimal import Decimal
from typing import Any


def kroner(ore: Any) -> Decimal:
    return Decimal(int(ore or 0)).scaleb(-2)
