"""Model capability definitions for different Siglent oscilloscope series."""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from scpi_control import exceptions

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
    dialect: str = "legacy"  # Wire dialect: "legacy", "modern", "tektronix", or "lecroy"
    vendor: str = "siglent"  # Instrument vendor: "siglent", "tektronix", or "lecroy"
    horiz_divisions: int = 14  # Screen grid width in divisions (Siglent scopes use 14)
    vert_divisions: int = 8  # Screen grid height in divisions

    def __str__(self) -> str:
        """String representation of model capability."""
        return f"{self.model_name} ({self.num_channels}ch, {self.bandwidth_mhz}MHz, {self.series})"


# Widest scope in the registry (MSO58 / MSO58LP are 8-channel). Used as the
# channel-range fallback when a scope's capability is not resolved yet.
MAX_SUPPORTED_CHANNELS = 8


def validate_channel(scope, channel: int) -> None:
    """Raise unless `channel` exists on `scope`'s model.

    The bound comes from the connected model's ``num_channels``. When that is
    unavailable or not an int -- an unconnected scope, or a ``unittest.mock.Mock``
    stand-in whose attribute access yields Mocks that cannot be compared
    numerically -- fall back to MAX_SUPPORTED_CHANNELS so the guard degrades to a
    range check instead of raising TypeError.

    Args:
        scope: Oscilloscope (or stand-in) whose model_capability bounds the range
        channel: 1-based channel number to validate

    Raises:
        InvalidParameterError: If the channel is outside 1..num_channels
    """
    num_channels = getattr(getattr(scope, "model_capability", None), "num_channels", None)
    if not isinstance(num_channels, int):
        num_channels = MAX_SUPPORTED_CHANNELS
    if not 1 <= channel <= num_channels:
        raise exceptions.InvalidParameterError(f"Invalid channel number: {channel}. Must be 1-{num_channels}.")


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
        dialect="modern",
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
        dialect="modern",
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
        dialect="legacy",
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
        dialect="legacy",
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
        dialect="legacy",
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
        dialect="legacy",
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
        dialect="modern",
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
        dialect="modern",
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
        dialect="modern",
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
        dialect="modern",
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
        dialect="modern",
    ),
    # Tektronix TBS1000C Series (datasheet: 2 ch, 1 GSa/s, 20 kpts, 15x8 grid)
    "TBS1102C": ModelCapability(
        model_name="TBS1102C",
        series="TBS1000C",
        num_channels=2,
        max_sample_rate=1.0,
        memory_depth=20_000,
        bandwidth_mhz=100,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=False,
        supported_decode_types=[],
        scpi_variant="tek_tbs",
        dialect="tektronix",
        vendor="tektronix",
        horiz_divisions=15,
        vert_divisions=8,
    ),
    # Tektronix 2 Series MSO (datasheet: 4 ch, 2.5 GSa/s, 10 Mpts, 10x10 grid)
    "MSO24": ModelCapability(
        model_name="MSO24",
        series="MSO2",
        num_channels=4,
        max_sample_rate=2.5,
        memory_depth=10_000_000,
        bandwidth_mhz=200,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=False,
        supported_decode_types=[],
        scpi_variant="tek_mso",
        dialect="tektronix",
        vendor="tektronix",
        horiz_divisions=10,
        vert_divisions=10,
    ),
    # LeCroy WaveSurfer 3000z (datasheet: 4 ch, 4 GSa/s, 10 Mpts, 10x8 grid)
    "WaveSurfer 3024z": ModelCapability(
        model_name="WaveSurfer 3024z",
        series="WaveSurfer3000z",
        num_channels=4,
        max_sample_rate=4.0,
        memory_depth=10_000_000,
        bandwidth_mhz=200,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=False,
        supported_decode_types=[],
        scpi_variant="lecroy_maui",
        dialect="lecroy",
        vendor="lecroy",
        horiz_divisions=10,
        vert_divisions=8,
    ),
    # LeCroy WaveRunner 8000 (datasheet: 4 ch, 10 GSa/s, 16 Mpts, 10x8 grid)
    "WaveRunner 8104": ModelCapability(
        model_name="WaveRunner 8104",
        series="WaveRunner8000",
        num_channels=4,
        max_sample_rate=10.0,
        memory_depth=16_000_000,
        bandwidth_mhz=1000,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=False,
        supported_decode_types=[],
        scpi_variant="lecroy_maui",
        dialect="lecroy",
        vendor="lecroy",
        horiz_divisions=10,
        vert_divisions=8,
    ),
}


