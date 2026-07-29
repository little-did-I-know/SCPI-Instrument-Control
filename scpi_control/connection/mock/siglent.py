"""Siglent scope personality: legacy (SDS1000/2000-style) and modern (SDS800X HD-style)
write/query dialects, plus the waveform-response builder."""

from __future__ import annotations

import math
import re
import struct
from typing import Dict, Optional, Tuple

import numpy as np

from scpi_control import exceptions
from scpi_control.connection.mock.helpers import _build_ieee_block, _build_ieee_block_9digit, _format_nr3, _format_scientific, _format_si_sample_rate
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

# Modern :MEASure:SIMPle:VALue? replies, keyed by the MODERN wire token and
# holding a bare NR3 string (p.369 shows "2.000E+00" -- no parameter name, no
# unit suffix, unlike the legacy PAVA? reply above). The numbers mirror
# _MOCK_PAVA_VALUES so both dialects describe the same synthesized signal.
#
# WID and NBWID are deliberately ABSENT. Per p.345 those are the BURST widths;
# the driver must send PWID/NWID for pulse widths. Leaving them out means a
# driver regression that sends WID gets an unmatched query (SiglentTimeoutError
# under strict mode) instead of a plausible-looking wrong number.
_MOCK_SIMPLE_VALUES: Dict[str, str] = {
    "PKPK": "2.000E+00",
    "MAX": "1.000E+00",
    "MIN": "-1.000E+00",
    "AMPL": "2.000E+00",
    "TOP": "1.000E+00",
    "BASE": "-1.000E+00",
    "CMEAN": "0.000E+00",
    "MEAN": "0.000E+00",
    "RMS": "7.070E-01",
    "CRMS": "7.070E-01",
    "FREQ": "1.000E+03",
    "PER": "1.000E-03",
    "RISE": "3.500E-05",
    "FALL": "3.500E-05",
    "PWID": "5.000E-04",
    "NWID": "5.000E-04",
    # ASSUMPTION, not a manual fact: the guide gives exactly one bare-NR3 response
    # example (p.369, MAX -> "2.000E+00") and no worked example for DUTY, so there is
    # no documented confirmation this reply is percent-scaled rather than a 0-1
    # fraction. "5.000E+01" is inherited from the legacy dialect's unit-suffixed
    # fixture (_MOCK_PAVA_VALUES["DUTY"] above) purely so both dialects describe the
    # same synthesized signal -- do not cite this value as verified against EN11G.
    "DUTY": "5.000E+01",
}


