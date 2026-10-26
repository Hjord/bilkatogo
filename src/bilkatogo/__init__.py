from importlib.metadata import PackageNotFoundError, version

from .client import BilkaToGoClient
from .exceptions import BilkaToGoError, InvalidCredentialsError
from .models import (
    Order,
    OrderDetails,
    OrderLine,
    OrderStatus,
    PickupCode,
    PickupPoint,
    PickupSlot,
    Substitution,
)
from .token_storage import FileTokenStorage, TokenStorage

try:
    __version__ = version("bilkatogo")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "BilkaToGoClient",
    "BilkaToGoError",
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
    "__version__",
]
