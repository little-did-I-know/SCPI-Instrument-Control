"""Custom exception classes for Siglent oscilloscope control."""

from typing import Any


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


class MeasurementUnavailableError(CommandError):
    """Raised when the instrument has no value for a measurement right now.

    Distinct from a failed read: the wire worked and the instrument answered,
    it simply has nothing to report for that item yet. A modern Siglent says
    so with the literal "****" (measured on an SDS824X HD: MEAN answered
    while PKPK/MAX/MIN returned "****" on the same live channel).

    Deliberately a CommandError subclass so callers written before it existed
    keep catching it, while callers that care can tell "not available yet"
    apart from "the read is broken" -- the difference between a normal
    transient and something worth alerting on.
    """

    pass


class InvalidParameterError(SiglentError):
    """Raised when invalid parameters are provided."""

    pass


class FeatureNotSupportedError(SiglentError):
    """Raised when an operation is not supported by the connected instrument's dialect."""

    pass


class FrequencySweepError(SiglentError):
    """A frequency sweep stopped early; `partial` holds what it had measured.

    Raising bare would throw away every point already captured, which on real
    hardware can be an hour of bench time. The partial result travels with the
    exception so a caller can save or inspect it.
    """

    def __init__(self, message: str, partial: Any = None) -> None:
        super().__init__(message)
        self.partial = partial


# Backward compatibility aliases (deprecated in 0.3.0)
# These will be removed in a future version
ConnectionError = SiglentConnectionError
TimeoutError = SiglentTimeoutError