def handle_write(conn, command: str) -> bool:
    """Handle a Siglent-dialect (legacy or modern) scope write. Returns True if consumed."""
    if conn.scope_dialect == "modern":
        if match := re.match(r":CHANnel(\d+):SWITch\s+(ON|OFF)", command, re.IGNORECASE):
            conn._channel_enabled[int(match.group(1))] = match.group(2).upper() == "ON"
            return True
        if match := re.match(r":CHANnel(\d+):SCALe\s+(.+)", command, re.IGNORECASE):
            ch = int(match.group(1))
            value = float(match.group(2))
            if conn.reject_if_invalid(value, name="SCALe"):
                return True  # consumed, ignored, error queued
            conn._voltage_scales[ch] = value
            conn.scale_updates.setdefault(ch, []).append(value)
            return True
        if match := re.match(r":CHANnel(\d+):OFFSet\s+(.+)", command, re.IGNORECASE):
            ch = int(match.group(1))
            value = float(match.group(2))
            # Offset may legitimately be negative or zero (e.g. p.56 EXAMPLE
            # "CHAN2:OFFS -3.8E+00"), so it is not gated on positivity.
            if conn.reject_if_invalid(value, name="OFFSet", positive=False):
                return True
            conn._voltage_offsets[ch] = value
            return True
        if match := re.match(r":CHANnel(\d+):COUPling\s+(\w+)", command, re.IGNORECASE):
            conn._channel_coupling[int(match.group(1))] = match.group(2).upper()
            return True
        if match := re.match(r":TIMebase:SCALe\s+(.+)", command, re.IGNORECASE):
            value = float(match.group(1))
            if conn.reject_if_invalid(value, name="TIMebase:SCALe"):
                return True
            conn.timebase = value
            conn.timebase_updates.append(conn.timebase)
            return True
        # :MEASure <ON|OFF> (p.337). Matched before the :MEASure:SIMPle forms
        # below; the required whitespace after the mnemonic means this pattern
        # cannot swallow ":MEASure:SIMPle:..." (next char there is ":").
        if match := re.match(r":MEAS(?:ure)?\s+(ON|OFF)\s*$", command, re.IGNORECASE):
            conn.measure_enabled = match.group(1).upper() == "ON"
            return True
        if match := re.match(r":MEAS(?:ure)?:MODE\s+(SIMP(?:le)?|ADV(?:anced)?)\s*$", command, re.IGNORECASE):
            conn.simple_mode = match.group(1)  # stored as wire token, e.g. "SIMPle" (guide p.365)
            return True
        if match := re.match(r":MEAS(?:ure)?:SIMP(?:le)?:SOUR(?:ce)?\s+(\w+)\s*$", command, re.IGNORECASE):
            conn.simple_source = match.group(1).upper()  # p.368
            return True
        if match := re.match(r":MEAS(?:ure)?:SIMP(?:le)?:ITEM\s+(\w+)\s*,\s*(ON|OFF)\s*$", command, re.IGNORECASE):
            item, state = match.group(1).upper(), match.group(2).upper()  # p.367
            if state == "ON":
                conn.simple_items.add(item)
            else:
                conn.simple_items.discard(item)
            return True
        if re.match(r":MEAS(?:ure)?:SIMP(?:le)?:CLE(?:ar)?\s*$", command, re.IGNORECASE):
            conn.simple_items.clear()  # p.367
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
            value = float(match.group(1))
            # Trigger level may legitimately be negative or zero (e.g. a signal
            # centered below/at ground), so it is not gated on positivity.
            if conn.reject_if_invalid(value, name="TRIGger:EDGE:LEVel", positive=False):
                return True
            conn.trigger_level[1] = value
            return True
        if match := re.match(r":TRIGger:EDGE:SLOPe\s+(\w+)", command, re.IGNORECASE):
            conn.trigger_slope = match.group(1)  # wire token, e.g. "RISing" (guide p.494)
            return True
        if match := re.match(r":TRIGger:EDGE:COUPling\s+(\w+)", command, re.IGNORECASE):
            conn.trigger_coupling = match.group(1)
            return True
        # Waveform transfer-parameter scalars (Task 17, audit H9; guide
        # pp.749-752). SOURce stores the bare source token verbatim (e.g.
        # "C2"); STARt/INTerval/POINt are NR1 integers.
        if match := re.match(r":WAVeform:SOURce\s+(\S+)", command, re.IGNORECASE):
            conn.waveform_source = match.group(1).upper()
            return True
        if match := re.match(r":WAVeform:STARt\s+(-?\d+)", command, re.IGNORECASE):
            conn.waveform_start = int(match.group(1))
            return True
        if match := re.match(r":WAVeform:INTerval\s+(-?\d+)", command, re.IGNORECASE):
            conn.waveform_interval = int(match.group(1))
            return True
        if match := re.match(r":WAVeform:POINt\s+(-?\d+)", command, re.IGNORECASE):
            conn.waveform_point = int(match.group(1))
            return True
        # Transfer width (Task 18, audit H9; guide p.754): selects the
        # COMM_TYPE the PREamble?/DATA? responses use.
        if match := re.match(r":WAVeform:WIDTh\s+(BYTE|WORD)", command, re.IGNORECASE):
            conn.waveform_width = match.group(1).upper()
            return True
        # Unknown modern writes fall through and are merely recorded,
        # mirroring real scopes which silently drop unknown commands

    if command.upper().startswith("TDIV "):
        raw = command.split(" ", 1)[1]
        try:
            value = float(raw)
        except ValueError:
            value = conn.timebase
        else:
            if conn.reject_if_invalid(value, name="TDIV"):
                value = conn.timebase
        conn.timebase = value
        conn.timebase_updates.append(conn.timebase)
        return True
    elif match := re.match(r"C(\d+):VDIV\s+(.+)", command, re.IGNORECASE):
        channel = int(match.group(1))
        value = float(match.group(2))
        if conn.reject_if_invalid(value, name="VDIV"):
            return True  # consumed, ignored, error queued
        conn._voltage_scales[channel] = value
        conn.scale_updates.setdefault(channel, []).append(value)
        return True
    elif match := re.match(r"C(\d+):OFST\s+(.+)", command, re.IGNORECASE):
        channel = int(match.group(1))
        value = float(match.group(2))
        # Offset may legitimately be negative or zero (p.83 EXAMPLE
        # "C2: OFST -3V"), so it is not gated on positivity.
        if conn.reject_if_invalid(value, name="OFST", positive=False):
            return True
        conn._voltage_offsets[channel] = value
        return True
    elif match := re.match(r"C(\d+):TRA\s+(ON|OFF)", command, re.IGNORECASE):
        channel = int(match.group(1))
        conn._channel_enabled[channel] = match.group(2).upper() == "ON"
        return True
    elif match := re.match(r"C(\d+):CPL\s+(\w+)", command, re.IGNORECASE):
        conn._channel_coupling[int(match.group(1))] = match.group(2).upper()
        return True
    elif match := re.match(r"C(\d+):ATTN\s+(.+)", command, re.IGNORECASE):
        # ATTENUATION (ATTN) -- RC01020-E01C p.22 (task 14, audit L3).
        channel = int(match.group(1))
        value = float(match.group(2))
        # An attenuation ratio is a magnitude, so it is gated on positivity.
        if conn.reject_if_invalid(value, name="ATTN"):
            return True
        conn.probe_ratios[channel] = value
        return True
    elif match := re.match(r"BWL\s+(C\d+,(?:ON|OFF)(?:,C\d+,(?:ON|OFF))*)", command, re.IGNORECASE):
        # BANDWIDTH_LIMIT (BWL) -- global, comma-separated channel/mode pairs,
        # not a per-channel colon-prefixed command (RC01020-E01C p.27; task 14).
        pairs = match.group(1).split(",")
        for i in range(0, len(pairs), 2):
            conn.bandwidth_limits[int(pairs[i][1:])] = pairs[i + 1].upper()
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
        value = float(match.group(2))
        # Trigger level may legitimately be negative or zero, so it is not
        # gated on positivity.
        if conn.reject_if_invalid(value, name="TRLV", positive=False):
            return True
        conn.trigger_level[channel] = value
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
        if upper == ":WAVEFORM:SOURCE?":  # bare source token, e.g. "C2", p.749
            return conn.waveform_source
        if upper == ":WAVEFORM:START?":  # bare NR1, p.750
            return str(conn.waveform_start)
        if upper == ":WAVEFORM:INTERVAL?":  # bare NR1, p.751
            return str(conn.waveform_interval)
        if upper == ":WAVEFORM:POINT?":  # bare NR1, p.752
            return str(conn.waveform_point)
        if upper == ":WAVEFORM:WIDTH?":  # BYTE|WORD, p.754
            return conn.waveform_width
        if upper == ":WAVEFORM:MAXPOINT?":  # bare NR1, p.753 (query-only, no setter)
            return str(conn.max_points)
        if match := re.match(r":MEAS(?:URE)?:SIMP(?:LE)?:VAL(?:UE)?\?\s*(\w+)", upper):
            # Answer for any token we know, regardless of whether ITEM switched it
            # on -- the wire-form corpus queries this directly with no setup writes.
            # An UNKNOWN token (e.g. the burst-width WID or NBWID, p.345, which the
            # driver must never send) falls through to None -> unmatched ->
            # SiglentTimeoutError under strict mode, so a mis-mapped measurement
            # type surfaces as a loud failure rather than a wrong number.
            item = match.group(1)
            if item in _MOCK_SIMPLE_VALUES:
                return _MOCK_SIMPLE_VALUES[item]  # bare NR3, p.369
        if upper == ":MEAS?" or upper == ":MEASURE?":  # p.337
            return "ON" if conn.measure_enabled else "OFF"
        if match := re.match(r":MEAS(?:URE)?:SIMP(?:LE)?:SOUR(?:CE)?\?", upper):  # p.368
            return conn.simple_source

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

        if match := re.match(r"C(\d+):ATTN\?", command, re.IGNORECASE):
            # RC01020-E01C p.22: RESPONSE FORMAT "<channel>:ATTeNuation
            # <attenuation>" -- header-echoed, collapsed to the short form.
            channel = int(match.group(1))
            value = conn.probe_ratios.get(channel, 1.0)
            return f"C{channel}:ATTN {value:g}"

        if upper == "BWL?":
            # RC01020-E01C p.27: bare query; RESPONSE FORMAT echoes the "BWL"
            # header followed by ALL-channel <channel>,<mode> pairs (task 14,
            # audit L3 -- replaces the invented per-channel "C{ch}:BWL?" form
            # this mock never actually answered). channel.py's bandwidth_limit
            # getter strips the header before parsing the pairs.
            pairs = ",".join(f"C{ch},{conn.bandwidth_limits.get(ch, 'OFF')}" for ch in sorted(conn._channel_enabled))
            return f"BWL {pairs}"

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
            # RC01020-E01C p.117: "SARA <value>" with an SI magnitude letter.
            return _format_si_sample_rate(conn.sample_rate)

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
    """Construct a minimal Siglent-style waveform block response.

    Legacy-dialect "C{ch}:WF? DAT2"/"DESC" only. As of v5.0.0 the modern
    dialect no longer falls through to this builder (Task 18's back-compat
    shim was removed on schedule); a modern-dialect read_raw() times out on
    an unrecognized/legacy waveform read instead, matching real modern
    hardware -- see build_waveform_preamble/build_waveform_data below for
    the documented modern path.
    """
    channel = conn._last_waveform_channel or next(iter(conn._waveform_payloads), 1)
    payload = mock_synth.payload_for(conn, channel, include_offset=True)
    return b"DESC," + _build_ieee_block(payload)


