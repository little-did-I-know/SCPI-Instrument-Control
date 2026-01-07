"""Model capability definitions for different Siglent oscilloscope series."""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelCapability:
    """Defines capabilities and features for a specific oscilloscope model.

    This dataclass contains all model-specific information including hardware
    specifications and supported features.
    """

    model_name: str  # Full model name (e.g., "SDS824X HD")
    series: str  # Series identifier (e.g., "SDS800XHD", "SDS1000X", "SDS2000XPlus")
    num_channels: int  # Number of analog channels (2 or 4)
    max_sample_rate: float  # Maximum sample rate in GSa/s
    memory_depth: int  # Maximum memory depth in points
    bandwidth_mhz: int  # Analog bandwidth in MHz
    has_math_channels: bool  # Supports math channels
    has_fft: bool  # Supports FFT analysis
    has_protocol_decode: bool  # Supports protocol decode
    supported_decode_types: List[str]  # Supported protocol types (I2C, SPI, UART, CAN, etc.)
    scpi_variant: str  # SCPI command variant ("standard", "hd_series", "x_series", "plus_series")

    def __str__(self) -> str:
        """String representation of model capability."""
        return f"{self.model_name} ({self.num_channels}ch, {self.bandwidth_mhz}MHz, {self.series})"


# Model Registry - Add new models here
MODEL_REGISTRY = {
    # SDS800X HD Series
    "SDS824X HD": ModelCapability(
        model_name="SDS824X HD",
        series="SDS800XHD",
        num_channels=4,
        max_sample_rate=1.0,
        memory_depth=100_000_000,
        bandwidth_mhz=200,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=True,
        supported_decode_types=["I2C", "SPI", "UART", "CAN", "LIN", "I2S"],
        scpi_variant="hd_series",
    ),  # 1 GSa/s  # 100 Mpts
    "SDS804X HD": ModelCapability(
        model_name="SDS804X HD",
        series="SDS800XHD",
        num_channels=4,
        max_sample_rate=1.0,
        memory_depth=100_000_000,
        bandwidth_mhz=70,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=True,
        supported_decode_types=["I2C", "SPI", "UART", "CAN", "LIN", "I2S"],
        scpi_variant="hd_series",
    ),
    # SDS1000X-E Series
    "SDS1104X-E": ModelCapability(
        model_name="SDS1104X-E",
        series="SDS1000XE",
        num_channels=4,
        max_sample_rate=1.0,
        memory_depth=14_000_000,
        bandwidth_mhz=100,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=True,
        supported_decode_types=["I2C", "SPI", "UART", "RS232"],
        scpi_variant="x_series",
    ),  # 14 Mpts
    "SDS1204X-E": ModelCapability(
        model_name="SDS1204X-E",
        series="SDS1000XE",
        num_channels=4,
        max_sample_rate=1.0,
        memory_depth=14_000_000,
        bandwidth_mhz=200,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=True,
        supported_decode_types=["I2C", "SPI", "UART", "RS232"],
        scpi_variant="x_series",
    ),
    "SDS1202X-E": ModelCapability(
        model_name="SDS1202X-E",
        series="SDS1000XE",
        num_channels=2,
        max_sample_rate=1.0,
        memory_depth=14_000_000,
        bandwidth_mhz=200,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=True,
        supported_decode_types=["I2C", "SPI", "UART", "RS232"],
        scpi_variant="x_series",
    ),
    "SDS1102X-E": ModelCapability(
        model_name="SDS1102X-E",
        series="SDS1000XE",
        num_channels=2,
        max_sample_rate=1.0,
        memory_depth=14_000_000,
        bandwidth_mhz=100,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=True,
        supported_decode_types=["I2C", "SPI", "UART", "RS232"],
        scpi_variant="x_series",
    ),
    # SDS2000X Plus Series
    "SDS2104X Plus": ModelCapability(
        model_name="SDS2104X Plus",
        series="SDS2000XPlus",
        num_channels=4,
        max_sample_rate=2.0,
        memory_depth=100_000_000,
        bandwidth_mhz=100,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=True,
        supported_decode_types=["I2C", "SPI", "UART", "CAN", "LIN", "FlexRay"],
        scpi_variant="plus_series",
    ),  # 2 GSa/s
    "SDS2204X Plus": ModelCapability(
        model_name="SDS2204X Plus",
        series="SDS2000XPlus",
        num_channels=4,
        max_sample_rate=2.0,
        memory_depth=100_000_000,
        bandwidth_mhz=200,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=True,
        supported_decode_types=["I2C", "SPI", "UART", "CAN", "LIN", "FlexRay"],
        scpi_variant="plus_series",
    ),
    "SDS2354X Plus": ModelCapability(
        model_name="SDS2354X Plus",
        series="SDS2000XPlus",
        num_channels=4,
        max_sample_rate=2.0,
        memory_depth=100_000_000,
        bandwidth_mhz=350,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=True,
        supported_decode_types=["I2C", "SPI", "UART", "CAN", "LIN", "FlexRay"],
        scpi_variant="plus_series",
    ),
    # SDS5000X Series
    "SDS5104X": ModelCapability(
        model_name="SDS5104X",
        series="SDS5000X",
        num_channels=4,
        max_sample_rate=5.0,
        memory_depth=250_000_000,
        bandwidth_mhz=1000,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=True,
        supported_decode_types=["I2C", "SPI", "UART", "CAN", "LIN", "FlexRay", "ARINC429"],
        scpi_variant="x_series",
    ),  # 5 GSa/s  # 250 Mpts  # 1 GHz
    "SDS5054X": ModelCapability(
        model_name="SDS5054X",
        series="SDS5000X",
        num_channels=4,
        max_sample_rate=5.0,
        memory_depth=250_000_000,
        bandwidth_mhz=500,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=True,
        supported_decode_types=["I2C", "SPI", "UART", "CAN", "LIN", "FlexRay", "ARINC429"],
        scpi_variant="x_series",
    ),
}


