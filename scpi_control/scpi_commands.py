"""SCPI command abstraction layer for different Siglent oscilloscope models.

Two wire dialects exist across Siglent scope generations:
- "legacy": the LeCroy-derived flat dialect (TRIG_SELECT, TDIV, C1:VDIV) spoken
  by SDS1000X-E era scopes.
- "modern": colon-form SCPI (:TRIGger:EDGE:SOURce, :TIMebase:SCALe) documented
  in the SDS Series Programming Guide EN11G for HD/Plus/SDS5000X+ scopes.

This module holds the per-dialect command tables and the enum conversions
between the library's public vocabulary and each dialect's wire tokens.
"""

import re
from typing import Dict

# Wire dialects with a command table. Grows as vendor tables land.
SUPPORTED_DIALECTS = ("legacy", "modern")

# IEEE-488.2 mandated common commands, identical on every instrument.
IEEE488_BASE = {
    "identify": "*IDN?",
    "reset": "*RST",
    "clear_status": "*CLS",
    "operation_complete": "*OPC?",
}

# Commands written once right after connect-time dialect resolution.
# legacy: response headers off (Siglent legacy echoes headers by default)
# modern: nothing needed
CONNECT_SETUP = {
    "legacy": ["CHDR OFF"],
    "modern": [],
}


class SCPICommandSet:
    """Per-model SCPI command table (dialect base + family overrides)."""

    LEGACY_COMMANDS = {
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
        # Measurements
        # NOTE: get_parameter_value's wire form is "PAVA? {param},C{ch}" (mtype
        # first, then a C-prefixed channel) -- this is what measurement.py
        # actually sent pre-refactor and what the legacy mock's PAVA? regex
        # parses; do not "correct" it to "C{ch}:PAVA? {param}".
        "get_parameter_value": "PAVA? {param},C{ch}",
        "add_measurement": "PACU {mtype},C{ch}",
        "set_statistics": "PAST {state}",
        "clear_measurements": "PACL",
        "reset_statistics": "PASTAT RESET",
        # Cursor control
        "set_cursor_type": "CRST {type}",
        "get_cursor_type": "CRST?",
        # NOTE: bare query -- no cursor id is ever passed by measurement.py.
        "get_cursor_value": "CRVA?",
        # Trigger holdoff (AUDIT M4: TRIG_DELAY is really trigger delay, not
        # holdoff; legacy-only, routing deferred to a trigger-rework follow-up)
        "set_trigger_holdoff": "TRIG_DELAY {t}",
        "get_trigger_holdoff": "TRIG_DELAY?",
        # Channel vertical unit (legacy-only)
        "set_channel_unit": "C{ch}:UNIT {unit}",
        "get_channel_unit": "C{ch}:UNIT?",
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
        # Measurements — get_parameter_value stays available (measure() keeps
        # working on modern, a documented gap); statistics/cursors/holdoff/unit
        # are legacy-only and intentionally absent so they gate cleanly.
        "get_parameter_value": "C{ch}:PAVA? {param}",
        # Screen capture (legacy strings accepted on modern scopes today; revisit with screen-capture overhaul)
        "screen_dump": "SCDP",
        "set_hardcopy_format": "HCSU DEV,FORMAT,{format}",
        "hardcopy_print": "HCSU PRINT",
    }

    # Dialect base tables, keyed by dialect name. Tek/LeCroy tables added later.
    DIALECT_TABLES = {
        "legacy": LEGACY_COMMANDS,
        "modern": MODERN_COMMANDS,
    }

    # Family overrides applied on top of the dialect base table.
    VARIANT_OVERRIDES: Dict[str, Dict[str, str]] = {
        "standard": {},
        "hd_series": {},
        "x_series": {},  # HCSU? screen-dump override removed: it was a hardcopy SETUP query, not a dump
        "plus_series": {},
    }

    def __init__(self, dialect: str = "legacy", scpi_variant: str = "standard"):
        """Build the command set for a dialect + model family.

        Args:
            dialect: wire dialect (one of SUPPORTED_DIALECTS) — selects the base table
            scpi_variant: family identifier ("standard", "hd_series", "x_series", "plus_series") for overrides
        """
        if dialect not in SUPPORTED_DIALECTS:
            raise ValueError(f"Unknown SCPI dialect: {dialect}. Must be one of {SUPPORTED_DIALECTS}.")
        self.dialect = dialect
        self.scpi_variant = scpi_variant
        self._command_set = self._build_command_set(dialect, scpi_variant)

    def _build_command_set(self, dialect: str, variant: str) -> Dict[str, str]:
        command_set = dict(IEEE488_BASE)
        command_set.update(self.DIALECT_TABLES[dialect])
        command_set.update(self.VARIANT_OVERRIDES.get(variant, {}))
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
# slopes POS|NEG|WINDOW, coupling DC|AC|GND, sources C1..C4|EX|EX5|LINE.
# These tables convert at the dialect boundary and are the only place wire
# enums are spelled out. A missing (dialect, token) pair means the dialect
# cannot express that public token -> FeatureNotSupportedError.

