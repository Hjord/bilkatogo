from importlib.metadata import PackageNotFoundError, version

from .client import BilkaToGoClient
from .exceptions import (
    BilkaToGoError,
    BilkaUnreachableError,
    InvalidCredentialsError,
    UnexpectedResponseError,
)
from .models import Order, OrderStatus, PickupPoint, PickupSlot
from .token_storage import FileTokenStorage, TokenStorage

try:
    __version__ = version("bilkatogo")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "BilkaToGoClient",
    "BilkaToGoError",
    "BilkaUnreachableError",
    "FileTokenStorage",
    "InvalidCredentialsError",
    "Order",
    "OrderStatus",
    "PickupPoint",
    "PickupSlot",
    "TokenStorage",
    "UnexpectedResponseError",
    "__version__",
]
