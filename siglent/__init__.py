"""Siglent Oscilloscope Control Package

This package provides programmatic control for Siglent oscilloscopes and power supplies
via Ethernet/LAN connection.

For high-level automation and data collection, see the automation module:
    from siglent.automation import DataCollector, TriggerWaitCollector

For power supply control (EXPERIMENTAL - v0.4.0-beta.1):
    # ⚠️ Power supply support is experimental and may change
    # Install: pip install "Siglent-Oscilloscope[power-supply-beta]"
    from siglent import PowerSupply
"""

__version__ = "0.4.0-beta.1"

from siglent.exceptions import (
    CommandError,
    SiglentConnectionError,
    SiglentError,
    SiglentTimeoutError,
)
from siglent.oscilloscope import Oscilloscope

# Experimental features (v0.4.0-beta.1)
# These modules are experimental and may change in future releases
from siglent.power_supply import PowerSupply
from siglent.psu_data_logger import PSUDataLogger, TimedPSULogger

__all__ = [
    # Stable core features
    "Oscilloscope",
    "SiglentError",
    "SiglentConnectionError",
    "SiglentTimeoutError",
    "CommandError",
    # Experimental features (v0.4.0-beta.1)
    "PowerSupply",
    "PSUDataLogger",
    "TimedPSULogger",
]
