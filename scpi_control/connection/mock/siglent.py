"""Siglent scope personality: legacy (SDS1000/2000-style) and modern (SDS800X HD-style)
write/query dialects, plus the waveform-response builder."""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

from scpi_control.connection.mock.helpers import _build_ieee_block, _format_nr3, _format_scientific
from scpi_control.connection.mock import synth as mock_synth

# Canonical PAVA? measurement values for the legacy dialect (mirrors real
# hardware where PAVA? is legacy-only; the modern dialect has no equivalent).
_MOCK_PAVA_VALUES: Dict[str, Tuple[str, str]] = {
    "PKPK": ("2.000E+00", "V"),
    "MAX": ("1.000E+00", "V"),
    "MIN": ("-1.000E+00", "V"),
    "AMPL": ("2.000E+00", "V"),
    "TOP": ("1.000E+00", "V"),
    "BASE": ("-1.000E+00", "V"),
    "CMEAN": ("0.000E+00", "V"),
    "MEAN": ("0.000E+00", "V"),
    "RMS": ("7.070E-01", "V"),
    "CRMS": ("7.070E-01", "V"),
    "FREQ": ("1.000E+03", "HZ"),
    "PER": ("1.000E-03", "S"),
    "RISE": ("3.500E-05", "S"),
    "FALL": ("3.500E-05", "S"),
    "WID": ("5.000E-04", "S"),
    "NWID": ("5.000E-04", "S"),
    "DUTY": ("5.000E+01", "%"),
}