def detect_model_from_idn(idn_string: str) -> ModelCapability:
    """Detect oscilloscope model and return its capability profile.

    Args:
        idn_string: The response from *IDN? command
                   Format: "Manufacturer,Model,Serial,Firmware"
                   Example: "Siglent Technologies,SDS824X HD,SERIAL123,1.0.0.0"

    Returns:
        ModelCapability object for the detected model

    Raises:
        ValueError: If model cannot be detected from IDN string
    """
    # Parse the model name from IDN string
    parts = idn_string.split(",")
    if len(parts) < 2:
        raise ValueError(f"Invalid *IDN? response format: {idn_string}")

    model_from_idn = parts[1].strip()
    logger.info(f"Detecting model from IDN: {model_from_idn}")

    # Try exact match first
    if model_from_idn in MODEL_REGISTRY:
        logger.info(f"Exact match found: {model_from_idn}")
        return MODEL_REGISTRY[model_from_idn]

    # Try fuzzy matching - handle variations in model name format
    # Remove spaces, dashes, underscores for comparison
    normalized_model = re.sub(r"[\s\-_]", "", model_from_idn).upper()

    for registered_model, capability in MODEL_REGISTRY.items():
        normalized_registered = re.sub(r"[\s\-_]", "", registered_model).upper()
        if normalized_model == normalized_registered:
            logger.info(f"Fuzzy match found: {model_from_idn} -> {registered_model}")
            return capability

    # Try partial matching - check if registry key is contained in model name
    for registered_model, capability in MODEL_REGISTRY.items():
        # Remove spaces from both for comparison
        if registered_model.replace(" ", "").upper() in model_from_idn.replace(" ", "").upper():
            logger.info(f"Partial match found: {model_from_idn} -> {registered_model}")
            return capability

    # Model not found - create a generic fallback capability
    logger.warning(f"Model '{model_from_idn}' not in registry, using generic fallback")

    # Try to infer series and channel count from model name
    series = "Unknown"
    num_channels = 4  # Default to 4 channels

    if "SDS8" in model_from_idn.upper():
        series = "SDS800XHD"
        scpi_variant = "hd_series"
    elif "SDS1" in model_from_idn.upper():
        series = "SDS1000XE"
        scpi_variant = "x_series"
    elif "SDS2" in model_from_idn.upper():
        series = "SDS2000XPlus"
        scpi_variant = "plus_series"
    elif "SDS5" in model_from_idn.upper():
        series = "SDS5000X"
        scpi_variant = "x_series"
    else:
        scpi_variant = "standard"

    # Try to determine channel count from model number
    # Most Siglent models have format: SDSxxYZ where Y can indicate channels
    # e.g., SDS1202X-E = 2 channels, SDS1104X-E = 4 channels
    match = re.search(r"SDS\d+([024])(\d+)", model_from_idn)
    if match:
        potential_channels = int(match.group(1))
        if potential_channels in [2, 4]:
            num_channels = potential_channels

    # Create generic capability
    generic_capability = ModelCapability(
        model_name=model_from_idn,
        series=series,
        num_channels=num_channels,
        max_sample_rate=1.0,
        memory_depth=10_000_000,
        bandwidth_mhz=100,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=False,
        supported_decode_types=[],
        scpi_variant=scpi_variant,
    )  # Conservative default  # Conservative default  # Most models support this  # Most models support this  # Conservative - don't assume

    logger.info(f"Created generic capability: {generic_capability}")
    return generic_capability


def list_supported_models() -> List[str]:
    """Get list of all explicitly supported model names.

    Returns:
        List of model names that have full capability definitions
    """
    return sorted(MODEL_REGISTRY.keys())


def get_model_by_series(series: str) -> List[ModelCapability]:
    """Get all models in a specific series.

    Args:
        series: Series identifier (e.g., "SDS1000XE", "SDS2000XPlus")

    Returns:
        List of ModelCapability objects for models in that series
    """
    return [cap for cap in MODEL_REGISTRY.values() if cap.series == series]
