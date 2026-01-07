"""Backward compatibility module for the 'siglent' package name.

DEPRECATED: This module provides backward compatibility for code using 'import siglent'.

The package has been renamed to 'scpi_control' to better reflect its capabilities:
- SCPI Instrument Control (scpi_control) supports oscilloscopes, power supplies,
  and function generators from Siglent and other SCPI-compatible manufacturers.

Migration Guide:
    Old import (deprecated):
        from siglent import Oscilloscope, PowerSupply, FunctionGenerator

    New import (recommended):
        from scpi_control import Oscilloscope, PowerSupply, FunctionGenerator

This compatibility module will be removed in v2.0.0.
For more information, see: https://github.com/little-did-I-know/SCPI-Instrument-Control
"""

import warnings

warnings.warn(
    "The 'siglent' package name is deprecated and will be removed in v2.0.0.\n"
    "Please update your imports to use 'scpi_control' instead:\n\n"
    "  Old: from siglent import Oscilloscope, PowerSupply, FunctionGenerator\n"
    "  New: from scpi_control import Oscilloscope, PowerSupply, FunctionGenerator\n\n"
    "PyPI package name: pip install SCPI-Instrument-Control\n"
    "See migration guide: https://github.com/little-did-I-know/SCPI-Instrument-Control",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new package for backward compatibility
from scpi_control import *  # noqa: F401, F403
from scpi_control import __version__, __all__  # noqa: F401
