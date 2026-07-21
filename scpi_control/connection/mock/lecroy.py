"""LeCroy MAUI mock personality.

Writes reuse the Siglent legacy handler (Siglent copied LeCroy's command set);
queries answer in CHDR OFF format: bare values, no unit suffixes.
"""

import re
import struct
from typing import Optional

from scpi_control.connection.mock import synth as mock_synth
from scpi_control.connection.mock.helpers import _build_ieee_block, _format_nr3
from scpi_control.connection.mock.siglent import _MOCK_PAVA_VALUES, handle_write as _legacy_write

_INR_MAP = {"TRIG'D": "1"}  # INR bit 0: new signal acquired


def handle_write(conn, command: str) -> bool:
    upper = command.strip().upper()
    if upper.startswith("CFMT ") or upper.startswith("CORD ") or upper == "CHDR OFF":
        return True
    if upper == "STOP":
        conn.trigger_mode = "STOP"  # TRMD? reports STOP after a STOP command
        return True
    if upper.startswith("BWL "):
        # Legacy chain has no BWL handler; record as a no-op write explicitly
        # so the fidelity contract (write returns True => consumed) holds.
        return True
    # The legacy chain understands TDIV/VDIV/TRA/CPL/TRIG_* — LeCroy originals.
    # Its modern branch gates on scope_dialect == "modern", which is False here.
    return _legacy_write(conn, command)


def handle_query(conn, command: str) -> Optional[str]:
    upper = command.strip().upper()

    if match := re.match(r"C(\d+):VDIV\?", upper):
        return _format_nr3(conn._voltage_scales.get(int(match.group(1)), 1.0))
    if match := re.match(r"C(\d+):OFST\?", upper):
        return _format_nr3(conn._voltage_offsets.get(int(match.group(1)), 0.0))
    if match := re.match(r"C(\d+):TRA\?", upper):
        return "ON" if conn._channel_enabled.get(int(match.group(1)), True) else "OFF"
    if match := re.match(r"C(\d+):CPL\?", upper):
        return conn._channel_coupling.get(int(match.group(1)), "D1M")
    if match := re.match(r"C(\d+):TRLV\?", upper):
        return _format_nr3(conn.trigger_level.get(int(match.group(1)), 0.0))
    if re.match(r"C(\d+):TRSL\?", upper):
        return conn.trigger_slope
    if re.match(r"C(\d+):TRCP\?", upper):
        return conn.trigger_coupling
    if match := re.match(r"C(\d+):ATTN\?", upper):
        return "10"
    if upper == "TDIV?":
        return _format_nr3(conn.timebase)
    if upper == "TRIG_MODE?" or upper == "TRMD?":
        return conn.trigger_mode
    if upper == "TRIG_SELECT?" or upper == "TRSE?":
        return f"{conn.trigger_type},SR,{conn.trigger_source}"
    if upper == "INR?":
        if len(conn.trigger_status) > 1:
            return _INR_MAP.get(conn.trigger_status.pop(0).upper(), "0")
        return _INR_MAP.get(conn.trigger_status[0].upper(), "0")
    if upper == "BWL?":
        return ",".join(f"C{ch},OFF" for ch in sorted(conn._channel_enabled))
    if upper.startswith("VBS? 'RETURN=APP.ACQUISITION.HORIZONTAL.SAMPLINGRATE'"):
        return _format_nr3(conn.sample_rate)
    if match := re.match(r"C(\d+):PAVA\?\s*(\w+)", upper):
        mtype = match.group(2)
        entry = _MOCK_PAVA_VALUES.get(mtype)
        if entry is not None:
            value, _unit = entry
            # CHDR OFF suppresses units on LeCroy; native shape is <param>,<value>,<state>
            return f"{mtype},{value},OK"
    return None


def build_waveform_response(conn) -> bytes:
    """Construct a LeCroy WAVEDESC + sample-array block (WF? ALL, CORD LO)."""
    channel = conn._last_waveform_channel or 1
    codes = mock_synth.payload_for(conn, channel, include_offset=True)
    gain = conn._voltage_scales.get(channel, 1.0) / 25.0  # mirror Siglent scaling for comparable volts
    desc = bytearray(346)
    desc[0:8] = b"WAVEDESC"
    struct.pack_into("<h", desc, 32, 0)
    struct.pack_into("<i", desc, 36, 346)
    struct.pack_into("<i", desc, 40, 0)
    # TRIGTIME_ARRAY (offset 48) and RIS_TIME_ARRAY (offset 52) lengths: 0 for
    # this single-shot mock (the bytearray is already zero-filled; packed
    # explicitly to document the layout parse_wavedesc now skips).
    struct.pack_into("<i", desc, 48, 0)
    struct.pack_into("<i", desc, 52, 0)
    struct.pack_into("<i", desc, 116, len(codes))
    struct.pack_into("<f", desc, 156, gain)
    struct.pack_into("<f", desc, 160, conn._voltage_offsets.get(channel, 0.0))
    struct.pack_into("<f", desc, 176, 1.0 / conn.sample_rate)
    struct.pack_into("<d", desc, 180, 0.0)
    return _build_ieee_block(bytes(desc) + codes)
