"""SCPI command sets for function generator/AWG control.

Provides generic SCPI-99 commands for any compliant arbitrary waveform generator,
with Siglent-specific command overrides for SDG series models.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


def parse_key_value_response(response: str) -> Dict[str, str]:
    """Parse an SDG key-value response into a dict.

    PG02-E05B p.27-28. Responses look like
    "C1:BSWV WVTP,SINE,FRQ,1000HZ,..." or "C1:OUTP ON,LOAD,HZ,PLRT,NOR".
    The "C<n>:<CMD> " header is always present -- CHDR is unavailable on
    SDG1000X/SDG2000X, so it cannot be switched off (availability table p.27).

    The OUTP response leads with a bare state token rather than a key; it is
    returned under the synthetic key "STATE".

    Args:
        response: Raw instrument response.

    Returns:
        Mapping of parameter name to raw value string (units not stripped).

    Raises:
        ValueError: If `response` is empty or carries no payload.
    """
    text = response.strip()
    if not text:
        raise ValueError("empty SDG response")
    if " " in text:
        text = text.split(" ", 1)[1]
    tokens = [t.strip() for t in text.split(",")]
    if not tokens or not tokens[0]:
        raise ValueError(f"no payload in SDG response: {response!r}")

    fields: Dict[str, str] = {}
    start = 0
    if tokens[0].upper() in {"ON", "OFF"}:
        fields["STATE"] = tokens[0].upper()
        start = 1
    for i in range(start, len(tokens) - 1, 2):
        fields[tokens[i].upper()] = tokens[i + 1]
    return fields


class AWGSCPICommandSet:
    """SCPI command abstraction for function generators and arbitrary waveform generators.

    Supports generic SCPI-99 commands with model-specific overrides for
    known manufacturers (e.g., Siglent SDG series).
    """

    # Generic SCPI-99 commands (standard compliant, work with most AWGs)
    GENERIC_COMMANDS: Dict[str, str] = {
        # System commands (IEEE 488.2)
        "identify": "*IDN?",
        "reset": "*RST",
        "clear_status": "*CLS",
        "get_error": "SYST:ERR?",
        # Waveform function selection
        "set_function": "SOUR{ch}:FUNC {function}",
        "get_function": "SOUR{ch}:FUNC?",
        # Frequency control
        "set_frequency": "SOUR{ch}:FREQ {frequency}",
        "get_frequency": "SOUR{ch}:FREQ?",
        # Amplitude control (Vpp)
        "set_amplitude": "SOUR{ch}:VOLT {amplitude}",
        "get_amplitude": "SOUR{ch}:VOLT?",
        # DC offset control
        "set_offset": "SOUR{ch}:VOLT:OFFS {offset}",
        "get_offset": "SOUR{ch}:VOLT:OFFS?",
        # Phase control
        "set_phase": "SOUR{ch}:PHAS {phase}",
        "get_phase": "SOUR{ch}:PHAS?",
        # Output control
        "set_output": "OUTP{ch} {state}",
        "get_output": "OUTP{ch}?",
        # Output impedance/load
        "set_output_load": "OUTP{ch}:LOAD {load}",
        "get_output_load": "OUTP{ch}:LOAD?",
        # Output polarity
        "set_output_polarity": "OUTP{ch}:POL {polarity}",
        "get_output_polarity": "OUTP{ch}:POL?",
        # Pulse waveform specific parameters
        "set_pulse_width": "SOUR{ch}:FUNC:PULS:WIDT {width}",
        "get_pulse_width": "SOUR{ch}:FUNC:PULS:WIDT?",
        "set_pulse_period": "SOUR{ch}:FUNC:PULS:PER {period}",
        "get_pulse_period": "SOUR{ch}:FUNC:PULS:PER?",
        "set_pulse_duty": "SOUR{ch}:FUNC:PULS:DCYC {duty}",
        "get_pulse_duty": "SOUR{ch}:FUNC:PULS:DCYC?",
        # Ramp waveform specific parameters
        "set_ramp_symmetry": "SOUR{ch}:FUNC:RAMP:SYMM {symmetry}",
        "get_ramp_symmetry": "SOUR{ch}:FUNC:RAMP:SYMM?",
    }

    # Siglent SDG series command overrides
    #
    # PG02-E05B p.27-28, p.62: every "get_*" QUERY SYNTAX below is bare -- none
    # of BSWV/OUTP/ARWV/MDWV/BTWV/SWWV documents a per-field selector query.
    # RESPONSE FORMAT always returns the WHOLE parameter list for the
    # subsystem as one comma-joined "KEY,value,KEY,value,..." reply, parsed by
    # `parse_key_value_response`. The "C{ch}:<CMD>? <FIELD>" selector grammar
    # previously used here was invented (audit H5, fixed Task 10).
    SIGLENT_SDG_OVERRIDES: Dict[str, str] = {
        # SDG series uses C{ch} prefix for basic commands
        "set_function": "C{ch}:BSWV WVTP,{function}",
        "get_function": "C{ch}:BSWV?",
        # Frequency using Basic Wave command
        "set_frequency": "C{ch}:BSWV FRQ,{frequency}",
        "get_frequency": "C{ch}:BSWV?",
        # Amplitude using Basic Wave command (in Vpp)
        "set_amplitude": "C{ch}:BSWV AMP,{amplitude}",
        "get_amplitude": "C{ch}:BSWV?",
        # Offset using Basic Wave command
        "set_offset": "C{ch}:BSWV OFST,{offset}",
        "get_offset": "C{ch}:BSWV?",
        # Phase using Basic Wave command (in degrees)
        "set_phase": "C{ch}:BSWV PHSE,{phase}",
        "get_phase": "C{ch}:BSWV?",
        # Pulse duty cycle
        "set_pulse_duty": "C{ch}:BSWV DUTY,{duty}",
        "get_pulse_duty": "C{ch}:BSWV?",
        # Ramp symmetry
        "set_ramp_symmetry": "C{ch}:BSWV SYM,{symmetry}",
        "get_ramp_symmetry": "C{ch}:BSWV?",
        # Output control
        "set_output": "C{ch}:OUTP {state}",
        "get_output": "C{ch}:OUTP?",
        # Output load
        "set_output_load": "C{ch}:OUTP LOAD,{load}",
        "get_output_load": "C{ch}:OUTP?",
        # Output polarity
        "set_output_polarity": "C{ch}:OUTP PLRT,{polarity}",
        "get_output_polarity": "C{ch}:OUTP?",
        # Arbitrary waveform specific (SDG)
        "set_arb_waveform": "C{ch}:ARWV NAME,{name}",
        "get_arb_waveform": "C{ch}:ARWV?",
        # Modulation commands (for future expansion)
        "set_modulation": "C{ch}:MDWV STATE,{state}",
        "get_modulation": "C{ch}:MDWV?",
        # Burst mode commands (for future expansion)
        "set_burst_state": "C{ch}:BTWV STATE,{state}",
        "get_burst_state": "C{ch}:BTWV?",
        # Sweep mode commands (for future expansion)
        "set_sweep_state": "C{ch}:SWWV STATE,{state}",
        "get_sweep_state": "C{ch}:SWWV?",
    }

    def __init__(self, variant: str = "generic"):
        """Initialize SCPI command set with variant.

        Args:
            variant: Command variant to use ("generic", "siglent_sdg")
        """
        self.variant = variant
        logger.info(f"Initialized AWG SCPI command set with variant: {variant}")

    def get_command(self, command_name: str, **kwargs) -> str:
        """Get SCPI command string with parameter substitution.

        Uses model-specific commands if available, falls back to generic.

        Args:
            command_name: Name of the command (e.g., "set_frequency")
            **kwargs: Parameters for command template substitution
                     (e.g., ch=1, frequency=1000.0)

        Returns:
            Formatted SCPI command string

        Raises:
            KeyError: If command_name is not found in any command set
            ValueError: If required parameters are missing for substitution

        Example:
            >>> cmd_set = AWGSCPICommandSet("siglent_sdg")
            >>> cmd = cmd_set.get_command("set_frequency", ch=1, frequency=1000.0)
            >>> print(cmd)
            'C1:BSWV FRQ,1000.0'
        """
        # Try model-specific commands first
        if self.variant == "siglent_sdg":
            if command_name in self.SIGLENT_SDG_OVERRIDES:
                template = self.SIGLENT_SDG_OVERRIDES[command_name]
                try:
                    return template.format(**kwargs)
                except KeyError as e:
                    raise ValueError(f"Missing required parameter for command '{command_name}': {e}")

        # Fall back to generic SCPI commands
        if command_name in self.GENERIC_COMMANDS:
            template = self.GENERIC_COMMANDS[command_name]
            try:
                return template.format(**kwargs)
            except KeyError as e:
                raise ValueError(f"Missing required parameter for command '{command_name}': {e}")

        # Command not found in any set
        raise KeyError(f"Unknown command: '{command_name}' for variant '{self.variant}'")

    def supports_command(self, command_name: str) -> bool:
        """Check if a command is supported by this variant.

        Args:
            command_name: Name of the command to check

        Returns:
            True if command is supported, False otherwise
        """
        if self.variant == "siglent_sdg" and command_name in self.SIGLENT_SDG_OVERRIDES:
            return True
        return command_name in self.GENERIC_COMMANDS

    def list_commands(self) -> list:
        """Get list of all available command names for this variant.

        Returns:
            Sorted list of command names
        """
        commands = set(self.GENERIC_COMMANDS.keys())
        if self.variant == "siglent_sdg":
            commands.update(self.SIGLENT_SDG_OVERRIDES.keys())
        return sorted(commands)
