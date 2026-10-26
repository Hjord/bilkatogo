from importlib.metadata import PackageNotFoundError, version

from .client import BilkaToGoClient
from .const import CURRENT_ORDER_SCAN_LIMIT
from .exceptions import (
    BilkaToGoError,
    BilkaUnreachableError,
    InvalidCredentialsError,
    UnexpectedResponseError,
)
from .models import (
    FINISHED_STATUSES,
    Order,
    OrderDetails,
    OrderLine,
    OrderStatus,
    PickupCode,
    PickupPoint,
    PickupSlot,
    Substitution,
    current_order,
)
from .token_storage import FileTokenStorage, TokenStorage

try:
    __version__ = version("bilkatogo")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "CURRENT_ORDER_SCAN_LIMIT",
    "FINISHED_STATUSES",
    "BilkaToGoClient",
    "BilkaToGoError",
    "BilkaUnreachableError",
    "FileTokenStorage",
    "InvalidCredentialsError",
    "Order",
    "OrderDetails",
    "OrderLine",
    "OrderStatus",
    "PickupCode",
    "PickupPoint",
    "PickupSlot",
    "Substitution",
    "TokenStorage",
    "UnexpectedResponseError",
    "__version__",
    "current_order",
]
