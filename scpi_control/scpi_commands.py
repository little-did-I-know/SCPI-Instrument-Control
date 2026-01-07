"""SCPI command abstraction layer for different Siglent oscilloscope models.

This module provides model-specific SCPI command routing to handle variations
in command syntax across different oscilloscope series.
"""

from typing import Any, Dict


class SCPICommandSet:
    """SCPI command abstraction layer.

    Provides a unified interface for SCPI commands while handling model-specific
    variations in command syntax.
    """

    # Base commands common to all Siglent oscilloscopes
    BASE_COMMANDS = {
        # Identification and system
        "identify": "*IDN?",
        "reset": "*RST",
        "clear_status": "*CLS",
        "operation_complete": "*OPC?",
        "get_error": "SYST:ERR?",
        # Trigger control
        "set_trigger_mode": "TRIG_MODE {mode}",  # mode: AUTO, NORM, SINGLE, STOP
        "get_trigger_mode": "TRIG_MODE?",
        "arm_trigger": "ARM",
        "force_trigger": "FRTR",
        "stop": "STOP",
        "run": "TRIG_MODE AUTO",  # Equivalent to run/start
        # Auto setup
        "auto_setup": "ASET",
        # Channel control
        "set_channel_display": "C{ch}:TRA {state}",  # state: ON, OFF
        "get_channel_display": "C{ch}:TRA?",
        "set_voltage_div": "C{ch}:VDIV {vdiv}",
        "get_voltage_div": "C{ch}:VDIV?",
        "set_voltage_offset": "C{ch}:OFST {offset}",
        "get_voltage_offset": "C{ch}:OFST?",
        "set_coupling": "C{ch}:CPL {coupling}",  # coupling: DC, AC, GND
        "get_coupling": "C{ch}:CPL?",
        "set_probe_ratio": "C{ch}:ATTN {ratio}",
        "get_probe_ratio": "C{ch}:ATTN?",
        "set_bandwidth_limit": "C{ch}:BWL {state}",  # state: ON, OFF
        "get_bandwidth_limit": "C{ch}:BWL?",
        # Timebase control
        "set_time_div": "TDIV {tdiv}",
        "get_time_div": "TDIV?",
        "set_time_offset": "TRDL {offset}",
        "get_time_offset": "TRDL?",
        "get_sample_rate": "SARA?",
        # Trigger settings
        "set_trigger_select": "TRIG_SELECT {type},{src}",  # type: EDGE, SLEW, etc.
        "get_trigger_select": "TRIG_SELECT?",
        "set_trigger_level": "{src}:TRLV {level}",  # src: C1, C2, C3, C4, EX, etc.
        "get_trigger_level": "{src}:TRLV?",
        "set_trigger_slope": "{src}:TRSL {slope}",  # slope: POS, NEG, WINDOW
        "get_trigger_slope": "{src}:TRSL?",
        "set_trigger_coupling": "{src}:TRCP {coupling}",
        "get_trigger_coupling": "{src}:TRCP?",
        # Waveform acquisition - note: HD series uses DAT2, others may use different format
        "get_waveform": "C{ch}:WF? DAT2",
        "get_waveform_preamble": "C{ch}:WF? DESC",
        # Measurements
        "get_parameter_value": "C{ch}:PAVA? {param}",  # param: PKPK, FREQ, etc.
        "clear_measurements": "PACU CLEAR",
        # Cursor control
        "set_cursor_type": "CRST {type}",  # type: OFF, HREL, VREL, HREF, VREF
        "get_cursor_type": "CRST?",
        "get_cursor_value": "CRVA? {cursor}",  # cursor: TRDELTA, TRALPHA, etc.
        # Math operations (basic)
        "set_math_display": "MATH{n}:TRA {state}",
        "get_math_display": "MATH{n}:TRA?",
        # Screen capture
        "screen_dump": "SCDP",  # Get screen image
        "set_hardcopy_format": "HCSU DEV,FORMAT,{format}",  # format: PNG, BMP, JPEG
        "hardcopy_print": "HCSU PRINT",
    }

    # HD Series specific overrides (SDS800X HD)
    HD_SERIES_OVERRIDES = {
        "get_waveform": "C{ch}:WF? DAT2",  # HD series uses DAT2 format
        "screen_dump": "SCDP",  # Screen dump command
    }

    # X Series specific overrides (SDS1000X-E, SDS5000X)
    X_SERIES_OVERRIDES = {
        "get_waveform": "C{ch}:WF? DAT2",  # X series also uses DAT2
        # Some X series models may use different screen capture commands
        "screen_dump": "HCSU?",
    }

    # Plus Series specific overrides (SDS2000X Plus)
    PLUS_SERIES_OVERRIDES = {
        "get_waveform": "C{ch}:WF? DAT2",
        "screen_dump": "SCDP",
    }

    # Standard fallback for unknown models
    STANDARD_OVERRIDES = {}

    def __init__(self, scpi_variant: str = "standard"):
        """Initialize SCPI command set with model-specific variant.

        Args:
            scpi_variant: SCPI command variant ("standard", "hd_series", "x_series", "plus_series")
        """
        self.scpi_variant = scpi_variant
        self._command_set = self._build_command_set(scpi_variant)

    def _build_command_set(self, variant: str) -> Dict[str, str]:
        """Build complete command set with variant-specific overrides.

        Args:
            variant: SCPI variant identifier

        Returns:
            Dictionary of command name to SCPI command string
        """
        # Start with base commands
        command_set = self.BASE_COMMANDS.copy()

        # Apply variant-specific overrides
        if variant == "hd_series":
            command_set.update(self.HD_SERIES_OVERRIDES)
        elif variant == "x_series":
            command_set.update(self.X_SERIES_OVERRIDES)
        elif variant == "plus_series":
            command_set.update(self.PLUS_SERIES_OVERRIDES)
        elif variant == "standard":
            command_set.update(self.STANDARD_OVERRIDES)

        return command_set

    def get_command(self, command_name: str, **kwargs) -> str:
        """Get SCPI command string with parameter substitution.

        Args:
            command_name: Name of the command (e.g., "set_voltage_div")
            **kwargs: Parameters to substitute in the command template
                     Common parameters:
                     - ch: Channel number (1-4)
                     - mode: Mode value
                     - state: State value (ON/OFF)
                     - vdiv: Voltage division
                     - etc.

        Returns:
            Formatted SCPI command string

        Raises:
            KeyError: If command_name is not in the command set

        Example:
            >>> cmd_set = SCPICommandSet("hd_series")
            >>> cmd_set.get_command("set_voltage_div", ch=1, vdiv="1V")
            'C1:VDIV 1V'
        """
        if command_name not in self._command_set:
            raise KeyError(f"Unknown command: {command_name}")

        command_template = self._command_set[command_name]

        # Substitute parameters if any
        if kwargs:
            try:
                return command_template.format(**kwargs)
            except KeyError as e:
                raise ValueError(f"Missing required parameter for command '{command_name}': {e}")

        return command_template

    def has_command(self, command_name: str) -> bool:
        """Check if a command is available in this command set.

        Args:
            command_name: Name of the command to check

        Returns:
            True if command exists, False otherwise
        """
        return command_name in self._command_set

    def list_commands(self) -> list:
        """Get list of all available command names.

        Returns:
            List of command names
        """
        return sorted(self._command_set.keys())

    def add_custom_command(self, command_name: str, command_template: str) -> None:
        """Add or override a command in the command set.

        This is useful for adding model-specific commands or user extensions.

        Args:
            command_name: Name for the command
            command_template: SCPI command template string
        """
        self._command_set[command_name] = command_template

    def __repr__(self) -> str:
        """String representation."""
        return f"SCPICommandSet(variant='{self.scpi_variant}', commands={len(self._command_set)})"
