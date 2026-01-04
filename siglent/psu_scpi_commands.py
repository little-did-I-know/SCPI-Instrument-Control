"""SCPI command sets for power supply control.

Provides generic SCPI-99 commands for any compliant power supply,
with Siglent-specific command overrides for SPD series models.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class PSUSCPICommandSet:
    """SCPI command abstraction for power supplies.

    Supports generic SCPI-99 commands with model-specific overrides for
    known manufacturers (e.g., Siglent SPD series).
    """

    # Generic SCPI-99 commands (standard compliant, work with ANY PSU)
    GENERIC_COMMANDS: Dict[str, str] = {
        # System commands (IEEE 488.2)
        "identify": "*IDN?",
        "reset": "*RST",
        "clear_status": "*CLS",
        "get_error": "SYST:ERR?",
        # Voltage control (SCPI-99 standard)
        "set_voltage": "SOUR{ch}:VOLT {voltage}",
        "get_voltage": "SOUR{ch}:VOLT?",
        "set_voltage_limit": "SOUR{ch}:VOLT:PROT {limit}",
        "get_voltage_limit": "SOUR{ch}:VOLT:PROT?",
        # Current control (SCPI-99 standard)
        "set_current": "SOUR{ch}:CURR {current}",
        "get_current": "SOUR{ch}:CURR?",
        "set_current_limit": "SOUR{ch}:CURR:PROT {limit}",
        "get_current_limit": "SOUR{ch}:CURR:PROT?",
        # Output control (SCPI-99 standard)
        "set_output": "OUTP{ch} {state}",
        "get_output": "OUTP{ch}?",
        "set_output_all": "OUTP:ALL {state}",
        # Measurements (SCPI-99 standard)
        "measure_voltage": "MEAS{ch}:VOLT?",
        "measure_current": "MEAS{ch}:CURR?",
        "measure_power": "MEAS{ch}:POW?",
        # Status
        "get_output_mode": "OUTP{ch}:MODE?",  # CV (const voltage) or CC (const current)
    }

    # Siglent SPD series command overrides
    SIGLENT_SPD_OVERRIDES: Dict[str, str] = {
        # Siglent uses CH{ch} prefix instead of SOUR{ch}
        "set_voltage": "CH{ch}:VOLT {voltage}",
        "get_voltage": "CH{ch}:VOLT?",
        "set_current": "CH{ch}:CURR {current}",
        "get_current": "CH{ch}:CURR?",
        # Measurements use MEASure subsystem
        "measure_voltage": "MEASure{ch}:VOLTage?",
        "measure_current": "MEASure{ch}:CURRent?",
        "measure_power": "MEASure{ch}:POWer?",
        # Output control uses specific format
        "set_output": "OUTPut CH{ch},{state}",
        "get_output": "OUTPut? CH{ch}",
        # Advanced Siglent-specific features
        # Timer functionality
        "set_timer_enable": "TIMEr CH{ch},{state}",
        "get_timer_enable": "TIMEr? CH{ch}",
        "set_timer_voltage": "TIMEr:VOLT CH{ch},{voltage}",
        "get_timer_voltage": "TIMEr:VOLT? CH{ch}",
        "set_timer_current": "TIMEr:CURR CH{ch},{current}",
        "get_timer_current": "TIMEr:CURR? CH{ch}",
        # Waveform generation
        "set_wave_enable": "WAVE CH{ch},{state}",
        "get_wave_enable": "WAVE? CH{ch}",
        "set_wave_type": "WAVE:TYPE CH{ch},{wave_type}",  # SINE, SQUARE, etc.
        "get_wave_type": "WAVE:TYPE? CH{ch}",
        "set_wave_freq": "WAVE:FREQ CH{ch},{frequency}",
        "get_wave_freq": "WAVE:FREQ? CH{ch}",
        "set_wave_amplitude": "WAVE:AMPL CH{ch},{amplitude}",
        "get_wave_amplitude": "WAVE:AMPL? CH{ch}",
        # Tracking modes (series/parallel)
        "set_tracking": "OUTP:TRACK {mode}",  # INDEPENDENT, SERIES, PARALLEL
        "get_tracking": "OUTP:TRACK?",
        # Remote sensing
        "set_remote_sense": "SYST:SENS CH{ch},{state}",
        "get_remote_sense": "SYST:SENS? CH{ch}",
    }

    def __init__(self, variant: str = "generic"):
        """Initialize SCPI command set with variant.

        Args:
            variant: Command variant to use ("generic", "siglent_spd")
        """
        self.variant = variant
        logger.info(f"Initialized PSU SCPI command set with variant: {variant}")

    def get_command(self, command_name: str, **kwargs) -> str:
        """Get SCPI command string with parameter substitution.

        Uses model-specific commands if available, falls back to generic.

        Args:
            command_name: Name of the command (e.g., "set_voltage")
            **kwargs: Parameters for command template substitution
                     (e.g., ch=1, voltage=5.0)

        Returns:
            Formatted SCPI command string

        Raises:
            KeyError: If command_name is not found in any command set
            ValueError: If required parameters are missing for substitution

        Example:
            >>> cmd_set = PSUSCPICommandSet("siglent_spd")
            >>> cmd = cmd_set.get_command("set_voltage", ch=1, voltage=5.0)
            >>> print(cmd)
            'CH1:VOLT 5.0'
        """
        # Try model-specific commands first
        if self.variant == "siglent_spd":
            if command_name in self.SIGLENT_SPD_OVERRIDES:
                template = self.SIGLENT_SPD_OVERRIDES[command_name]
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
        if self.variant == "siglent_spd" and command_name in self.SIGLENT_SPD_OVERRIDES:
            return True
        return command_name in self.GENERIC_COMMANDS

    def list_commands(self) -> list:
        """Get list of all available command names for this variant.

        Returns:
            Sorted list of command names
        """
        commands = set(self.GENERIC_COMMANDS.keys())
        if self.variant == "siglent_spd":
            commands.update(self.SIGLENT_SPD_OVERRIDES.keys())
        return sorted(commands)
