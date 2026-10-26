class BilkaToGoError(Exception):
    """Base class for all errors raised by the bilkatogo client."""


class InvalidCredentialsError(BilkaToGoError):
    """Bilka rejected the email or password. Ask the user for new credentials."""
