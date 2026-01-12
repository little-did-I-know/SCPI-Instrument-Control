"""Backward compatibility module for siglent.exceptions.

DEPRECATED: This module provides backward compatibility for code using
'from siglent.exceptions import ...'. Please update imports to use
'from scpi_control.exceptions import ...' instead.

This compatibility module will be removed in v2.0.0.
"""

import warnings

warnings.warn(
    "The 'siglent.exceptions' module is deprecated and will be removed in v2.0.0.\n"
    "Please update your imports to use 'scpi_control.exceptions' instead:\n\n"
    "  Old: from siglent.exceptions import SiglentError\n"
    "  New: from scpi_control.exceptions import SiglentError",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new package for backward compatibility
from scpi_control.exceptions import (  # noqa: F401, E402
    CommandError,
    ConnectionError,
    InvalidParameterError,
    SiglentConnectionError,
    SiglentError,
    SiglentTimeoutError,
    TimeoutError,
)

__all__ = [
    "SiglentError",
    "SiglentConnectionError",
    "SiglentTimeoutError",
    "CommandError",
    "InvalidParameterError",
    "ConnectionError",
    "TimeoutError",
]
