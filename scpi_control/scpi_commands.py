"""SCPI command abstraction layer for different Siglent oscilloscope models.

Two wire dialects exist across Siglent scope generations:
- "legacy": the LeCroy-derived flat dialect (TRIG_SELECT, TDIV, C1:VDIV) spoken
  by SDS1000X-E era scopes.
- "modern": colon-form SCPI (:TRIGger:EDGE:SOURce, :TIMebase:SCALe) documented
  in the SDS Series Programming Guide EN11G for HD/Plus/SDS5000X+ scopes.

This module holds the per-dialect command tables and the enum conversions
between the library's public vocabulary and each dialect's wire tokens.
"""

from typing import Dict


class SCPICommandSet:
    """Per-model SCPI command table (dialect base + family overrides)."""

    LEGACY_COMMANDS = {
        # Identification and system
        "identify": "*IDN?",
        "reset": "*RST",
        "clear_status": "*CLS",
        "operation_complete": "*OPC?",
        # Trigger control
        "set_trigger_mode": "TRIG_MODE {mode}",  # mode: AUTO, NORM, SINGLE, STOP
        "get_trigger_mode": "TRIG_MODE?",
        "arm_trigger": "ARM",
        "force_trigger": "FRTR",
        "stop": "STOP",
        "run": "TRIG_MODE AUTO",
        "get_acq_status": "SAST?",
        # Auto setup
        "auto_setup": "ASET",
        # Channel control
        "set_channel_display": "C{ch}:TRA {state}",
        "get_channel_display": "C{ch}:TRA?",
        "set_voltage_div": "C{ch}:VDIV {vdiv}",
        "get_voltage_div": "C{ch}:VDIV?",
        "set_voltage_offset": "C{ch}:OFST {offset}",
        "get_voltage_offset": "C{ch}:OFST?",
        "set_coupling": "C{ch}:CPL {coupling}",  # coupling wire tokens: A1M, D1M, GND
        "get_coupling": "C{ch}:CPL?",
        "set_probe_ratio": "C{ch}:ATTN {ratio}",
        "get_probe_ratio": "C{ch}:ATTN?",
        "set_bandwidth_limit": "C{ch}:BWL {limit}",  # limit: ON, OFF
        "get_bandwidth_limit": "C{ch}:BWL?",
        # Timebase control
        "set_time_div": "TDIV {tdiv}",
        "get_time_div": "TDIV?",
        "set_time_offset": "TRDL {offset}",
        "get_time_offset": "TRDL?",
        "get_sample_rate": "SARA?",
        # Trigger settings
        "set_trigger_select": "TRIG_SELECT {type},SR,{src}",
        "get_trigger_select": "TRIG_SELECT?",
        "set_trigger_level": "{src}:TRLV {level}",
        "get_trigger_level": "{src}:TRLV?",
        "set_trigger_slope": "{src}:TRSL {slope}",
        "get_trigger_slope": "{src}:TRSL?",
        "set_trigger_coupling": "{src}:TRCP {coupling}",
        "get_trigger_coupling": "{src}:TRCP?",
        # Waveform acquisition (transfer path unchanged until the waveform
        # sub-project; the DAT2 path works on both scope generations)
        "get_waveform": "C{ch}:WF? DAT2",
        "get_waveform_preamble": "C{ch}:WF? DESC",
        # Measurements (routing deferred to the waveform/measurement sub-project)
        "get_parameter_value": "C{ch}:PAVA? {param}",
        "clear_measurements": "PACU CLEAR",
        # Cursor control
        "set_cursor_type": "CRST {type}",
        "get_cursor_type": "CRST?",
        "get_cursor_value": "CRVA? {cursor}",
        # Math operations (basic)
        "set_math_display": "MATH{n}:TRA {state}",
        "get_math_display": "MATH{n}:TRA?",
        # Screen capture
        "screen_dump": "SCDP",
        "set_hardcopy_format": "HCSU DEV,FORMAT,{format}",
        "hardcopy_print": "HCSU PRINT",
    }

    # Modern colon-form dialect, verbatim from the SDS Series Programming
    # Guide EN11G (page references in the design spec's command table).
    MODERN_COMMANDS = {
        # Identification and system
        "identify": "*IDN?",
        "reset": "*RST",
        "clear_status": "*CLS",
        "operation_complete": "*OPC?",
        # Trigger control (p.482-484; no standalone ARM/force — FTRIG forces)
        "set_trigger_mode": ":TRIGger:MODE {mode}",  # wire modes: AUTO, NORMal, SINGle, FTRIG
        "get_trigger_mode": ":TRIGger:MODE?",
        "force_trigger": ":TRIGger:MODE FTRIG",
        "stop": ":TRIGger:STOP",
        "run": ":TRIGger:RUN",
        "get_acq_status": ":TRIGger:STATus?",
        # Auto setup (p.33, command-only)
        "auto_setup": ":AUToset",
        # Channel control (p.50-60)
        "set_channel_display": ":CHANnel{ch}:SWITch {state}",
        "get_channel_display": ":CHANnel{ch}:SWITch?",
        "set_voltage_div": ":CHANnel{ch}:SCALe {vdiv}",
        "get_voltage_div": ":CHANnel{ch}:SCALe?",
        "set_voltage_offset": ":CHANnel{ch}:OFFSet {offset}",
        "get_voltage_offset": ":CHANnel{ch}:OFFSet?",
        "set_coupling": ":CHANnel{ch}:COUPling {coupling}",  # coupling wire tokens: DC, AC, GND
        "get_coupling": ":CHANnel{ch}:COUPling?",
        "set_probe_ratio": ":CHANnel{ch}:PROBe VALue,{ratio}",
        "get_probe_ratio": ":CHANnel{ch}:PROBe?",
        "set_bandwidth_limit": ":CHANnel{ch}:BWLimit {limit}",  # limit: FULL, 20M, 200M
        "get_bandwidth_limit": ":CHANnel{ch}:BWLimit?",
        # Timebase control (p.473-476)
        "set_time_div": ":TIMebase:SCALe {tdiv}",
        "get_time_div": ":TIMebase:SCALe?",
        "set_time_offset": ":TIMebase:DELay {offset}",
        "get_time_offset": ":TIMebase:DELay?",
        "get_sample_rate": ":ACQuire:SRATe?",  # p.46
        # Trigger settings (p.484-495)
        "set_trigger_type": ":TRIGger:TYPE {type}",
        "get_trigger_type": ":TRIGger:TYPE?",
        "set_trigger_source": ":TRIGger:EDGE:SOURce {src}",
        "get_trigger_source": ":TRIGger:EDGE:SOURce?",
        "set_trigger_level": ":TRIGger:EDGE:LEVel {level}",
        "get_trigger_level": ":TRIGger:EDGE:LEVel?",
        "set_trigger_slope": ":TRIGger:EDGE:SLOPe {slope}",  # wire slopes: RISing, FALLing, ALTernate
        "get_trigger_slope": ":TRIGger:EDGE:SLOPe?",
        "set_trigger_coupling": ":TRIGger:EDGE:COUPling {coupling}",
        "get_trigger_coupling": ":TRIGger:EDGE:COUPling?",
        # Waveform acquisition — unchanged until the waveform sub-project
        "get_waveform": "C{ch}:WF? DAT2",
        "get_waveform_preamble": "C{ch}:WF? DESC",
        # Measurements — routing deferred to the waveform/measurement sub-project
        "get_parameter_value": "C{ch}:PAVA? {param}",
        "clear_measurements": "PACU CLEAR",
        # Screen capture (legacy strings accepted on modern scopes today; revisit with screen-capture overhaul)
        "screen_dump": "SCDP",
        "set_hardcopy_format": "HCSU DEV,FORMAT,{format}",
        "hardcopy_print": "HCSU PRINT",
    }

    # Family overrides applied on top of the dialect base table.
    HD_SERIES_OVERRIDES: Dict[str, str] = {}
    X_SERIES_OVERRIDES: Dict[str, str] = {}  # HCSU? screen-dump override removed: it was a hardcopy SETUP query, not a dump
    PLUS_SERIES_OVERRIDES: Dict[str, str] = {}
    STANDARD_OVERRIDES: Dict[str, str] = {}

    def __init__(self, dialect: str = "legacy", scpi_variant: str = "standard"):
        """Build the command set for a dialect + model family.

        Args:
            dialect: "legacy" or "modern" — selects the base table
            scpi_variant: family identifier ("standard", "hd_series", "x_series", "plus_series") for overrides
        """
        if dialect not in ("legacy", "modern"):
            raise ValueError(f"Unknown SCPI dialect: {dialect}. Must be 'legacy' or 'modern'.")
        self.dialect = dialect
        self.scpi_variant = scpi_variant
        self._command_set = self._build_command_set(dialect, scpi_variant)

    def _build_command_set(self, dialect: str, variant: str) -> Dict[str, str]:
        command_set = (self.LEGACY_COMMANDS if dialect == "legacy" else self.MODERN_COMMANDS).copy()
        overrides = {
            "hd_series": self.HD_SERIES_OVERRIDES,
            "x_series": self.X_SERIES_OVERRIDES,
            "plus_series": self.PLUS_SERIES_OVERRIDES,
            "standard": self.STANDARD_OVERRIDES,
        }.get(variant, {})
        command_set.update(overrides)
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
        return f"SCPICommandSet(dialect='{self.dialect}', variant='{self.scpi_variant}', commands={len(self._command_set)})"