from scpi_control import exceptions

# Dialects whose trigger commands are per-source-prefixed (C1:TRLV ...) rather
# than global (:TRIGger:EDGE:LEVel ...). These also have a STOP trigger-mode
# wire token; the global-style dialects detect STOP via acquisition status.
FLAT_TRIGGER_DIALECTS = frozenset({"legacy"})

# Dialects whose numeric queries return a bare NR3 value with no unit suffix.
BARE_NR3_DIALECTS = frozenset({"modern"})


def is_flat_trigger(dialect: str) -> bool:
    return dialect in FLAT_TRIGGER_DIALECTS


_MODE_TO_WIRE = {
    "legacy": {"AUTO": "AUTO", "NORM": "NORM", "SINGLE": "SINGLE", "STOP": "STOP"},
    "modern": {"AUTO": "AUTO", "NORM": "NORMal", "SINGLE": "SINGle"},
}
_MODE_FROM_WIRE = {
    "legacy": {"AUTO": "AUTO", "NORM": "NORM", "SINGLE": "SINGLE", "STOP": "STOP"},
    "modern": {"AUTO": "AUTO", "NORMAL": "NORM", "SINGLE": "SINGLE", "FTRIG": "AUTO"},
}
_SLOPE_TO_WIRE = {
    "legacy": {"POS": "POS", "NEG": "NEG", "WINDOW": "WINDOW"},
    "modern": {"POS": "RISing", "NEG": "FALLing", "WINDOW": "ALTernate"},
}
_SLOPE_FROM_WIRE = {
    "legacy": {"POS": "POS", "NEG": "NEG", "WINDOW": "WINDOW"},
    "modern": {"RISING": "POS", "FALLING": "NEG", "ALTERNATE": "WINDOW"},
}
_COUPLING_TO_WIRE = {
    "legacy": {"DC": "D1M", "AC": "A1M", "GND": "GND"},
    "modern": {"DC": "DC", "AC": "AC", "GND": "GND"},
}
_COUPLING_FROM_WIRE = {
    "legacy": {"D1M": "DC", "A1M": "AC", "D50": "DC", "A50": "AC", "GND": "GND"},
    "modern": {"DC": "DC", "AC": "AC", "GND": "GND"},
}

_PUBLIC_MODES = {"AUTO", "NORM", "SINGLE", "STOP"}
_PUBLIC_SLOPES = {"POS", "NEG", "WINDOW"}
_PUBLIC_COUPLINGS = {"DC", "AC", "GND"}

# Acquisition-status vocabulary shared by every dialect's status query.
_STATUS_MAP = {"ARM": "ARM", "ARMED": "ARM", "READY": "READY", "AUTO": "AUTO", "TRIG'D": "TRIGD", "STOP": "STOP", "ROLL": "ROLL"}


def _last_token(raw: str) -> str:
    return raw.strip().split()[-1].upper() if raw.strip() else ""