# ---- Modern :WAVeform:PREamble?/:WAVeform:DATA? binary responses ----------
# SDS Series Programming Guide EN11G p.755-756 (Table 1: "Explanation of the
# descriptor block"). Field offsets are from the first byte AFTER the
# "#9<9-digits>" header. wave_desc_length is fixed at 346 bytes; fields not
# read by ModernTransfer (Reserved, instrument/template name beyond the fixed
# prefix, the model-dependent Timebase enum, etc.) are left zeroed.
_MODERN_WAVEDESC_LEN = 346
_MODERN_COMM_TYPE = 32  # short: 0=byte, 1=word (p.755)
_MODERN_COMM_ORDER = 34  # short: 0=LSB, 1=MSB (p.755) -- mock always writes 0 (little-endian)
_MODERN_WAVE_DESC_LENGTH = 36  # long (p.755)
_MODERN_WAVE_ARRAY_1 = 60  # long: bytes in the transmitted array (p.755)
_MODERN_WAVE_ARRAY_COUNT = 116  # long: number of data points (p.755)
_MODERN_FIRST_POINT = 132  # long: = :WAVeform:STARt (p.755)
_MODERN_DATA_INTERVAL = 136  # long: = :WAVeform:INTerval (p.755)
_MODERN_VERTICAL_GAIN = 156  # float: V/div, no probe attenuation (p.756)
_MODERN_VERTICAL_OFFSET = 160  # float (p.756)
_MODERN_CODE_PER_DIV = 164  # float (p.756)
_MODERN_HORIZ_INTERVAL = 176  # float: 1/sample_rate (p.756)
_MODERN_HORIZ_OFFSET = 180  # double: trigger offset, seconds (p.756)

