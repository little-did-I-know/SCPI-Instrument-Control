"""Tektronix mock personality: TBS1000C / MSO 2-Series wire language.

Command spellings mirror the TEKTRONIX_COMMANDS table (scpi_commands.py);
responses use HEADer OFF format (bare values), matching CONNECT_SETUP.
"""

import re
from typing import Optional

from scpi_control.connection.mock import synth as mock_synth
from scpi_control.connection.mock.helpers import _build_ieee_block, _format_nr3
from scpi_control.scpi_commands import wire_coupling_tokens, wire_trigger_coupling_tokens, wire_trigger_mode_tokens, wire_trigger_slope_tokens

# Immediate-measurement values mirror _MOCK_PAVA_VALUES semantically (same
# synthetic 1 kHz, 2 Vpp signal) but keyed by Tek IMMed type names.
_MOCK_IMMED_VALUES = {
    "PK2PK": "2.0E0",
    "MAXIMUM": "1.0E0",
    "MINIMUM": "-1.0E0",
    "AMPLITUDE": "2.0E0",
    "HIGH": "1.0E0",
    "LOW": "-1.0E0",
    "CMEAN": "0.0E0",
    "MEAN": "0.0E0",
    "RMS": "7.07E-1",
    "CRMS": "7.07E-1",
    "FREQUENCY": "1.0E3",
    "PERIOD": "1.0E-3",
    "RISE": "3.5E-5",
    "FALL": "3.5E-5",
    "PWIDTH": "5.0E-4",
    "NWIDTH": "5.0E-4",
    "PDUTY": "5.0E1",
}

# Badge TYPe vocabulary differs from IMMed (RISETIME vs RISe, etc.), so the
# badge results need their own lookup keyed by the uppercased badge token.
_MOCK_BADGE_VALUES = {
    "PK2PK": "2.0E0",
    "MAXIMUM": "1.0E0",
    "MINIMUM": "-1.0E0",
    "AMPLITUDE": "2.0E0",
    "TOP": "1.0E0",
    "BASE": "-1.0E0",
    "MEAN": "0.0E0",
    "RMS": "7.07E-1",
    "FREQUENCY": "1.0E3",
    "PERIOD": "1.0E-3",
    "RISETIME": "3.5E-5",
    "FALLTIME": "3.5E-5",
    "PWIDTH": "5.0E-4",
    "NWIDTH": "5.0E-4",
    "PDUTY": "5.0E1",
}