# ---- Public-vocabulary <-> wire-token conversions -------------------------
# The library's public API always speaks: modes AUTO|NORM|SINGLE|STOP,
# slopes POS|NEG|WINDOW, coupling DC|AC|GND. These helpers convert at the
# dialect boundary and are the only place wire enums are spelled out.

_MODE_TO_MODERN = {"AUTO": "AUTO", "NORM": "NORMal", "SINGLE": "SINGle"}
_MODE_FROM_MODERN = {"AUTO": "AUTO", "NORMAL": "NORM", "SINGLE": "SINGLE", "FTRIG": "AUTO"}
_LEGACY_MODES = {"AUTO", "NORM", "SINGLE", "STOP"}

_SLOPE_TO_MODERN = {"POS": "RISing", "NEG": "FALLing", "WINDOW": "ALTernate"}
_SLOPE_FROM_MODERN = {"RISING": "POS", "FALLING": "NEG", "ALTERNATE": "WINDOW"}
_LEGACY_SLOPES = {"POS", "NEG", "WINDOW"}

_COUPLING_TO_LEGACY = {"DC": "D1M", "AC": "A1M", "GND": "GND"}
_COUPLING_FROM_LEGACY = {"D1M": "DC", "A1M": "AC", "D50": "DC", "A50": "AC", "GND": "GND"}
_MODERN_COUPLINGS = {"DC", "AC", "GND"}