def handle_write(conn, command: str) -> bool:
    """Handle a Siglent-dialect (legacy or modern) scope write. Returns True if consumed."""
    if conn.scope_dialect == "modern":
        if match := re.match(r":CHANnel(\d+):SWITch\s+(ON|OFF)", command, re.IGNORECASE):
            conn._channel_enabled[int(match.group(1))] = match.group(2).upper() == "ON"
            return True
        if match := re.match(r":CHANnel(\d+):SCALe\s+(.+)", command, re.IGNORECASE):
            ch = int(match.group(1))
            conn._voltage_scales[ch] = float(match.group(2))
            conn.scale_updates.setdefault(ch, []).append(float(match.group(2)))
            return True
        if match := re.match(r":CHANnel(\d+):OFFSet\s+(.+)", command, re.IGNORECASE):
            conn._voltage_offsets[int(match.group(1))] = float(match.group(2))
            return True
        if match := re.match(r":CHANnel(\d+):COUPling\s+(\w+)", command, re.IGNORECASE):
            conn._channel_coupling[int(match.group(1))] = match.group(2).upper()
            return True
        if match := re.match(r":TIMebase:SCALe\s+(.+)", command, re.IGNORECASE):
            conn.timebase = float(match.group(1))
            conn.timebase_updates.append(conn.timebase)
            return True
        if match := re.match(r":TRIGger:MODE\s+(\w+)", command, re.IGNORECASE):
            conn.trigger_mode = match.group(1)  # stored as wire token, e.g. "NORMal" (guide p.482)
            if match.group(1).upper() == "SINGLE" and len(conn.trigger_status) <= 1:
                # Status vocabulary matches real hardware: Ready while armed, Stop when done (same rule as the legacy ARM handler)
                conn.trigger_status = ["Ready", "Stop"]
            return True
        if re.match(r":TRIGger:RUN$", command, re.IGNORECASE):
            conn.trigger_mode = "AUTO"
            return True
        if re.match(r":TRIGger:STOP$", command, re.IGNORECASE):
            if len(conn.trigger_status) <= 1:
                conn.trigger_status = ["Stop"]
            return True
        if match := re.match(r":TRIGger:TYPE\s+(\w+)", command, re.IGNORECASE):
            conn.trigger_type = match.group(1).upper()
            return True
        if match := re.match(r":TRIGger:EDGE:SOURce\s+(\w+)", command, re.IGNORECASE):
            conn.trigger_source = match.group(1).upper()
            return True
        if match := re.match(r":TRIGger:EDGE:LEVel\s+(.+)", command, re.IGNORECASE):
            conn.trigger_level[1] = float(match.group(1))
            return True
        if match := re.match(r":TRIGger:EDGE:SLOPe\s+(\w+)", command, re.IGNORECASE):
            conn.trigger_slope = match.group(1)  # wire token, e.g. "RISing" (guide p.494)
            return True
        if match := re.match(r":TRIGger:EDGE:COUPling\s+(\w+)", command, re.IGNORECASE):
            conn.trigger_coupling = match.group(1)
            return True
        # Unknown modern writes fall through and are merely recorded,
        # mirroring real scopes which silently drop unknown commands

    if command.upper().startswith("TDIV "):
        value = command.split(" ", 1)[1]
        try:
            conn.timebase = float(value)
        except ValueError:
            conn.timebase = conn.timebase
        conn.timebase_updates.append(conn.timebase)
        return True
    elif match := re.match(r"C(\d+):VDIV\s+(.+)", command, re.IGNORECASE):
        channel = int(match.group(1))
        value = float(match.group(2))
        conn._voltage_scales[channel] = value
        conn.scale_updates.setdefault(channel, []).append(value)
        return True
    elif match := re.match(r"C(\d+):OFST\s+(.+)", command, re.IGNORECASE):
        channel = int(match.group(1))
        value = float(match.group(2))
        conn._voltage_offsets[channel] = value
        return True
    elif match := re.match(r"C(\d+):TRA\s+(ON|OFF)", command, re.IGNORECASE):
        channel = int(match.group(1))
        conn._channel_enabled[channel] = match.group(2).upper() == "ON"
        return True
    elif match := re.match(r"C(\d+):CPL\s+(\w+)", command, re.IGNORECASE):
        conn._channel_coupling[int(match.group(1))] = match.group(2).upper()
        return True
    elif command.upper().startswith("TRIG_MODE "):
        conn.trigger_mode = command.split(" ", 1)[1].upper()
        return True
    elif command.upper().startswith("TRIG_SELECT "):
        _, params = command.split(" ", 1)
        trig_type, _, source = params.split(",")
        conn.trigger_type = trig_type.strip().upper()
        conn.trigger_source = source.strip().upper()
        return True
    elif match := re.match(r"C(\d+):TRSL\s+(\w+)", command, re.IGNORECASE):
        conn.trigger_slope = match.group(2).upper()
        return True
    elif match := re.match(r"C(\d+):TRCP\s+(\w+)", command, re.IGNORECASE):
        conn.trigger_coupling = match.group(2).upper()
        return True
    elif command.upper() == "ARM":
        # Simulate an acquisition that will eventually stop when no custom sequence is provided.
        # Status vocabulary matches real hardware: Ready while armed, Stop when done.
        if len(conn.trigger_status) <= 1:
            conn.trigger_status = ["Ready", "Stop"]
        return True
    elif match := re.match(r"C(\d+):TRLV\s+(.+)", command, re.IGNORECASE):
        channel = int(match.group(1))
        conn.trigger_level[channel] = float(match.group(2))
        return True

    return False


