"""Model capability definitions for SCPI-controlled function generators.

Supports generic SCPI-99 arbitrary waveform generators and Siglent SDG series models.
"""

import logging
import re
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class ChannelSpec:
    """Specification for a single function generator output channel."""

    channel_num: int  # Channel number (1, 2, etc.)
    max_frequency: float  # Maximum frequency in Hz
    max_amplitude: float  # Maximum amplitude in Vpp
    min_amplitude: float  # Minimum amplitude in Vpp
    max_offset: float  # Maximum DC offset in volts
    frequency_resolution: float  # Frequency resolution in Hz
    amplitude_resolution: float  # Amplitude resolution in Vpp

    def __str__(self) -> str:
        """String representation of channel spec."""
        freq_mhz = self.max_frequency / 1e6
        return f"Ch{self.channel_num}: {freq_mhz}MHz, {self.max_amplitude}Vpp"


@dataclass
class AWGCapability:
    """Defines capabilities and features for a specific function generator model.

    This dataclass contains all model-specific information including hardware
    specifications and supported features.
    """

    model_name: str  # Full model name (e.g., "SDG1032X")
    manufacturer: str  # Manufacturer name (e.g., "Siglent")
    num_channels: int  # Number of output channels (1 or 2 typically)
    channel_specs: List[ChannelSpec]  # Specifications for each channel
    sample_rate: float  # Sample rate in Sa/s
    waveform_length: int  # Maximum arbitrary waveform length in points
    has_modulation: bool  # AM, FM, PM modulation support
    has_sweep: bool  # Frequency sweep support
    has_burst: bool  # Burst mode support
    has_arbitrary: bool  # Arbitrary waveform support
    has_noise: bool  # Noise generator support
    scpi_variant: str  # SCPI command variant ("generic", "siglent_sdg")

    def __str__(self) -> str:
        """String representation of AWG capability."""
        return (
            f"{self.manufacturer} {self.model_name} "
            f"({self.num_channels} channels, {self.scpi_variant})"
        )


# AWG Model Registry - Add new models here
AWG_MODEL_REGISTRY = {
    # Siglent SDG1000X Series (entry-level, 1-2 channels)
    "SDG1032X": AWGCapability(
        model_name="SDG1032X",
        manufacturer="Siglent",
        num_channels=2,
        channel_specs=[
            ChannelSpec(1, 30e6, 20.0, 0.002, 10.0, 1e-6, 0.001),  # 30MHz, 20Vpp max
            ChannelSpec(2, 30e6, 20.0, 0.002, 10.0, 1e-6, 0.001),
        ],
        sample_rate=150e6,  # 150 MSa/s
        waveform_length=16384,  # 16k points
        has_modulation=True,
        has_sweep=True,
        has_burst=True,
        has_arbitrary=True,
        has_noise=True,
        scpi_variant="siglent_sdg",
    ),
    "SDG1025": AWGCapability(
        model_name="SDG1025",
        manufacturer="Siglent",
        num_channels=2,
        channel_specs=[
            ChannelSpec(1, 25e6, 10.0, 0.002, 5.0, 1e-6, 0.001),  # 25MHz, 10Vpp max
            ChannelSpec(2, 25e6, 10.0, 0.002, 5.0, 1e-6, 0.001),
        ],
        sample_rate=125e6,  # 125 MSa/s
        waveform_length=8192,  # 8k points
        has_modulation=True,
        has_sweep=True,
        has_burst=True,
        has_arbitrary=True,
        has_noise=True,
        scpi_variant="siglent_sdg",
    ),
    "SDG1020": AWGCapability(
        model_name="SDG1020",
        manufacturer="Siglent",
        num_channels=2,
        channel_specs=[
            ChannelSpec(1, 20e6, 10.0, 0.002, 5.0, 1e-6, 0.001),  # 20MHz, 10Vpp max
            ChannelSpec(2, 20e6, 10.0, 0.002, 5.0, 1e-6, 0.001),
        ],
        sample_rate=125e6,  # 125 MSa/s
        waveform_length=8192,  # 8k points
        has_modulation=True,
        has_sweep=True,
        has_burst=True,
        has_arbitrary=True,
        has_noise=True,
        scpi_variant="siglent_sdg",
    ),
    # Siglent SDG2000X Series (mid-range, higher performance)
    "SDG2122X": AWGCapability(
        model_name="SDG2122X",
        manufacturer="Siglent",
        num_channels=2,
        channel_specs=[
            ChannelSpec(1, 120e6, 20.0, 0.002, 10.0, 1e-6, 0.001),  # 120MHz, 20Vpp
            ChannelSpec(2, 120e6, 20.0, 0.002, 10.0, 1e-6, 0.001),
        ],
        sample_rate=1.2e9,  # 1.2 GSa/s
        waveform_length=16384,  # 16k points
        has_modulation=True,
        has_sweep=True,
        has_burst=True,
        has_arbitrary=True,
        has_noise=True,
        scpi_variant="siglent_sdg",
    ),
    "SDG2082X": AWGCapability(
        model_name="SDG2082X",
        manufacturer="Siglent",
        num_channels=2,
        channel_specs=[
            ChannelSpec(1, 80e6, 20.0, 0.002, 10.0, 1e-6, 0.001),  # 80MHz, 20Vpp
            ChannelSpec(2, 80e6, 20.0, 0.002, 10.0, 1e-6, 0.001),
        ],
        sample_rate=1.2e9,  # 1.2 GSa/s
        waveform_length=16384,  # 16k points
        has_modulation=True,
        has_sweep=True,
        has_burst=True,
        has_arbitrary=True,
        has_noise=True,
        scpi_variant="siglent_sdg",
    ),
    "SDG2042X": AWGCapability(
        model_name="SDG2042X",
        manufacturer="Siglent",
        num_channels=2,
        channel_specs=[
            ChannelSpec(1, 40e6, 20.0, 0.002, 10.0, 1e-6, 0.001),  # 40MHz, 20Vpp
            ChannelSpec(2, 40e6, 20.0, 0.002, 10.0, 1e-6, 0.001),
        ],
        sample_rate=1.2e9,  # 1.2 GSa/s
        waveform_length=16384,  # 16k points
        has_modulation=True,
        has_sweep=True,
        has_burst=True,
        has_arbitrary=True,
        has_noise=True,
        scpi_variant="siglent_sdg",
    ),
}