# code_per_div the mock encodes with. BYTE mirrors WAVEFORM_CODE_PER_DIV_8BIT
# (waveform.py); WORD is that value left-shifted 8 bits (256x), matching
# p.758's note that >8-bit models transmit word samples "left aligned, and
# the lower bit is zero filled" -- i.e. WAVEFORM_CODE_PER_DIV_16BIT is
# WAVEFORM_CODE_PER_DIV_8BIT * 256. Restated here (not imported) to avoid a
# waveform.py <-> connection.mock import edge; kept numerically identical.
_MODERN_CODE_PER_DIV_BYTE = 25.0
_MODERN_CODE_PER_DIV_WORD = 25.0 * 256


def _modern_source_channel(conn) -> int:
    """Extract the analog channel number from the stored :WAVeform:SOURce token."""
    match = re.fullmatch(r"C(\d+)", conn.waveform_source, re.IGNORECASE)
    if not match:
        raise exceptions.CommandError(f"Mock :WAVeform:SOURce {conn.waveform_source!r} is not an analog channel (only C<n> sources are modeled)")
    return int(match.group(1))


def _effective_record_length(conn, channel: int) -> int:
    """Total logical record length behind a modern-dialect capture.

    Task 19 (deep-memory chunking, guide p.753): `conn.record_length` is None
    by default, which defers to the existing single-shot formula
    (mock_synth.point_count -- an explicit payload's length, or the
    timebase/sample-rate window). Tests set `conn.record_length` explicitly,
    larger than `conn.max_points`, to model a record that does not fit in one
    :WAVeform:DATA? transfer.
    """
    if conn.record_length is not None:
        return conn.record_length
    return mock_synth.point_count(conn, channel)