# :TRIGger:STATus? enum (guide p.483) plus legacy SAST? responses share this space
_STATUS_MAP = {"ARM": "ARM", "ARMED": "ARM", "READY": "READY", "AUTO": "AUTO", "TRIG'D": "TRIGD", "STOP": "STOP", "ROLL": "ROLL"}


def mode_to_wire(dialect: str, mode: str) -> str:
    """Convert a public trigger mode (AUTO|NORM|SINGLE) to the wire token.

    STOP is not a wire mode on the modern dialect (it is the :TRIGger:STOP
    command); callers handle it before converting.
    """
    mode = mode.upper()
    if dialect == "legacy":
        if mode not in _LEGACY_MODES:
            raise ValueError(f"Invalid trigger mode: {mode}")
        return mode
    if mode not in _MODE_TO_MODERN:
        raise ValueError(f"Invalid trigger mode for modern dialect: {mode}")
    return _MODE_TO_MODERN[mode]


def mode_from_wire(dialect: str, raw: str) -> str:
    """Normalize a trigger-mode query response to AUTO|NORM|SINGLE|STOP."""
    token = raw.strip().split()[-1].upper() if raw.strip() else ""
    if dialect == "legacy":
        if token not in _LEGACY_MODES:
            raise ValueError(f"Unrecognized legacy trigger mode response: {raw!r}")
        return token
    if token not in _MODE_FROM_MODERN:
        raise ValueError(f"Unrecognized modern trigger mode response: {raw!r}")
    return _MODE_FROM_MODERN[token]


def slope_to_wire(dialect: str, slope: str) -> str:
    slope = slope.upper()
    if slope not in _LEGACY_SLOPES:
        raise ValueError(f"Invalid trigger slope: {slope}. Must be POS, NEG, or WINDOW.")
    return slope if dialect == "legacy" else _SLOPE_TO_MODERN[slope]


def slope_from_wire(dialect: str, raw: str) -> str:
    token = raw.strip().split()[-1].upper() if raw.strip() else ""
    if dialect == "legacy":
        if token not in _LEGACY_SLOPES:
            raise ValueError(f"Unrecognized legacy slope response: {raw!r}")
        return token
    if token not in _SLOPE_FROM_MODERN:
        raise ValueError(f"Unrecognized modern slope response: {raw!r}")
    return _SLOPE_FROM_MODERN[token]


def coupling_to_wire(dialect: str, coupling: str) -> str:
    coupling = coupling.upper()
    if coupling not in _MODERN_COUPLINGS:
        raise ValueError(f"Invalid coupling mode: {coupling}. Must be DC, AC, or GND.")
    return _COUPLING_TO_LEGACY[coupling] if dialect == "legacy" else coupling


def coupling_from_wire(dialect: str, raw: str) -> str:
    token = raw.strip().split()[-1].upper() if raw.strip() else ""
    if dialect == "legacy":
        if token not in _COUPLING_FROM_LEGACY:
            raise ValueError(f"Unrecognized legacy coupling response: {raw!r}")
        return _COUPLING_FROM_LEGACY[token]
    if token not in _MODERN_COUPLINGS:
        raise ValueError(f"Unrecognized modern coupling response: {raw!r}")
    return token


def normalize_status(raw: str) -> str:
    """Normalize an acquisition-status response to ARM|READY|AUTO|TRIGD|STOP|ROLL.

    Accepts modern ':TRIGger:STATus?' responses (Arm|Ready|Auto|Trig'd|Stop|Roll,
    guide p.483) and legacy 'SAST?' responses, with or without the 'SAST ' echo.
    """
    token = raw.strip().split()[-1].upper() if raw.strip() else ""
    if token not in _STATUS_MAP:
        raise ValueError(f"Unrecognized acquisition status response: {raw!r}")
    return _STATUS_MAP[token]