def handle_write(conn, command: str) -> bool:
    upper = command.upper()

    if upper in ("HEADER OFF", "HEADER ON"):
        return True
    if match := re.match(r"(?:SELECT:CH|DISPLAY:GLOBAL:CH)(\d+)(?::STATE)?\s+(ON|OFF|1|0)", upper):
        conn._channel_enabled[int(match.group(1))] = match.group(2) in ("ON", "1")
        return True
    if match := re.match(r"CH(\d+):SCALE\s+(.+)", upper):
        ch = int(match.group(1))
        value = float(match.group(2))
        # A vertical scale is a magnitude (V/div), so it is gated on positivity.
        if conn.reject_if_invalid(value, name="SCALE"):
            return True  # consumed, ignored, error queued
        conn._voltage_scales[ch] = value
        conn.scale_updates.setdefault(ch, []).append(value)
        return True
    if match := re.match(r"CH(\d+):OFFSET\s+(.+)", upper):
        ch = int(match.group(1))
        value = float(match.group(2))
        # Offset may legitimately be negative or zero, so it is not gated on positivity.
        if conn.reject_if_invalid(value, name="OFFSET", positive=False):
            return True
        conn._voltage_offsets[ch] = value
        return True
    if match := re.match(r"CH(\d+):COUPLING\s+(\w+)", upper):
        token = match.group(2)
        if token not in wire_coupling_tokens("tektronix"):
            conn.push_error(-224, "Illegal parameter value")
            return True
        conn._channel_coupling[int(match.group(1))] = token
        return True
    if match := re.match(r"CH(\d+):PROBE:GAIN\s+(.+)", upper):
        ch = int(match.group(1))
        value = float(match.group(2))
        # A probe attenuation/gain factor is a magnitude, so it is gated on positivity.
        if conn.reject_if_invalid(value, name="PROBE:GAIN"):
            return True
        conn.probe_gains[ch] = value
        return True
    if match := re.match(r"CH(\d+):PROBEFUNC:EXTATTEN\s+(.+)", upper):
        # tek_mso spelling for the same probe-gain state (tek_tbs uses PRObe:GAIN above).
        ch = int(match.group(1))
        value = float(match.group(2))
        if conn.reject_if_invalid(value, name="PROBEFUNC:EXTATTEN"):
            return True
        conn.probe_gains[ch] = value
        return True
    if match := re.match(r"CH(\d+):BANDWIDTH\s+(\w+)", upper):
        return True  # accepted, not modeled
    if match := re.match(r"HORIZONTAL:SCALE\s+(.+)", upper):
        value = float(match.group(1))
        # A timebase is a magnitude, so it is gated on positivity.
        if conn.reject_if_invalid(value, name="HORIZONTAL:SCALE"):
            return True
        conn.timebase = value
        conn.timebase_updates.append(conn.timebase)
        return True
    if re.match(r"HORIZONTAL:DELAY:TIME\s+", upper):
        return True
    if match := re.match(r"TRIGGER:A:MODE\s+(\w+)", upper):
        token = match.group(1)
        if token not in wire_trigger_mode_tokens("tektronix"):
            conn.push_error(-224, "Illegal parameter value")
            return True
        conn.trigger_mode = token
        return True
    if match := re.match(r"ACQUIRE:STOPAFTER\s+(\w+)", upper):
        conn.tek_stop_after = match.group(1)
        return True
    if re.match(r"ACQUIRE:STATE\s+(RUN|ON|1)", upper):
        if conn.tek_stop_after == "SEQUENCE" and len(conn.trigger_status) <= 1:
            # Single-shot: Ready while armed, Save when done (Tek vocabulary)
            conn.trigger_status = ["READY", "SAVE"]
        return True
    if re.match(r"ACQUIRE:STATE\s+(STOP|OFF|0)", upper):
        if len(conn.trigger_status) <= 1:
            conn.trigger_status = ["SAVE"]
        return True
    if re.match(r"TRIGGER\s+FORCE", upper):
        return True
    if match := re.match(r"TRIGGER:A:TYPE\s+(\w+)", upper):
        conn.trigger_type = match.group(1)
        return True
    if match := re.match(r"TRIGGER:A:EDGE:SOURCE\s+(\w+)", upper):
        conn.trigger_source = match.group(1)
        return True
    if match := re.match(r"TRIGGER:A:LEVEL:CH(\d+)\s+(.+)", upper):
        ch = int(match.group(1))
        value = float(match.group(2))
        # Trigger level may legitimately be negative or zero, so it is not
        # gated on positivity.
        if conn.reject_if_invalid(value, name="TRIGGER:A:LEVEL", positive=False):
            return True
        conn.trigger_level[ch] = value
        return True
    if match := re.match(r"TRIGGER:A:EDGE:SLOPE\s+(\w+)", upper):
        token = match.group(1)
        if token not in wire_trigger_slope_tokens("tektronix"):
            conn.push_error(-224, "Illegal parameter value")
            return True
        conn.trigger_slope = token
        return True
    if match := re.match(r"TRIGGER:A:EDGE:COUPLING\s+(\w+)", upper):
        token = match.group(1)
        if token not in wire_trigger_coupling_tokens("tektronix"):
            conn.push_error(-224, "Illegal parameter value")
            return True
        conn.trigger_coupling = token
        return True
    if match := re.match(r"TRIGGER:A:HOLDOFF:TIME\s+(.+)", upper):
        value = float(match.group(1))
        # trigger.py's own validation rejects a NEGATIVE holdoff
        # (`if time_seconds < 0: raise`), so 0 is legitimate but a negative
        # value is not -- gated on non_negative (>= 0), not positive (> 0)
        # (I2: `positive=False` alone let `-5.0` silently through).
        if conn.reject_if_invalid(value, name="TRIGGER:A:HOLDOFF:TIME", positive=False, non_negative=True):
            return True
        conn.holdoff_time = value
        return True
    if re.match(r"AUTOSET\s+EXECUTE", upper):
        return True
    if match := re.match(r"DATA:SOURCE\s+CH(\d+)", upper):
        conn.data_source = int(match.group(1))
        conn._last_waveform_channel = conn.data_source
        return True
    if match := re.match(r"DATA:START\s+(\d+)", upper):
        # MSO4/5/6 PM p.2-341: DATa:STARt is the first point of the window
        # CURVe?/NR_Pt? operate on. Storing it (rather than discarding the
        # write, as before) is what lets a test seed or observe the window a
        # driver is measuring/widening.
        conn.data_start = int(match.group(1))
        return True
    if match := re.match(r"DATA:STOP\s+(\d+)", upper):
        # MSO4/5/6 PM p.2-341/2-342: DATa:STOP is the last point of the
        # window; the manual is explicit that a record-length change is NOT
        # automatically reflected here, which is the whole hazard this state
        # models (a stale STOP left behind by a prior script or recall).
        conn.data_stop = int(match.group(1))
        return True
    if re.match(r"DATA:(ENCDG|WIDTH)\s+", upper):
        return True
    if upper == "CURVE?":
        conn.waveform_requests.append(conn.data_source)
        return True
    if re.match(r"MEASUREMENT:IMMED:(TYPE|SOURCE1)\s+", upper):
        if match := re.match(r"MEASUREMENT:IMMED:TYPE\s+(\w+)", upper):
            conn.meas_immed_type = match.group(1)
        return True
    if match := re.match(r'MEASUREMENT:ADDNEW\s+"MEAS(\d+)"', upper):
        conn.badges.setdefault(int(match.group(1)), {})
        return True
    if match := re.match(r"MEASUREMENT:MEAS(\d+):TYPE\s+(\w+)", upper):
        conn.badges.setdefault(int(match.group(1)), {})["type"] = match.group(2)
        return True
    if match := re.match(r"MEASUREMENT:MEAS(\d+):SOURCE\s+(\w+)", upper):
        conn.badges.setdefault(int(match.group(1)), {})["source"] = match.group(2)
        return True
    if match := re.match(r'MEASUREMENT:DELETE\s+"MEAS(\d+)"', upper):
        conn.badges.pop(int(match.group(1)), None)
        return True
    return False