def handle_query(conn, command: str) -> Optional[str]:
    """Handle a Siglent-dialect (legacy or modern) scope query. Returns None if unmatched."""
    upper = command.upper()

    if conn.scope_dialect == "modern":
        if upper == ":TRIGGER:STATUS?":  # enum Arm|Ready|Auto|Trig'd|Stop|Roll, p.483
            if len(conn.trigger_status) > 1:
                return conn.trigger_status.pop(0)
            return conn.trigger_status[0]
        if upper == ":TRIGGER:MODE?":  # mixed-case wire token, e.g. "NORMal", p.482
            return conn.trigger_mode
        if upper == ":TRIGGER:TYPE?":
            return conn.trigger_type
        if upper == ":TRIGGER:EDGE:SOURCE?":  # bare token, p.495
            return conn.trigger_source
        if upper == ":TRIGGER:EDGE:SLOPE?":  # wire token e.g. "RISing", p.494
            return conn.trigger_slope
        if upper == ":TRIGGER:EDGE:COUPLING?":
            return conn.trigger_coupling
        if upper == ":TRIGGER:EDGE:LEVEL?":  # bare NR3, p.492
            return _format_nr3(conn.trigger_level.get(1, 0.0))
        if match := re.match(r":CHANNEL(\d+):SWITCH\?", upper):
            return "ON" if conn._channel_enabled.get(int(match.group(1)), True) else "OFF"
        if match := re.match(r":CHANNEL(\d+):SCALE\?", upper):  # bare NR3, p.58
            return _format_nr3(conn._voltage_scales.get(int(match.group(1)), 1.0))
        if match := re.match(r":CHANNEL(\d+):OFFSET\?", upper):  # bare NR3, p.56
            return _format_nr3(conn._voltage_offsets.get(int(match.group(1)), 0.0))
        if match := re.match(r":CHANNEL(\d+):COUPLING\?", upper):  # DC|AC|GND, p.51
            return conn._channel_coupling.get(int(match.group(1)), "DC")
        if upper == ":TIMEBASE:SCALE?":  # bare NR3, p.476
            return _format_nr3(conn.timebase)
        if upper == ":ACQUIRE:SRATE?":  # bare NR3, p.46
            return _format_nr3(conn.sample_rate)

    if conn.scope_dialect == "legacy":
        if match := re.match(r"C(\d+):VDIV\?", command, re.IGNORECASE):
            channel = int(match.group(1))
            value = conn._voltage_scales.get(channel, 1.0)
            return _format_scientific(value, "V")

        if match := re.match(r"C(\d+):OFST\?", command, re.IGNORECASE):
            channel = int(match.group(1))
            value = conn._voltage_offsets.get(channel, 0.0)
            return _format_scientific(value, "V")

        if match := re.match(r"C(\d+):TRA\?", command, re.IGNORECASE):
            channel = int(match.group(1))
            return "ON" if conn._channel_enabled.get(channel, True) else "OFF"

        if match := re.match(r"C(\d+):CPL\?", command, re.IGNORECASE):
            return conn._channel_coupling.get(int(match.group(1)), "D1M")

        if match := re.match(r"C(\d+):TRLV\?", command, re.IGNORECASE):
            channel = int(match.group(1))
            return _format_scientific(conn.trigger_level.get(channel, 0.0), "V")

        if re.match(r"C(\d+):TRSL\?", command, re.IGNORECASE):
            return conn.trigger_slope

        if re.match(r"C(\d+):TRCP\?", command, re.IGNORECASE):
            return conn.trigger_coupling

        if upper == "TDIV?":
            return _format_scientific(conn.timebase, "S")

        if upper == "SARA?":
            return _format_scientific(conn.sample_rate, "Sa/s")

        if upper == "SAST?":
            if len(conn.trigger_status) > 1:
                return conn.trigger_status.pop(0)
            return conn.trigger_status[0]

        if upper == "TRIG_MODE?":
            return conn.trigger_mode

        if upper == "TRIG_SELECT?":
            return f"{conn.trigger_type},SR,{conn.trigger_source}"

        # RC01020-E01C p.88: request "C<n>:PAVA? <param>",
        # response "<trace>:PAVA <parameter>,<value>" -- two comma fields.
        if match := re.match(r"C(\d+):PAVA\?\s*(\w+)", command, re.IGNORECASE):
            channel = match.group(1)
            mtype = match.group(2).upper()
            entry = _MOCK_PAVA_VALUES.get(mtype)
            if entry is not None:
                value, unit = entry
                return f"C{channel}:PAVA {mtype},{value}{unit}"

    return None


def build_waveform_response(conn) -> bytes:
    """Construct a minimal Siglent-style waveform block response."""
    channel = conn._last_waveform_channel or next(iter(conn._waveform_payloads), 1)
    payload = mock_synth.payload_for(conn, channel, include_offset=True)
    return b"DESC," + _build_ieee_block(payload)
