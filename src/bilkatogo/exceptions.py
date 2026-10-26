class BilkaToGoError(Exception):
    """Base class for all errors raised by the bilkatogo client."""


class InvalidCredentialsError(BilkaToGoError):
    """Bilka rejected the email or password. Ask the user for new credentials."""


class BilkaUnreachableError(BilkaToGoError):
    """Bilka could not be reached (connection error or timeout). Retry later."""


class UnknownPickupPointError(BilkaToGoError):
    """No Pickup Point has the given name."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown Pickup Point {name!r}")
        self.name = name


class CartChangeRejectedError(BilkaToGoError):
    """Bilka applied a different quantity than asked to a Cart Line; the message is Bilka's."""

    def __init__(self, message: str, article_number: str, requested: int, applied: int) -> None:
        super().__init__(message)
        self.article_number = article_number
        self.requested = requested
        self.applied = applied


class UnexpectedResponseError(BilkaToGoError):
    """Bilka answered with something the client does not understand. Retry later."""
