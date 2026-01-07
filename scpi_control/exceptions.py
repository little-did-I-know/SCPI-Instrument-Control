"""Custom exception classes for Siglent oscilloscope control."""


class SiglentError(Exception):
    """Base exception class for all Siglent-related errors."""

    pass


class SiglentConnectionError(SiglentError):
    """Raised when connection to oscilloscope fails or is lost."""

    pass


class SiglentTimeoutError(SiglentError):
    """Raised when a command times out."""

    pass


class CommandError(SiglentError):
    """Raised when a SCPI command fails or returns an error."""

    pass


class InvalidParameterError(SiglentError):
    """Raised when invalid parameters are provided."""

    pass


# Backward compatibility aliases (deprecated in 0.3.0)
# These will be removed in a future version
ConnectionError = SiglentConnectionError
TimeoutError = SiglentTimeoutError