def _match_registry(model_from_idn: str, vendor: Optional[str] = None) -> Optional[ModelCapability]:
    """Exact -> fuzzy -> partial registry match, optionally filtered by vendor."""
    candidates = {name: cap for name, cap in MODEL_REGISTRY.items() if vendor is None or cap.vendor == vendor}

    if model_from_idn in candidates:
        logger.info(f"Exact match found: {model_from_idn}")
        return candidates[model_from_idn]

    normalized_model = re.sub(r"[\s\-_]", "", model_from_idn).upper()
    for registered_model, capability in candidates.items():
        if re.sub(r"[\s\-_]", "", registered_model).upper() == normalized_model:
            logger.info(f"Fuzzy match found: {model_from_idn} -> {registered_model}")
            return capability

    for registered_model, capability in candidates.items():
        if registered_model.replace(" ", "").upper() in model_from_idn.replace(" ", "").upper():
            logger.info(f"Partial match found: {model_from_idn} -> {registered_model}")
            return capability

    return None


def _generic_vendor_capability(model_from_idn: str, vendor: str) -> ModelCapability:
    """Conservative fallback for an unrecognized model of a known vendor."""
    upper = model_from_idn.upper()
    if vendor == "tektronix":
        # TBS1000-pattern models are 2-channel; everything else defaults to 4
        num_channels = 2 if re.match(r"TBS1\d", upper) else 4
        scpi_variant = "tek_tbs" if upper.startswith("TBS") else "tek_mso"
        dialect = "tektronix"
        horiz, vert = (15, 8) if upper.startswith("TBS1") else (10, 10)
    else:  # lecroy
        num_channels = 4
        scpi_variant = "lecroy_maui"
        dialect = "lecroy"
        horiz, vert = 10, 8

    logger.warning(f"Model '{model_from_idn}' not in registry, using generic {vendor} fallback")
    return ModelCapability(
        model_name=model_from_idn,
        series="Unknown",
        num_channels=num_channels,
        max_sample_rate=1.0,
        memory_depth=10_000_000,
        bandwidth_mhz=100,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=False,
        supported_decode_types=[],
        scpi_variant=scpi_variant,
        dialect=dialect,
        vendor=vendor,
        horiz_divisions=horiz,
        vert_divisions=vert,
    )


def detect_model_from_idn(idn_string: str) -> ModelCapability:
    """Detect oscilloscope model and return its capability profile.

    Routes on the manufacturer field: Tektronix and LeCroy IDNs are matched
    against their vendor-scoped registry entries (falling back to a generic
    vendor capability), while every other manufacturer takes the historical
    Siglent detection path unchanged.

    Args:
        idn_string: The response from *IDN? command
                   Format: "Manufacturer,Model,Serial,Firmware"
                   Example: "Siglent Technologies,SDS824X HD,SERIAL123,1.0.0.0"

    Returns:
        ModelCapability object for the detected model

    Raises:
        ValueError: If model cannot be detected from IDN string
    """
    # Parse the manufacturer and model name from IDN string
    parts = idn_string.split(",")
    if len(parts) < 2:
        raise ValueError(f"Invalid *IDN? response format: {idn_string}")

    manufacturer = parts[0].strip().upper()
    model_from_idn = parts[1].strip()
    logger.info(f"Detecting model from IDN: {manufacturer} / {model_from_idn}")

    if "TEKTRONIX" in manufacturer:
        return _match_registry(model_from_idn, "tektronix") or _generic_vendor_capability(model_from_idn, "tektronix")
    if "LECROY" in manufacturer:  # covers both "LECROY" and "TELEDYNE LECROY"
        return _match_registry(model_from_idn, "lecroy") or _generic_vendor_capability(model_from_idn, "lecroy")

    # Everything else takes the historical Siglent path, byte-for-byte
    matched = _match_registry(model_from_idn)
    if matched is not None:
        return matched
    return _detect_siglent(model_from_idn)


def _detect_siglent(model_from_idn: str) -> ModelCapability:
    """Generic Siglent fallback when no registry match is found.

    Historical behavior, unchanged: infer series/channel count/dialect from
    the model name pattern when the model isn't in the registry.
    """
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

    upper_model = model_from_idn.upper()
    # Modern colon-form generations: HD models, Plus models, SDS5000X and up.
    # Everything else (X-E era, unknown) stays on the legacy dialect.
    if " HD" in upper_model or upper_model.endswith("HD") or "PLUS" in upper_model or any(s in upper_model for s in ("SDS5", "SDS6", "SDS7")):
        dialect = "modern"
    else:
        dialect = "legacy"

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
        dialect=dialect,
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
