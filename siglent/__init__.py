"""Siglent Oscilloscope Control Package

This package provides programmatic control for Siglent oscilloscopes and power supplies
via Ethernet/LAN connection.

For high-level automation and data collection, see the automation module:
    from siglent.automation import DataCollector, TriggerWaitCollector

For power supply control:
    from siglent import PowerSupply

For automated test report generation:
    from siglent.report_generator import ReportGenerator
"""

__version__ = "0.5.0"

from siglent.exceptions import CommandError, SiglentConnectionError, SiglentError, SiglentTimeoutError
from siglent.oscilloscope import Oscilloscope

# Power supply support (stable as of v0.5.0)
from siglent.power_supply import PowerSupply
from siglent.psu_data_logger import PSUDataLogger, TimedPSULogger

__all__ = [
    # Core features
    "Oscilloscope",
    "SiglentError",
    "SiglentConnectionError",
    "SiglentTimeoutError",
    "CommandError",
    # Power supply features
    "PowerSupply",
    "PSUDataLogger",
    "TimedPSULogger",
]
