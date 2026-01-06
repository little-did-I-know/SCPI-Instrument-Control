"""SCPI Instrument Control Package

This package provides programmatic control for SCPI-compatible test equipment
via Ethernet/LAN connection.

Supported equipment:
- Oscilloscopes (Siglent SDS series and SCPI-compatible models)
- Function Generators / AWGs (Siglent SDG series and SCPI-compatible models)
- Power Supplies (Siglent SPD series and SCPI-compatible models)

For high-level automation and data collection, see the automation module:
    from scpi_control.automation import DataCollector, TriggerWaitCollector

For power supply control:
    from scpi_control import PowerSupply

For function generator control:
    from scpi_control import FunctionGenerator

For automated test report generation:
    from scpi_control.report_generator import ReportGenerator
"""

__version__ = "1.0.0"

from scpi_control.exceptions import CommandError, SiglentConnectionError, SiglentError, SiglentTimeoutError
from scpi_control.oscilloscope import Oscilloscope

# Power supply support (stable as of v0.5.0)
from scpi_control.power_supply import PowerSupply
from scpi_control.psu_data_logger import PSUDataLogger, TimedPSULogger

# Function generator support (new in v0.6.0, stable in v1.0.0)
from scpi_control.function_generator import FunctionGenerator

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
    # Function generator features
    "FunctionGenerator",
]