def _synthesize_modern_codes(conn, channel: int, record_length: int, word: bool) -> np.ndarray:
    """Build the FULL record's code array once per acquisition.

    Cached by build_waveform_preamble (below) so that repeated windowed
    :WAVeform:DATA? reads (Task 19 chunking) slice ONE consistent waveform
    instead of each independently re-synthesizing -- which would also each
    advance mock_synth's acquisition count (free-run drift / RNG reseed) and
    desync the windows from one another.
    """
    explicit = conn._waveform_payloads.get(channel)
    if explicit is not None:
        return np.frombuffer(explicit, dtype="<i2" if word else np.int8)
    code_per_div = _MODERN_CODE_PER_DIV_WORD if word else _MODERN_CODE_PER_DIV_BYTE
    vdiv = conn._voltage_scales.get(channel, 1.0)
    voffset = conn._voltage_offsets.get(channel, 0.0)
    volts = mock_synth.raw_volts(conn, channel, n_override=record_length)
    codes = np.rint((volts + voffset) * code_per_div / vdiv)
    if word:
        return np.clip(codes, -32768, 32767).astype("<i2")
    return np.clip(codes, -128, 127).astype(np.int8)


def build_waveform_preamble(conn) -> bytes:
    """Build the modern :WAVeform:PREamble? response: "#9<9-digits>" + a 346-byte WAVEDESC.

    SDS Series Programming Guide EN11G p.755 (Table 1). The scaling fields
    (vertical_gain/vertical_offset/code_per_div/horizontal_interval) are
    exactly what build_waveform_data below encodes samples with, so the
    driver's parser recovers the mock's true volts (audit H9, Task 18).

    Task 19: wave_array_count is the FULL record length (guide p.756:
    "Number of data points in the data array"), even when that record exceeds
    max_points and will need several :WAVeform:DATA? windows to read -- on
    real hardware the preamble describes the whole record, only DATA?
    transfers are capped. This also (re)populates the per-channel code cache
    that build_waveform_data slices from, since PREamble? is read exactly
    once per capture, before the STARt-driven DATA? loop begins.

    ASSUMPTION, made visible (Task 3 stride follow-up, not yet confirmed
    against real hardware): wave_array_count/WAVE_ARRAY_1 below report the
    STRIDED (post-:WAVeform:INTerval) point/byte count, and HORIZ_INTERVAL
    reports the STRIDED sample spacing, not the full record's. We read it
    this way because WAVE_ARRAY_1 (addr 60) is documented as "bytes in the
    TRANSMITTED array", and FIRST_POINT (132)/DATA_INTERVAL (136) exist as
    their own fields precisely because the transmitted array is a sparse
    subset of the full record -- there would be nothing for DATA_INTERVAL to
    describe if wave_array_count were always the unstrided count. If a real
    SDS800X HD disagrees, this mock and ModernTransfer.acquire's DATA_INTERVAL
    cross-check (waveform_transfer.py) change together.
    """
    channel = _modern_source_channel(conn)
    word = conn.waveform_width == "WORD"
    bytes_per_point = 2 if word else 1
    code_per_div = _MODERN_CODE_PER_DIV_WORD if word else _MODERN_CODE_PER_DIV_BYTE
    record_length = _effective_record_length(conn, channel)
    conn._modern_waveform_codes[channel] = _synthesize_modern_codes(conn, channel, record_length, word)

    interval = max(1, conn.waveform_interval)
    strided_length = math.ceil(record_length / interval)

    desc = bytearray(_MODERN_WAVEDESC_LEN)
    desc[0:8] = b"WAVEDESC"
    desc[16:23] = b"WAVEACE"
    struct.pack_into("<h", desc, _MODERN_COMM_TYPE, 1 if word else 0)
    struct.pack_into("<h", desc, _MODERN_COMM_ORDER, 0)
    struct.pack_into("<i", desc, _MODERN_WAVE_DESC_LENGTH, _MODERN_WAVEDESC_LEN)
    struct.pack_into("<i", desc, _MODERN_WAVE_ARRAY_1, strided_length * bytes_per_point)
    struct.pack_into("<i", desc, _MODERN_WAVE_ARRAY_COUNT, strided_length)
    struct.pack_into("<i", desc, _MODERN_FIRST_POINT, conn.waveform_start)
    struct.pack_into("<i", desc, _MODERN_DATA_INTERVAL, conn.waveform_interval)
    struct.pack_into("<f", desc, _MODERN_VERTICAL_GAIN, conn._voltage_scales.get(channel, 1.0))
    struct.pack_into("<f", desc, _MODERN_VERTICAL_OFFSET, conn._voltage_offsets.get(channel, 0.0))
    struct.pack_into("<f", desc, _MODERN_CODE_PER_DIV, code_per_div)
    struct.pack_into("<f", desc, _MODERN_HORIZ_INTERVAL, ((1.0 / conn.sample_rate) * interval) if conn.sample_rate else 0.0)
    struct.pack_into("<d", desc, _MODERN_HORIZ_OFFSET, 0.0)  # mock triggers at the first sample
    return _build_ieee_block_9digit(bytes(desc))