def detect_awg_from_idn(idn_string: str) -> AWGCapability:
    """Detect function generator model and return its capability profile.

    Args:
        idn_string: The response from *IDN? command
                   Format: "Manufacturer,Model,Serial,Firmware"
                   Example: "Siglent Technologies,SDG1032X,SDG1XXXXXXXXXXX,2.01.01.37R1"

    Returns:
        AWGCapability object for the detected model

    Note:
        Unknown models will receive a generic SCPI capability profile
        to enable basic control functionality.
    """
    # Parse the model name from IDN string
    parts = idn_string.split(",")
    if len(parts) < 2:
        logger.warning(f"Invalid *IDN? response format: {idn_string}")
        return create_generic_awg_capability(idn_string)

    manufacturer = parts[0].strip()
    model_from_idn = parts[1].strip()
    logger.info(f"Detecting AWG model from IDN: {manufacturer}, {model_from_idn}")

    # Try exact match first
    if model_from_idn in AWG_MODEL_REGISTRY:
        logger.info(f"Exact match found: {model_from_idn}")
        return AWG_MODEL_REGISTRY[model_from_idn]

    # Try fuzzy matching - handle variations in model name format
    # Remove spaces, dashes, underscores for comparison
    normalized_model = re.sub(r"[\s\-_]", "", model_from_idn).upper()

    for registered_model, capability in AWG_MODEL_REGISTRY.items():
        normalized_registered = re.sub(r"[\s\-_]", "", registered_model).upper()
        if normalized_model == normalized_registered:
            logger.info(
                f"Fuzzy match found: {model_from_idn} -> {registered_model}"
            )
            return capability

    # Try partial matching for Siglent models
    if "Siglent" in manufacturer and "SDG" in model_from_idn.upper():
        for registered_model, capability in AWG_MODEL_REGISTRY.items():
            # Check if registry key is contained in model name
            if (
                registered_model.replace(" ", "").upper()
                in model_from_idn.replace(" ", "").upper()
            ):
                logger.info(
                    f"Partial match found: {model_from_idn} -> {registered_model}"
                )
                return capability

    # Model not found - create a generic fallback capability
    logger.warning(
        f"Model '{model_from_idn}' not in registry, using generic SCPI profile"
    )
    return create_generic_awg_capability(idn_string)


def create_generic_awg_capability(idn_string: str) -> AWGCapability:
    """Create generic SCPI capability for unknown function generator.

    This provides a conservative capability profile that should work with
    any SCPI-99 compliant arbitrary waveform generator using standard commands.

    Args:
        idn_string: The *IDN? response string

    Returns:
        Generic AWGCapability with conservative defaults
    """
    parts = idn_string.split(",")
    manufacturer = parts[0].strip() if len(parts) > 0 else "Unknown"
    model = parts[1].strip() if len(parts) > 1 else "Generic AWG"

    logger.info(f"Creating generic AWG capability for {manufacturer} {model}")

    # Conservative generic capability
    # Most AWGs have at least 1 channel with these typical ranges
    generic_capability = AWGCapability(
        model_name=model,
        manufacturer=manufacturer,
        num_channels=1,  # Conservative default
        channel_specs=[
            ChannelSpec(
                1, 10e6, 10.0, 0.01, 5.0, 1e-6, 0.001
            )  # 10MHz, 10Vpp typical
        ],
        sample_rate=100e6,  # 100 MSa/s typical
        waveform_length=8192,  # 8k points typical
        has_modulation=False,  # Conservative - don't assume
        has_sweep=False,  # Conservative - don't assume
        has_burst=False,  # Conservative - don't assume
        has_arbitrary=False,  # Conservative - don't assume
        has_noise=False,  # Conservative - don't assume
        scpi_variant="generic",  # Use standard SCPI-99 commands
    )

    logger.info(f"Created generic capability: {generic_capability}")
    return generic_capability


def list_supported_models() -> List[str]:
    """Get list of all explicitly supported AWG model names.

    Returns:
        Sorted list of model names that have full capability definitions
    """
    return sorted(AWG_MODEL_REGISTRY.keys())


def get_models_by_manufacturer(manufacturer: str) -> List[AWGCapability]:
    """Get all models from a specific manufacturer.

    Args:
        manufacturer: Manufacturer name (e.g., "Siglent", "Keysight")

    Returns:
        List of AWGCapability objects for models from that manufacturer
    """
    return [
        cap
        for cap in AWG_MODEL_REGISTRY.values()
        if cap.manufacturer.lower() == manufacturer.lower()
    ]
