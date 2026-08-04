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
    """Raised when a SCPI command fails or returns an error.

    Optional structured context (all default to None): `command` is the string
    actually sent on the wire, `dialect`/`model` identify the instrument, and
    `instrument_error` carries the instrument's own error-queue text where the
    failing path already read it.
    """

    def __init__(self, message="", *, command=None, dialect=None, model=None, instrument_error=None):
        self.command = command
        self.dialect = dialect
        self.model = model
        self.instrument_error = instrument_error
        super().__init__(message)


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


class InvalidParameterError(SiglentError, ValueError):
    """Raised when invalid parameters are provided.

    Also a ValueError: validation paths that historically raised bare
    ValueError now raise this class, and pre-existing `except ValueError`
    callers must keep catching it.
    """

    def __init__(self, message=None, *, parameter=None, value=None, valid_options=None, dialect=None, model=None):
        self.parameter = parameter
        self.value = value
        self.valid_options = sorted(valid_options) if valid_options is not None else None
        self.dialect = dialect
        self.model = model
        if message is None:
            parts = [f"Invalid {parameter or 'parameter'}: {value!r}."]
            if self.valid_options:
                parts.append(f"Valid: {', '.join(str(v) for v in self.valid_options)}.")
            context = ", ".join(p for p in (dialect, model) if p)
            if context:
                parts.append(f"({context})")
            message = " ".join(parts)
        super().__init__(message)


class FeatureNotSupportedError(SiglentError, NotImplementedError):
    """Raised when an operation is not supported by the connected instrument.

    Also a NotImplementedError: the PSU capability gates historically raised
    bare NotImplementedError, and pre-existing `except NotImplementedError`
    callers must keep catching them. (Same dual-base rationale as
    InvalidParameterError, which is also a ValueError.)
    """

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
