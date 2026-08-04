"""Model capability definitions for SCPI-controlled power supplies.

Supports generic SCPI-99 power supplies and Siglent SPD series models.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutputSpec:
    """Specification for a single power supply output.

    The six capability flags record what the model's programming manual
    documents for THIS output. They all default True, so every model that
    does not set them keeps its existing behaviour; only an output the
    manual restricts sets one False. Frozen because PowerSupply.capabilities
    hands back the shared registry object: a caller flipping a flag would
    change behaviour for every instance in the process.
    """

    output_num: int  # Output number (1, 2, etc.)
    max_voltage: float  # Maximum voltage in volts
    max_current: float  # Maximum current in amps
    max_power: float  # Maximum power in watts
    voltage_resolution: float  # Voltage resolution in volts
    current_resolution: float  # Current resolution in amps
    programmable: bool = True  # Voltage/current setpoints can be set and queried
    measurable: bool = True  # MEASure: voltage/current/power, and CV/CC mode
    switchable: bool = True  # Output can be turned on/off
    state_readable: bool = True  # Output on/off state can be read back
    supports_timer: bool = True  # Timer subsystem covers this output
    supports_waveform: bool = True  # Waveform display covers this output

    def __str__(self) -> str:
        """String representation of output spec."""
        return f"Output{self.output_num}: {self.max_voltage}V/{self.max_current}A ({self.max_power}W)"


@dataclass(frozen=True)
class PSUCapability:
    """Defines capabilities and features for a specific power supply model.

    This dataclass contains all model-specific information including hardware
    specifications and supported features.
    """

    model_name: str  # Full model name (e.g., "SPD3303X")
    manufacturer: str  # Manufacturer name (e.g., "Siglent", "Keysight")
    num_outputs: int  # Number of outputs (1, 2, or 3)
    output_specs: List[OutputSpec]  # Specifications for each output
    has_ovp: bool  # Over-voltage protection support
    has_ocp: bool  # Over-current protection support
    has_timer: bool  # Timer functionality
    has_waveform: bool  # Waveform generation
    has_tracking: bool  # Channel tracking modes (series/parallel)
    has_remote_sense: bool  # 4-wire remote sensing
    scpi_variant: str  # SCPI command variant ("generic", "siglent_spd")

    def __str__(self) -> str:
        """String representation of PSU capability."""
        return f"{self.manufacturer} {self.model_name} " f"({self.num_outputs} outputs, {self.scpi_variant})"


# PSU Model Registry - Add new models here
PSU_MODEL_REGISTRY = {
    # Siglent SPD3303X/SPD3303X-E (triple output)
    "SPD3303X": PSUCapability(
        model_name="SPD3303X",
        manufacturer="Siglent",
        num_outputs=3,
        output_specs=[
            OutputSpec(1, 30.0, 3.0, 90.0, 0.001, 0.001),
            OutputSpec(2, 30.0, 3.0, 90.0, 0.001, 0.001),
            # CH3 is the DIP-switch-selected fixed rail (2.5V/3.3V/5V, 3.2A --
            # QS0503X-E01B p.21). There is no SCPI path to its setpoints:
            # VOLTage/CURRent are [{CH1|CH2}:] only (p.39), MEASure is
            # [{CH1|CH2}] only (p.38), TIMEr is {CH1|CH2} (p.41) and
            # OUTPut:WAVE is {CH1|CH2} (p.40). p.42's SYSTem:STATus? bit table
            # defines CH1/CH2 CV/CC and on/off bits only -- there is no CH3
            # state bit, which is why reading output3.enabled used to hang.
            # OUTPut {CH1|CH2|CH3},{ON|OFF} (p.40) DOES cover CH3, so it stays
            # switchable.
            OutputSpec(
                3,
                5.0,
                3.0,
                15.0,
                0.01,
                0.001,
                programmable=False,
                measurable=False,
                switchable=True,
                state_readable=False,
                supports_timer=False,
                supports_waveform=False,
            ),
        ],
        # QS0503X-E01B p.36 lists the full SPD3303X command set; it has no
        # protection subsystem, so OVP/OCP calls never armed anything on
        # real hardware. False as of v5.0.0 (audit H18).
        has_ovp=False,
        has_ocp=False,
        has_timer=True,
        has_waveform=True,
        has_tracking=True,
        has_remote_sense=True,
        scpi_variant="siglent_spd",
    ),
    "SPD3303X-E": PSUCapability(
        model_name="SPD3303X-E",
        manufacturer="Siglent",
        num_outputs=3,
        output_specs=[
            OutputSpec(1, 30.0, 3.0, 90.0, 0.001, 0.001),
            OutputSpec(2, 30.0, 3.0, 90.0, 0.001, 0.001),
            # CH3 is the DIP-switch-selected fixed rail (2.5V/3.3V/5V, 3.2A --
            # QS0503X-E01B p.21). There is no SCPI path to its setpoints:
            # VOLTage/CURRent are [{CH1|CH2}:] only (p.39), MEASure is
            # [{CH1|CH2}] only (p.38), TIMEr is {CH1|CH2} (p.41) and
            # OUTPut:WAVE is {CH1|CH2} (p.40). p.42's SYSTem:STATus? bit table
            # defines CH1/CH2 CV/CC and on/off bits only -- there is no CH3
            # state bit, which is why reading output3.enabled used to hang.
            # OUTPut {CH1|CH2|CH3},{ON|OFF} (p.40) DOES cover CH3, so it stays
            # switchable.
            OutputSpec(
                3,
                5.0,
                3.0,
                15.0,
                0.01,
                0.001,
                programmable=False,
                measurable=False,
                switchable=True,
                state_readable=False,
                supports_timer=False,
                supports_waveform=False,
            ),
        ],
        # QS0503X-E01B p.36 lists the full SPD3303X command set; it has no
        # protection subsystem, so OVP/OCP calls never armed anything on
        # real hardware. False as of v5.0.0 (audit H18).
        has_ovp=False,
        has_ocp=False,
        has_timer=True,
        has_waveform=True,
        has_tracking=True,
        has_remote_sense=True,
        scpi_variant="siglent_spd",
    ),
    # Siglent SPD1305X (single output, 30V/5A)
    "SPD1305X": PSUCapability(
        model_name="SPD1305X",
        manufacturer="Siglent",
        num_outputs=1,
        output_specs=[
            OutputSpec(1, 30.0, 5.0, 150.0, 0.001, 0.001),
        ],
        # No SPD1000X programming manual in docs/ documents a protection
        # subsystem; the generic SOUR{ch}:VOLT:PROT fallback previously used
        # here is uncitable and silently discarded by SPD firmware (same class
        # as audit H18 on the SPD3303X). Backend review 2026-07-31, High-3.
        has_ovp=False,
        has_ocp=False,
        has_timer=False,
        has_waveform=False,
        has_tracking=False,
        has_remote_sense=True,
        scpi_variant="siglent_spd",
    ),
    # Siglent SPD1168X (single output, 16V/8A)
    "SPD1168X": PSUCapability(
        model_name="SPD1168X",
        manufacturer="Siglent",
        num_outputs=1,
        output_specs=[
            OutputSpec(1, 16.0, 8.0, 128.0, 0.001, 0.001),
        ],
        # No SPD1000X programming manual in docs/ documents a protection
        # subsystem; the generic SOUR{ch}:VOLT:PROT fallback previously used
        # here is uncitable and silently discarded by SPD firmware (same class
        # as audit H18 on the SPD3303X). Backend review 2026-07-31, High-3.
        has_ovp=False,
        has_ocp=False,
        has_timer=False,
        has_waveform=False,
        has_tracking=False,
        has_remote_sense=True,
        scpi_variant="siglent_spd",
    ),
}


def detect_psu_from_idn(idn_string: str) -> PSUCapability:
    """Detect power supply model and return its capability profile.

    Args:
        idn_string: The response from *IDN? command
                   Format: "Manufacturer,Model,Serial,Firmware"
                   Example: "Siglent Technologies,SPD3303X,SPD3XXXXXXXXXXX,V1.01"

    Returns:
        PSUCapability object for the detected model

    Note:
        Unknown models will receive a generic SCPI capability profile
        to enable basic control functionality.
    """
    # Parse the model name from IDN string
    parts = idn_string.split(",")
    if len(parts) < 2:
        logger.warning(f"Invalid *IDN? response format: {idn_string}")
        return create_generic_psu_capability(idn_string)

    manufacturer = parts[0].strip()
    model_from_idn = parts[1].strip()
    logger.info(f"Detecting PSU model from IDN: {manufacturer}, {model_from_idn}")

    # Try exact match first
    if model_from_idn in PSU_MODEL_REGISTRY:
        logger.info(f"Exact match found: {model_from_idn}")
        return PSU_MODEL_REGISTRY[model_from_idn]

    # Try fuzzy matching - handle variations in model name format
    # Remove spaces, dashes, underscores for comparison
    normalized_model = re.sub(r"[\s\-_]", "", model_from_idn).upper()

    for registered_model, capability in PSU_MODEL_REGISTRY.items():
        normalized_registered = re.sub(r"[\s\-_]", "", registered_model).upper()
        if normalized_model == normalized_registered:
            logger.info(f"Fuzzy match found: {model_from_idn} -> {registered_model}")
            return capability

    # Try partial matching for Siglent models
    if "Siglent" in manufacturer and "SPD" in model_from_idn.upper():
        for registered_model, capability in PSU_MODEL_REGISTRY.items():
            # Check if registry key is contained in model name
            if registered_model.replace(" ", "").upper() in model_from_idn.replace(" ", "").upper():
                logger.info(f"Partial match found: {model_from_idn} -> {registered_model}")
                return capability

    # Model not found - create a generic fallback capability
    logger.warning(f"Model '{model_from_idn}' not in registry, using generic SCPI profile")
    return create_generic_psu_capability(idn_string)


def create_generic_psu_capability(idn_string: str) -> PSUCapability:
    """Create generic SCPI capability for unknown power supply.

    This provides a conservative capability profile that should work with
    any SCPI-99 compliant power supply using standard commands.

    Args:
        idn_string: The *IDN? response string

    Returns:
        Generic PSUCapability with conservative defaults
    """
    parts = idn_string.split(",")
    manufacturer = parts[0].strip() if len(parts) > 0 else "Unknown"
    model = parts[1].strip() if len(parts) > 1 else "Generic PSU"

    logger.info(f"Creating generic PSU capability for {manufacturer} {model}")

    # Conservative generic capability
    # Most SCPI PSUs have at least 1 output with these typical ranges
    generic_capability = PSUCapability(
        model_name=model,
        manufacturer=manufacturer,
        num_outputs=1,  # Conservative default
        output_specs=[OutputSpec(1, 30.0, 3.0, 90.0, 0.001, 0.001)],  # Typical lab PSU specs
        # HONESTY GATE: an unrecognized model must not advertise a protection
        # subsystem nobody can cite -- the generic SOUR{ch}:VOLT:PROT fallback
        # is exactly the uncitable path the SPD registry entries gate with
        # has_ovp=False (audit H18 / backend review 2026-07-31 High-3). A model
        # that really has OVP/OCP belongs in PSU_MODEL_REGISTRY with citations.
        has_ovp=False,
        has_ocp=False,
        has_timer=False,  # Conservative - don't assume
        has_waveform=False,  # Advanced feature - don't assume
        has_tracking=False,  # Advanced feature - don't assume
        has_remote_sense=False,  # Not always available
        scpi_variant="generic",  # Use standard SCPI-99 commands
    )

    logger.info(f"Created generic capability: {generic_capability}")
    return generic_capability


def list_supported_models() -> List[str]:
    """Get list of all explicitly supported PSU model names.

    Returns:
        Sorted list of model names that have full capability definitions
    """
    return sorted(PSU_MODEL_REGISTRY.keys())


def get_models_by_manufacturer(manufacturer: str) -> List[PSUCapability]:
    """Get all models from a specific manufacturer.

    Args:
        manufacturer: Manufacturer name (e.g., "Siglent", "Keysight")

    Returns:
        List of PSUCapability objects for models from that manufacturer
    """
    return [cap for cap in PSU_MODEL_REGISTRY.values() if cap.manufacturer.lower() == manufacturer.lower()]