def _to_wire(table, public_values, dialect: str, token: str, what: str) -> str:
    token = token.upper()
    if token not in public_values:
        raise ValueError(f"Invalid {what}: {token}. Must be one of {sorted(public_values)}.")
    try:
        return table[dialect][token]
    except KeyError:
        raise exceptions.FeatureNotSupportedError(f"{what} {token} is not supported on the {dialect} dialect")


def _from_wire(table, dialect: str, raw: str, what: str) -> str:
    token = _last_token(raw)
    try:
        return table[dialect][token]
    except KeyError:
        raise ValueError(f"Unrecognized {dialect} {what} response: {raw!r}")


# Public measurement vocabulary (PAVA parameter names). Identity for Siglent
# dialects; vendor dialects map or reject per their manuals.
_MEASUREMENT_TYPES = {"PKPK", "MAX", "MIN", "AMPL", "TOP", "BASE", "CMEAN", "MEAN", "RMS", "CRMS", "FREQ", "PER", "RISE", "FALL", "WID", "NWID", "DUTY"}
_MEASUREMENT_TO_WIRE = {
    "legacy": {m: m for m in _MEASUREMENT_TYPES},
    "modern": {m: m for m in _MEASUREMENT_TYPES},
}


def measurement_to_wire(dialect: str, mtype: str) -> str:
    """Convert a public measurement type to the dialect's wire token."""
    return _to_wire(_MEASUREMENT_TO_WIRE, _MEASUREMENT_TYPES, dialect, mtype, "measurement type")


def mode_to_wire(dialect: str, mode: str) -> str:
    """Convert a public trigger mode to the wire token.

    STOP is only a wire mode on flat-trigger dialects; global-style dialects
    implement it via their stop command, and callers handle it before converting.
    """
    return _to_wire(_MODE_TO_WIRE, _PUBLIC_MODES, dialect, mode, "trigger mode")


def mode_from_wire(dialect: str, raw: str) -> str:
    """Normalize a trigger-mode query response to AUTO|NORM|SINGLE|STOP."""
    return _from_wire(_MODE_FROM_WIRE, dialect, raw, "trigger mode")


def slope_to_wire(dialect: str, slope: str) -> str:
    return _to_wire(_SLOPE_TO_WIRE, _PUBLIC_SLOPES, dialect, slope, "trigger slope")


def slope_from_wire(dialect: str, raw: str) -> str:
    return _from_wire(_SLOPE_FROM_WIRE, dialect, raw, "trigger slope")


def coupling_to_wire(dialect: str, coupling: str) -> str:
    return _to_wire(_COUPLING_TO_WIRE, _PUBLIC_COUPLINGS, dialect, coupling, "coupling mode")


def coupling_from_wire(dialect: str, raw: str) -> str:
    return _from_wire(_COUPLING_FROM_WIRE, dialect, raw, "coupling mode")


def channel_token(dialect: str, source) -> str:
    """Convert a public channel source (int, 'C2', 'EX', 'LINE') to the wire token."""
    if isinstance(source, int):
        number = source
    else:
        token = str(source).strip().upper()
        match = re.fullmatch(r"C(?:H)?(\d+)", token)
        if not match:
            return token  # EX, EX5, LINE and friends pass through
        number = int(match.group(1))
    return f"CH{number}" if dialect == "tektronix" else f"C{number}"


def source_from_wire(dialect: str, raw: str) -> str:
    """Normalize a trigger-source query response to the public vocabulary."""
    token = raw.strip().upper()
    match = re.fullmatch(r"C(?:H)?(\d+)", token)
    if match:
        return f"C{int(match.group(1))}"
    return token


def normalize_status(raw: str) -> str:
    """Normalize an acquisition-status response to ARM|READY|AUTO|TRIGD|STOP|ROLL."""
    token = _last_token(raw)
    if token not in _STATUS_MAP:
        raise ValueError(f"Unrecognized acquisition status response: {raw!r}")
    return _STATUS_MAP[token]
