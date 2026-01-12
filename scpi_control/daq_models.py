"""Model capability definitions for SCPI-controlled Data Acquisition systems.

Supports generic SCPI-99 DAQ/Data Loggers and Keysight 34970A/DAQ970A series models.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class MeasurementFunction(Enum):
    """Supported measurement functions for DAQ channels."""

    VOLTAGE_DC = "VOLT:DC"
    VOLTAGE_AC = "VOLT:AC"
    CURRENT_DC = "CURR:DC"
    CURRENT_AC = "CURR:AC"
    RESISTANCE_2W = "RES"  # 2-wire resistance
    RESISTANCE_4W = "FRES"  # 4-wire (Fresistance)
    FREQUENCY = "FREQ"
    PERIOD = "PER"
    TEMPERATURE = "TEMP"  # Thermocouple, RTD, thermistor
    CONTINUITY = "CONT"
    DIODE = "DIOD"
    DIGITAL_INPUT = "DIG:INP"
    DIGITAL_OUTPUT = "DIG:OUTP"
    TOTALIZER = "TOT"  # Counter/totalizer


@dataclass
class ModuleSpec:
    """Specification for a DAQ plug-in module/card."""

    slot: int  # Slot number (1, 2, 3, etc.)
    module_type: str  # Module type identifier (e.g., "34901A", "DAQM901A")
    num_channels: int  # Number of channels on this module
    channel_start: int  # Starting channel number (e.g., 101 for slot 1)
    supported_functions: List[MeasurementFunction]  # Supported measurement types
    max_voltage: float = 300.0  # Maximum input voltage
    max_current: float = 1.0  # Maximum input current (if applicable)
    has_switching: bool = True  # Multiplexer/switching capability
    description: str = ""  # Human-readable description

    def __str__(self) -> str:
        """String representation of module spec."""
        return f"Slot {self.slot}: {self.module_type} ({self.num_channels}ch, {self.channel_start}-{self.channel_start + self.num_channels - 1})"

    def get_channel_list(self) -> List[int]:
        """Get list of all channel numbers for this module."""
        return list(range(self.channel_start, self.channel_start + self.num_channels))


@dataclass
class DAQCapability:
    """Defines capabilities and features for a specific DAQ model.

    This dataclass contains all model-specific information including hardware
    specifications and supported features.
    """

    model_name: str  # Full model name (e.g., "34970A", "DAQ970A")
    manufacturer: str  # Manufacturer name (e.g., "Keysight", "Agilent")
    num_slots: int  # Number of module slots
    modules: List[ModuleSpec] = field(default_factory=list)  # Installed modules
    has_internal_dmm: bool = True  # Built-in digital multimeter
    dmm_resolution: float = 6.5  # DMM resolution in digits
    max_sample_rate: float = 250.0  # Maximum scan rate (channels/second)
    memory_readings: int = 50000  # Reading memory capacity
    has_timestamp: bool = True  # Timestamp capability
    has_alarm: bool = True  # Alarm/limit checking
    has_math: bool = True  # Math functions (mx+b scaling)
    scpi_variant: str = "generic"  # SCPI command variant

    def __str__(self) -> str:
        """String representation of DAQ capability."""
        return f"{self.manufacturer} {self.model_name} ({self.num_slots} slots, {self.scpi_variant})"

    @property
    def total_channels(self) -> int:
        """Get total number of channels across all modules."""
        return sum(m.num_channels for m in self.modules)

    def get_all_channels(self) -> List[int]:
        """Get list of all channel numbers across all modules."""
        channels = []
        for module in self.modules:
            channels.extend(module.get_channel_list())
        return sorted(channels)


# Common module types
MULTIPLEXER_20CH = lambda slot: ModuleSpec(
    slot=slot,
    module_type="34901A",
    num_channels=20,
    channel_start=slot * 100 + 1,
    supported_functions=[
        MeasurementFunction.VOLTAGE_DC,
        MeasurementFunction.VOLTAGE_AC,
        MeasurementFunction.CURRENT_DC,
        MeasurementFunction.CURRENT_AC,
        MeasurementFunction.RESISTANCE_2W,
        MeasurementFunction.RESISTANCE_4W,
        MeasurementFunction.FREQUENCY,
        MeasurementFunction.PERIOD,
        MeasurementFunction.TEMPERATURE,
    ],
    max_voltage=300.0,
    description="20-Channel Multiplexer (2/4-wire)",
)

MULTIPLEXER_40CH = lambda slot: ModuleSpec(
    slot=slot,
    module_type="34902A",
    num_channels=16,
    channel_start=slot * 100 + 1,
    supported_functions=[
        MeasurementFunction.VOLTAGE_DC,
        MeasurementFunction.VOLTAGE_AC,
        MeasurementFunction.RESISTANCE_2W,
        MeasurementFunction.FREQUENCY,
        MeasurementFunction.PERIOD,
        MeasurementFunction.TEMPERATURE,
    ],
    max_voltage=300.0,
    description="16-Channel Multiplexer (2-wire only)",
)

DIGITAL_IO_MODULE = lambda slot: ModuleSpec(
    slot=slot,
    module_type="34903A",
    num_channels=20,
    channel_start=slot * 100 + 1,
    supported_functions=[
        MeasurementFunction.DIGITAL_INPUT,
        MeasurementFunction.DIGITAL_OUTPUT,
    ],
    has_switching=True,
    description="20-Channel Actuator/GP Switch",
)


# DAQ Model Registry - Add new models here
DAQ_MODEL_REGISTRY = {
    # Keysight/Agilent 34970A (classic model)
    "34970A": DAQCapability(
        model_name="34970A",
        manufacturer="Keysight",
        num_slots=3,
        modules=[MULTIPLEXER_20CH(1)],  # Default config - can be updated after connection
        has_internal_dmm=True,
        dmm_resolution=6.5,
        max_sample_rate=250.0,
        memory_readings=50000,
        has_timestamp=True,
        has_alarm=True,
        has_math=True,
        scpi_variant="keysight_daq",
    ),
    # Keysight 34972A (USB enabled version)
    "34972A": DAQCapability(
        model_name="34972A",
        manufacturer="Keysight",
        num_slots=3,
        modules=[MULTIPLEXER_20CH(1)],
        has_internal_dmm=True,
        dmm_resolution=6.5,
        max_sample_rate=250.0,
        memory_readings=50000,
        has_timestamp=True,
        has_alarm=True,
        has_math=True,
        scpi_variant="keysight_daq",
    ),
    # Keysight DAQ970A (modern replacement)
    "DAQ970A": DAQCapability(
        model_name="DAQ970A",
        manufacturer="Keysight",
        num_slots=3,
        modules=[MULTIPLEXER_20CH(1)],
        has_internal_dmm=True,
        dmm_resolution=6.5,
        max_sample_rate=450.0,  # Faster scanning
        memory_readings=500000,  # More memory
        has_timestamp=True,
        has_alarm=True,
        has_math=True,
        scpi_variant="keysight_daq",
    ),
    # Keysight DAQ973A (no internal DMM)
    "DAQ973A": DAQCapability(
        model_name="DAQ973A",
        manufacturer="Keysight",
        num_slots=3,
        modules=[],
        has_internal_dmm=False,
        dmm_resolution=0,
        max_sample_rate=450.0,
        memory_readings=500000,
        has_timestamp=True,
        has_alarm=True,
        has_math=False,
        scpi_variant="keysight_daq",
    ),
}


def detect_daq_from_idn(idn_string: str) -> DAQCapability:
    """Detect DAQ model and return its capability profile.

    Args:
        idn_string: The response from *IDN? command
                   Format: "Manufacturer,Model,Serial,Firmware"
                   Example: "Keysight Technologies,34970A,MY12345678,A.01.02"

    Returns:
        DAQCapability object for the detected model

    Note:
        Unknown models will receive a generic SCPI capability profile
        to enable basic control functionality.
    """
    parts = idn_string.split(",")
    if len(parts) < 2:
        logger.warning(f"Invalid *IDN? response format: {idn_string}")
        return create_generic_daq_capability(idn_string)

    manufacturer = parts[0].strip()
    model_from_idn = parts[1].strip()
    logger.info(f"Detecting DAQ model from IDN: {manufacturer}, {model_from_idn}")

    # Try exact match first
    if model_from_idn in DAQ_MODEL_REGISTRY:
        logger.info(f"Exact match found: {model_from_idn}")
        return DAQ_MODEL_REGISTRY[model_from_idn]

    # Try fuzzy matching
    normalized_model = re.sub(r"[\s\-_]", "", model_from_idn).upper()

    for registered_model, capability in DAQ_MODEL_REGISTRY.items():
        normalized_registered = re.sub(r"[\s\-_]", "", registered_model).upper()
        if normalized_model == normalized_registered:
            logger.info(f"Fuzzy match found: {model_from_idn} -> {registered_model}")
            return capability

    # Try partial matching for Keysight/Agilent models
    if any(mfr in manufacturer for mfr in ["Keysight", "Agilent", "HP"]):
        for registered_model, capability in DAQ_MODEL_REGISTRY.items():
            if registered_model in model_from_idn:
                logger.info(f"Partial match found: {model_from_idn} -> {registered_model}")
                return capability

    # Model not found - create generic fallback
    logger.warning(f"Model '{model_from_idn}' not in registry, using generic SCPI profile")
    return create_generic_daq_capability(idn_string)


def create_generic_daq_capability(idn_string: str) -> DAQCapability:
    """Create generic SCPI capability for unknown DAQ.

    Args:
        idn_string: The *IDN? response string

    Returns:
        Generic DAQCapability with conservative defaults
    """
    parts = idn_string.split(",")
    manufacturer = parts[0].strip() if len(parts) > 0 else "Unknown"
    model = parts[1].strip() if len(parts) > 1 else "Generic DAQ"

    logger.info(f"Creating generic DAQ capability for {manufacturer} {model}")

    generic_capability = DAQCapability(
        model_name=model,
        manufacturer=manufacturer,
        num_slots=1,
        modules=[
            ModuleSpec(
                slot=1,
                module_type="Generic",
                num_channels=20,
                channel_start=101,
                supported_functions=[
                    MeasurementFunction.VOLTAGE_DC,
                    MeasurementFunction.VOLTAGE_AC,
                    MeasurementFunction.RESISTANCE_2W,
                ],
                description="Generic Input Module",
            )
        ],
        has_internal_dmm=True,
        dmm_resolution=5.5,
        max_sample_rate=100.0,
        memory_readings=10000,
        has_timestamp=True,
        has_alarm=False,
        has_math=False,
        scpi_variant="generic",
    )

    logger.info(f"Created generic capability: {generic_capability}")
    return generic_capability


def list_supported_models() -> List[str]:
    """Get list of all explicitly supported DAQ model names."""
    return sorted(DAQ_MODEL_REGISTRY.keys())


def get_models_by_manufacturer(manufacturer: str) -> List[DAQCapability]:
    """Get all models from a specific manufacturer."""
    return [cap for cap in DAQ_MODEL_REGISTRY.values() if cap.manufacturer.lower() == manufacturer.lower()]
