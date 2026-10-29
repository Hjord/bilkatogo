from importlib.metadata import PackageNotFoundError, version

from .client import BilkaToGoClient
from .const import CURRENT_ORDER_SCAN_LIMIT, REQUEST_TIMEOUT_SECONDS
from .exceptions import (
    BilkaToGoError,
    BilkaUnreachableError,
    CartChangeRejectedError,
    InvalidCredentialsError,
    NoPickupPointError,
    UnexpectedResponseError,
    UnknownPickupPointError,
)
from .models import (
    FINISHED_STATUSES,
    Cart,
    CartLine,
    MissingItem,
    Offer,
    Order,
    OrderDetails,
    OrderLine,
    OrderStatus,
    PickupCode,
    PickupPoint,
    PickupSlot,
    Product,
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
    "Cart",
    "CartChangeRejectedError",
    "CartLine",
    "FileTokenStorage",
    "InvalidCredentialsError",
    "MissingItem",
    "NoPickupPointError",
    "Offer",
    "Order",
    "OrderDetails",
    "OrderLine",
    "OrderStatus",
    "PickupCode",
    "PickupPoint",
    "PickupSlot",
    "Product",
    "REQUEST_TIMEOUT_SECONDS",
    "Substitution",
    "TokenStorage",
    "UnexpectedResponseError",
    "UnknownPickupPointError",
    "__version__",
    "current_order",
]