def build_waveform_data(conn) -> bytes:
    """Build the modern :WAVeform:DATA? response: "#9<9-digits>" + raw sample codes.

    SDS Series Programming Guide EN11G p.757-758. Codes are encoded with the
    INVERSE of the guide's own p.758 voltage formula (code = (volts+voffset)
    * code_per_div / vdiv), so waveform_transfer.ModernTransfer's forward
    formula recovers the original volts (the round-trip this sub-project
    exists to make trustworthy -- see wavedesc-reference.md).

    Task 19 (deep-memory chunking, guide p.753): window-aware. Returns only
    transmitted[start : start + window], where window is capped by BOTH
    :WAVeform:POINt (when set) and :WAVeform:MAXPoint, and never reads past
    the (strided) record's end -- exactly the "read the waveform data in
    pieces" the guide's own MAXPoint description names. A single-shot capture
    (record length <= max_points, the common case and every Task 18 test)
    still returns the whole record in one call, unchanged.

    `transmitted` is codes[::interval] -- see build_waveform_preamble's
    ASSUMPTION note on why DATA? is read as answering from the strided
    subset, not the full record. interval=1 (the default, and every read that
    never sets :WAVeform:INTerval) makes this identical to the pre-stride
    behavior.
    """
    channel = _modern_source_channel(conn)
    word = conn.waveform_width == "WORD"
    codes = conn._modern_waveform_codes.get(channel)
    if codes is None:
        # DATA? without a preceding PREamble? read is not the order the
        # driver uses, but tolerate it (one-shot synthesis, not cached)
        # rather than raising, matching this mock's general leniency.
        codes = _synthesize_modern_codes(conn, channel, _effective_record_length(conn, channel), word)
    interval = max(1, conn.waveform_interval)
    transmitted = codes[::interval] if interval > 1 else codes
    record_length = len(transmitted)
    start = max(0, conn.waveform_start)
    remaining = max(0, record_length - start)
    requested = conn.waveform_point if conn.waveform_point else conn.max_points
    window = max(0, min(requested, conn.max_points, remaining))
    return _build_ieee_block_9digit(transmitted[start : start + window].tobytes())