def handle_query(conn, command: str) -> Optional[str]:
    upper = command.strip().upper()

    if match := re.match(r"(?:SELECT:CH|DISPLAY:GLOBAL:CH)(\d+)(?::STATE)?\?", upper):
        return "1" if conn._channel_enabled.get(int(match.group(1)), True) else "0"
    if match := re.match(r"CH(\d+):SCALE\?", upper):
        return _format_nr3(conn._voltage_scales.get(int(match.group(1)), 1.0))
    if match := re.match(r"CH(\d+):OFFSET\?", upper):
        return _format_nr3(conn._voltage_offsets.get(int(match.group(1)), 0.0))
    if match := re.match(r"CH(\d+):COUPLING\?", upper):
        return conn._channel_coupling.get(int(match.group(1)), "DC")
    if match := re.match(r"CH(\d+):PROBE:GAIN\?", upper):
        return _format_nr3(conn.probe_gains.get(int(match.group(1)), 0.1))
    if match := re.match(r"CH(\d+):PROBEFUNC:EXTATTEN\?", upper):
        return _format_nr3(conn.probe_gains.get(int(match.group(1)), 0.1))
    if re.match(r"CH(\d+):BANDWIDTH\?", upper):
        return "FULL"
    if upper == "HORIZONTAL:SCALE?":
        return _format_nr3(conn.timebase)
    if upper == "HORIZONTAL:SAMPLERATE?":
        return _format_nr3(conn.sample_rate)
    if upper == "TRIGGER:STATE?":
        if len(conn.trigger_status) > 1:
            return conn.trigger_status.pop(0).upper()
        return conn.trigger_status[0].upper()
    if upper == "TRIGGER:A:MODE?":
        return conn.trigger_mode.upper()
    if upper == "TRIGGER:A:TYPE?":
        return conn.trigger_type.upper()
    if upper == "TRIGGER:A:EDGE:SOURCE?":
        return conn.trigger_source
    if match := re.match(r"TRIGGER:A:LEVEL:CH(\d+)\?", upper):
        return _format_nr3(conn.trigger_level.get(int(match.group(1)), 0.0))
    if upper == "TRIGGER:A:EDGE:SLOPE?":
        return conn.trigger_slope.upper()
    if upper == "TRIGGER:A:EDGE:COUPLING?":
        return conn.trigger_coupling.upper()
    if upper == "TRIGGER:A:HOLDOFF:TIME?":
        return _format_nr3(conn.holdoff_time)
    if upper == "WFMOUTPRE:NR_PT?":
        # MSO4/5/6 programmer manual p.2-1461: NR_Pt? reports the points that will
        # be TRANSMITTED for the current DATa:STARt/STOP window, not the acquisition
        # record length (p.2-1455's own example: a 1250-point record reporting
        # NR_PT 1000). Modelling the window is what lets a test catch a driver that
        # measures the record through a stale window.
        record = mock_synth.point_count(conn, conn.data_source)
        stop = record if conn.data_stop is None else min(conn.data_stop, record)
        return str(max(0, stop - conn.data_start + 1))
    if upper == "WFMOUTPRE:XINCR?":
        return _format_nr3(1.0 / conn.sample_rate)
    if upper == "WFMOUTPRE:XZERO?":
        return "0.0E0"
    if upper == "WFMOUTPRE:PT_OFF?":
        return "0"
    if upper == "WFMOUTPRE:YMULT?":
        # Mirror the Siglent 25-codes-per-division scale so end-to-end volts match
        return _format_nr3(conn._voltage_scales.get(conn.data_source, 1.0) / 25.0)
    if upper == "WFMOUTPRE:YZERO?":
        return "0.0E0"
    if upper == "WFMOUTPRE:YOFF?":
        return "0.0E0"
    if upper == "MEASUREMENT:IMMED:VALUE?":
        return _MOCK_IMMED_VALUES.get(getattr(conn, "meas_immed_type", ""), "0.0E0")
    if upper == "MEASUREMENT:LIST?":
        # MSO2 PM 077-1776-07 p.2-411 states explicitly: "When no measurements
        # are defined, the command returns NONE." The 4/5/6 PM 077-1305-11
        # p.2-592 doesn't document this case, but is consistent-but-silent,
        # not contradictory, so the same NONE spelling is used here.
        return ",".join(f"MEAS{n}" for n in sorted(conn.badges)) if conn.badges else "NONE"
    if match := re.match(r"MEASUREMENT:MEAS(\d+):RESULTS:CURRENTACQ:MEAN\?", upper):
        badge = conn.badges.get(int(match.group(1)))
        if badge is None:
            return None  # no such badge -> caller times out, as on real hardware
        return _MOCK_BADGE_VALUES.get(badge.get("type", ""), "0.0E0")
    return None


def build_waveform_response(conn) -> bytes:
    # Tek's converter is (code - yoff)*ymult + yzero with yoff=yzero=0 here, so
    # codes carry no channel-offset term (include_offset=False).
    payload = mock_synth.payload_for(conn, conn.data_source, include_offset=False)
    # CURVe? only transmits the DATa:STARt/STOP window -- the same semantics
    # WFMOutpre:NR_Pt? reports above (MSO4/5/6 PM p.2-1461) -- so the actual
    # byte count returned here must agree with NR_Pt?'s answer. Sliced here,
    # not inside the shared payload_for()/point_count() (also used by the
    # Siglent/LeCroy personalities, which never touch data_start/data_stop),
    # so those dialects are unaffected.
    record = len(payload)
    stop = record if conn.data_stop is None else min(conn.data_stop, record)
    start = max(1, conn.data_start)
    windowed = payload[start - 1 : stop]
    return _build_ieee_block(windowed)  # CURVe? responses are a bare IEEE block
