class BilkaToGoError(Exception):
    """Base class for all errors raised by the bilkatogo client."""


class InvalidCredentialsError(BilkaToGoError):
    """Bilka rejected the email or password. Ask the user for new credentials."""


class BilkaUnreachableError(BilkaToGoError):
    """Bilka could not be reached (connection error or timeout). Retry later."""


class UnexpectedResponseError(BilkaToGoError):
    """Bilka answered with something the client does not understand. Retry later."""
