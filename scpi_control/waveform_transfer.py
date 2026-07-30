"""Per-dialect waveform transfer strategies.

Legacy Siglent speaks WF? DAT2 with fixed code-per-division scaling;
Tektronix speaks the CURVe protocol scaled by the WFMOutpre preamble; LeCroy
(Task 15) speaks WF? ALL scaled by the WAVEDESC descriptor; modern Siglent
(Task 18, audit H9) speaks the documented :WAVeform:SOURce/PREamble/DATA
subsystem, also scaled by a WAVEDESC-shaped descriptor but with an explicit
code_per_div field the LeCroy path does not have. The IEEE-488.2
definite-length block framing is shared by all of them.
"""

import logging
import re
import struct
from typing import TYPE_CHECKING, Optional

import numpy as np

from scpi_control import exceptions
from scpi_control.waveform import (
    WAVEFORM_CODE_CENTER,
    WAVEFORM_CODE_PER_DIV_8BIT,
    WAVEFORM_CODE_PER_DIV_16BIT,
    WaveformData,
)

if TYPE_CHECKING:
    from scpi_control.oscilloscope import Oscilloscope

logger = logging.getLogger(__name__)


def parse_ieee_block(raw_data: bytes, dtype, *, error_context: str = "") -> np.ndarray:
    """Parse an IEEE-488.2 definite-length block into a numpy array.

    Args:
        raw_data: Raw bytes containing a "#<n><length><data>" block (with an
            optional prefix before the "#", e.g. Siglent's "DESC," header).
        dtype: numpy dtype of the packed samples (np.int8 or np.int16).
        error_context: Extra context appended to error messages, e.g.
            "host 1.2.3.4:5025, command 'C1:WF? DAT2'".

    Returns:
        Numpy array of raw data codes.

    Raises:
        exceptions.CommandError: If the block is malformed.
    """

    def _err(message: str) -> str:
        return f"{message} ({error_context})" if error_context else message

    if not raw_data:
        raise exceptions.CommandError(_err("Invalid waveform format: empty response"))

    # Look for the # character indicating block data
    header_end = raw_data.find(b"#")
    if header_end == -1:
        raise exceptions.CommandError(_err("Invalid waveform format: no # found in block header"))

    if header_end + 2 > len(raw_data):
        raise exceptions.CommandError(_err("Invalid waveform format: truncated block header"))

    # Parse IEEE 488.2 definite length block
    # Format: #<n><length><data>
    # where n is number of digits in length
    n_digit_char = chr(raw_data[header_end + 1])
    if not n_digit_char.isdigit():
        raise exceptions.CommandError(_err(f"Invalid waveform format: non-numeric length digit '{n_digit_char}'"))

    n_digits = int(n_digit_char)
    if n_digits <= 0:
        raise exceptions.CommandError(_err(f"Invalid waveform format: length digit must be positive (got {n_digits})"))

    length_field_start = header_end + 2
    length_field_end = length_field_start + n_digits
    if length_field_end > len(raw_data):
        raise exceptions.CommandError(_err("Invalid waveform format: truncated length field"))

    length_field = raw_data[length_field_start:length_field_end]
    if not re.fullmatch(rb"\d+", length_field):
        raise exceptions.CommandError(_err(f"Invalid waveform format: non-numeric length field '{length_field.decode(errors='ignore')}'"))

    data_length = int(length_field)
    data_start = length_field_end
    data_end = data_start + data_length

    if data_end > len(raw_data):
        raise exceptions.CommandError(_err("Invalid waveform format: declared data length exceeds available data"))

    # Extract binary data
    binary_data = raw_data[data_start:data_end]

    # Convert to numpy array
    if dtype == np.int16:
        # 16-bit signed data
        if data_length % 2:
            raise exceptions.CommandError(_err("Invalid waveform format: WORD data length must be even"))

    data = np.frombuffer(binary_data, dtype=dtype)

    return data


class SiglentTransfer:
    """WF? DAT2 transfer with code-per-division scaling (current behavior, moved)."""

    def __init__(self, scope: "Oscilloscope"):
        self._scope = scope

    def acquire(self, channel: int, format: str = "BYTE", stride: Optional[int] = None) -> WaveformData:
        """Acquire waveform data from a channel via WF? DAT2.

        Args:
            channel: Channel number (1-4)
            format: Data format - 'BYTE' or 'WORD' (default: 'BYTE')
            stride: Unused on this dialect -- legacy Siglent has no documented
                :WAVeform:INTerval-equivalent command, so nothing is written.
                Accepted only so callers can pass it uniformly regardless of
                which transfer make_transfer() selected.

        Returns:
            WaveformData object with time and voltage arrays

        Raises:
            CommandError: If acquisition fails
        """
        # Get channel configuration
        ch = f"C{channel}"
        voltage_scale = self._scope.waveform._get_voltage_scale(ch)
        voltage_offset = self._scope.waveform._get_voltage_offset(ch)
        timebase = self._scope.waveform._get_timebase()
        sample_rate = self._scope.waveform._get_sample_rate()

        # Request waveform data; hold the connection lock so no other thread
        # can slip a query between the command and its binary response
        waveform_command = self._scope._get_command("get_waveform", ch=channel)
        with self._scope._connection.lock:
            self._scope.write(waveform_command)
            raw_data = self._scope.read_raw()

        # Parse waveform data
        if format == "BYTE":
            dtype = np.int8
        elif format == "WORD":
            dtype = np.int16
        else:
            raise exceptions.InvalidParameterError(f"Invalid format: {format}")

        error_context = f"host {self._scope.host}:{self._scope.port}, command '{waveform_command}'"
        voltage_data = parse_ieee_block(raw_data, dtype, error_context=error_context)
        record_length = len(voltage_data)

        # Convert to voltage using scale and offset
        # Formula: Voltage = (code - code_offset) * code_scale + voltage_offset
        # For 8-bit data: typically code_offset = 127 (or 128), code_scale = voltage_scale / 25
        voltage = self._convert_to_voltage(voltage_data, voltage_scale, voltage_offset)

        # Generate time axis
        time = self._generate_time_axis(record_length, sample_rate, timebase)

        logger.info(f"Acquired {record_length} samples from channel {channel}")

        return WaveformData(
            time=time,
            voltage=voltage,
            channel=channel,
            sample_rate=sample_rate,
            record_length=record_length,
            timebase=timebase,
            voltage_scale=voltage_scale,
            voltage_offset=voltage_offset,
        )

    def _convert_to_voltage(self, codes: np.ndarray, voltage_scale: float, voltage_offset: float) -> np.ndarray:
        """Convert raw ADC codes to voltage values.

        Uses conversion formula from Siglent SCPI programming manual:
        voltage = (code - code_center) * (voltage_scale / code_per_div) - voltage_offset

        For 8-bit ADC:  25 codes per vertical division
        For 16-bit ADC: 6400 codes per vertical division

        Args:
            codes: Raw ADC code values (signed int8 or int16)
            voltage_scale: Voltage scale in volts/division
            voltage_offset: Voltage offset in volts

        Returns:
            Voltage array in volts
        """
        # Select conversion constants based on ADC resolution
        if codes.dtype == np.int8:
            code_per_div = WAVEFORM_CODE_PER_DIV_8BIT
        else:  # 16-bit data
            code_per_div = WAVEFORM_CODE_PER_DIV_16BIT

        # Convert codes to voltage using Siglent formula
        # Since we use signed integers, center code is 0
        voltage = (codes.astype(np.float64) - WAVEFORM_CODE_CENTER) * (voltage_scale / code_per_div) - voltage_offset

        return voltage

    def _generate_time_axis(self, num_samples: int, sample_rate: float, timebase: float) -> np.ndarray:
        """Generate time axis for waveform.

        Args:
            num_samples: Number of samples
            sample_rate: Sample rate in Sa/s
            timebase: Timebase in s/div

        Returns:
            Time array in seconds
        """
        # Calculate time interval
        dt = 1.0 / sample_rate

        # Generate time axis (centered at trigger point)
        # Typically trigger is at center of screen (14 divisions total, 7 left of trigger)
        total_time = num_samples * dt
        trigger_position = total_time / 2  # Assume trigger at center

        time = np.arange(num_samples) * dt - trigger_position

        return time


class TektronixTransfer:
    """CURVe? transfer scaled by the WFMOutpre preamble (Tek PMs, Task 7 citations)."""

    def __init__(self, scope: "Oscilloscope"):
        self._scope = scope

    def acquire(self, channel: int, format: str = "BYTE", stride: Optional[int] = None) -> WaveformData:
        """Acquire waveform data from a channel via the CURVe protocol.

        Args:
            channel: Channel number (1-4)
            format: Data format - only 'BYTE' (8-bit, DATa:WIDth 1) is
                supported today; 'WORD' (16-bit) is a follow-up.
            stride: Unused on this dialect -- no documented Tektronix
                equivalent to :WAVeform:INTerval. Accepted only so callers
                can pass it uniformly regardless of which transfer
                make_transfer() selected.

        Returns:
            WaveformData scaled by the WFMOutpre preamble (ymult/yoff/yzero for
            volts, xincr/xzero/pt_off for the time axis).

        Raises:
            FeatureNotSupportedError: If a non-BYTE format is requested.
            CommandError: If the CURVe block is malformed.
        """
        if format.upper() != "BYTE":
            raise exceptions.FeatureNotSupportedError("16-bit waveform transfer on tektronix is not supported yet (DATa:WIDth 1 only)")
        scope = self._scope
        scope.write(scope._get_command("set_data_source", ch=channel))
        scope.write(scope._get_command("set_data_encoding"))
        scope.write(scope._get_command("set_data_width"))
        n_points = int(float(scope.query(scope._get_command("get_wfm_nr_pt"))))
        scope.write(scope._get_command("set_data_start", start=1))
        scope.write(scope._get_command("set_data_stop", stop=n_points))
        xincr = float(scope.query(scope._get_command("get_wfm_xincr")))
        xzero = float(scope.query(scope._get_command("get_wfm_xzero")))
        # WFMOutpre:PT_Off? is MSO2-only (absent from the TBS1000C WFMOutpre
        # subsystem, per Task 7's manual audit) -- default to 0 (trigger at
        # record start) when the active dialect/variant doesn't define it.
        if scope._has_command("get_wfm_pt_off"):
            pt_off = float(scope.query(scope._get_command("get_wfm_pt_off")))
        else:
            pt_off = 0.0
        ymult = float(scope.query(scope._get_command("get_wfm_ymult")))
        yzero = float(scope.query(scope._get_command("get_wfm_yzero")))
        yoff = float(scope.query(scope._get_command("get_wfm_yoff")))

        command = scope._get_command("get_waveform")
        with scope._connection.lock:
            scope.write(command)
            raw = scope.read_raw()
        codes = parse_ieee_block(raw, np.int8, error_context=f"host {scope.host}:{scope.port}, command '{command}'")

        voltage = (codes.astype(np.float64) - yoff) * ymult + yzero
        time = xzero + (np.arange(len(codes)) - pt_off) * xincr
        voltage_scale = scope.waveform._get_voltage_scale(f"C{channel}")
        timebase = scope.waveform._get_timebase()
        logger.info(f"Acquired {len(codes)} samples from channel {channel} (tektronix)")
        return WaveformData(
            time=time,
            voltage=voltage,
            channel=channel,
            sample_rate=1.0 / xincr if xincr else None,
            record_length=len(codes),
            timebase=timebase,
            voltage_scale=voltage_scale,
        )


# WAVEDESC field offsets, per the MAUI remote manual's TEMPLATE? definition.
_WAVEDESC_COMM_TYPE = 32  # int16: 0 = byte, 1 = word
_WAVEDESC_DESC_LEN = 36  # int32: descriptor block length (typ. 346)
_WAVEDESC_USER_TEXT_LEN = 40  # int32
_WAVEDESC_TRIGTIME_LEN = 48  # int32: TRIGTIME_ARRAY byte length (0 unless sequence/segment mode)
_WAVEDESC_RISTIME_LEN = 52  # int32: RIS_TIME_ARRAY byte length (0 unless RIS mode)
_WAVEDESC_ARRAY_COUNT = 116  # int32: number of samples
_WAVEDESC_VERTICAL_GAIN = 156  # float32
_WAVEDESC_VERTICAL_OFFSET = 160  # float32
_WAVEDESC_HORIZ_INTERVAL = 176  # float32
_WAVEDESC_HORIZ_OFFSET = 180  # float64


def parse_wavedesc(payload: bytes, *, error_context: str = "") -> dict:
    """Parse the WAVEDESC descriptor out of a LeCroy WF? ALL payload (CORD LO)."""
    start = payload.find(b"WAVEDESC")
    if start == -1:
        message = "Invalid LeCroy waveform: no WAVEDESC descriptor found"
        raise exceptions.CommandError(f"{message} ({error_context})" if error_context else message)
    desc_len = struct.unpack_from("<i", payload, start + _WAVEDESC_DESC_LEN)[0]
    user_text_len = struct.unpack_from("<i", payload, start + _WAVEDESC_USER_TEXT_LEN)[0]
    # Per the WAVEDESC template, DATA_ARRAY_1 follows WAVEDESC + USER_TEXT +
    # TRIGTIME_ARRAY + RIS_TIME_ARRAY. The two array lengths are 0 for a plain
    # single-shot capture but non-zero in sequence/RIS modes, and must be
    # skipped or the sample data is read from the wrong offset.
    trigtime_len = struct.unpack_from("<i", payload, start + _WAVEDESC_TRIGTIME_LEN)[0]
    ristime_len = struct.unpack_from("<i", payload, start + _WAVEDESC_RISTIME_LEN)[0]
    return {
        "comm_type": struct.unpack_from("<h", payload, start + _WAVEDESC_COMM_TYPE)[0],
        "desc_len": desc_len,
        "user_text_len": user_text_len,
        "trigtime_len": trigtime_len,
        "ristime_len": ristime_len,
        "wave_array_count": struct.unpack_from("<i", payload, start + _WAVEDESC_ARRAY_COUNT)[0],
        "vertical_gain": struct.unpack_from("<f", payload, start + _WAVEDESC_VERTICAL_GAIN)[0],
        "vertical_offset": struct.unpack_from("<f", payload, start + _WAVEDESC_VERTICAL_OFFSET)[0],
        "horiz_interval": struct.unpack_from("<f", payload, start + _WAVEDESC_HORIZ_INTERVAL)[0],
        "horiz_offset": struct.unpack_from("<d", payload, start + _WAVEDESC_HORIZ_OFFSET)[0],
        "data_offset": start + desc_len + user_text_len + trigtime_len + ristime_len,
    }


class LeCroyTransfer:
    """WF? ALL transfer scaled by the WAVEDESC descriptor (MAUI remote manual)."""

    def __init__(self, scope: "Oscilloscope"):
        self._scope = scope

    def acquire(self, channel: int, format: str = "BYTE", stride: Optional[int] = None) -> WaveformData:
        """Acquire waveform data from a channel via WF? ALL.

        Args:
            channel: Channel number (1-4)
            format: Data format - 'BYTE' or 'WORD'
            stride: Unused on this dialect -- no documented LeCroy equivalent
                to :WAVeform:INTerval. Accepted only so callers can pass it
                uniformly regardless of which transfer make_transfer()
                selected.
        """
        scope = self._scope
        fmt = "WORD" if format.upper() == "WORD" else "BYTE"
        scope.write(scope._get_command("set_comm_format", fmt=fmt))
        scope.write(scope._get_command("set_comm_order"))
        command = scope._get_command("get_waveform", ch=channel)
        with scope._connection.lock:
            scope.write(command)
            raw = scope.read_raw()
        context = f"host {scope.host}:{scope.port}, command '{command}'"
        payload = parse_ieee_block(raw, np.uint8, error_context=context).tobytes()
        meta = parse_wavedesc(payload, error_context=context)
        dtype = np.int16 if meta["comm_type"] == 1 else np.int8
        codes = np.frombuffer(payload, dtype=dtype, count=meta["wave_array_count"], offset=meta["data_offset"])
        voltage = meta["vertical_gain"] * codes.astype(np.float64) - meta["vertical_offset"]
        time = meta["horiz_offset"] + np.arange(len(codes)) * meta["horiz_interval"]
        logger.info(f"Acquired {len(codes)} samples from channel {channel} (lecroy)")
        return WaveformData(
            time=time,
            voltage=voltage,
            channel=channel,
            sample_rate=1.0 / meta["horiz_interval"] if meta["horiz_interval"] else None,
            record_length=len(codes),
            timebase=scope.waveform._get_timebase(),
            voltage_scale=scope.waveform._get_voltage_scale(f"C{channel}"),
        )


# Modern-dialect WAVEDESC field offsets -- SDS Series Programming Guide EN11G
# p.755-756 (Table 1). Structurally the same 346-byte WAVEDESC layout as the
# LeCroy descriptor above (_WAVEDESC_* constants), but kept as its own table:
# the modern voltage formula (ModernTransfer.acquire, below) reads an
# EXPLICIT code_per_div field the LeCroy path never touches, and the two
# dialects must stay independently editable (Task 15 vs Task 18).
_MODERN_COMM_TYPE = 32  # short: 0=byte, 1=word
_MODERN_WAVE_ARRAY_COUNT = 116  # long: number of data points
_MODERN_DATA_INTERVAL = 136  # long: = :WAVeform:INTerval, echoed back (p.755)
_MODERN_VERTICAL_GAIN = 156  # float: V/div, no probe attenuation
_MODERN_VERTICAL_OFFSET = 160  # float
_MODERN_CODE_PER_DIV = 164  # float
_MODERN_HORIZ_INTERVAL = 176  # float: 1/sample_rate
_MODERN_HORIZ_OFFSET = 180  # double: trigger offset, seconds


def parse_modern_wavedesc(payload: bytes, *, error_context: str = "") -> dict:
    """Parse the WAVEDESC out of a modern-dialect :WAVeform:PREamble? response.

    SDS Series Programming Guide EN11G p.755-756 (Table 1). Unlike the LeCroy
    WAVEDESC (parse_wavedesc above), the modern descriptor's vertical_gain is
    "the value of vertical scale [...] without probe attenuation" (V/div) and
    a SEPARATE code_per_div field is needed to turn it into volts/code -- see
    the p.758 worked formula in ModernTransfer.acquire below.
    """

    def _err(message: str) -> str:
        return f"{message} ({error_context})" if error_context else message

    if len(payload) < _MODERN_HORIZ_OFFSET + 8:
        raise exceptions.CommandError(_err(f"Invalid modern WAVEDESC: expected at least {_MODERN_HORIZ_OFFSET + 8} bytes, got {len(payload)}"))
    return {
        "comm_type": struct.unpack_from("<h", payload, _MODERN_COMM_TYPE)[0],
        "wave_array_count": struct.unpack_from("<i", payload, _MODERN_WAVE_ARRAY_COUNT)[0],
        # Echoed back purely so acquire() can cross-check it against the
        # stride it actually requested -- see the DATA_INTERVAL mismatch
        # warning below. Not otherwise used to scale anything.
        "data_interval": struct.unpack_from("<i", payload, _MODERN_DATA_INTERVAL)[0],
        "vertical_gain": struct.unpack_from("<f", payload, _MODERN_VERTICAL_GAIN)[0],
        "vertical_offset": struct.unpack_from("<f", payload, _MODERN_VERTICAL_OFFSET)[0],
        "code_per_div": struct.unpack_from("<f", payload, _MODERN_CODE_PER_DIV)[0],
        "horiz_interval": struct.unpack_from("<f", payload, _MODERN_HORIZ_INTERVAL)[0],
        "horiz_offset": struct.unpack_from("<d", payload, _MODERN_HORIZ_OFFSET)[0],
    }


_DATA_INTERVAL_STATE_ATTR = "_data_interval_mismatch_state"


def _note_data_interval_mismatch(scope: "Oscilloscope", channel: int, requested: int, reported: int) -> None:
    """Once-per-transition warning for a DATA_INTERVAL echo that disagrees
    with the stride we asked for (see ModernTransfer.acquire above).

    This runs on every acquire() -- including stride==1 on the export path --
    so logging every call would write one WARNING per frame, indefinitely, at
    up to four frames a second if real hardware's echo disagreed persistently.
    Same discipline as the poll-path fix in server/adapters.py: one WARNING
    when the mismatch starts, one recovery WARNING when it stops (same level,
    deliberately -- an operator or alert filtering at WARNING must see the
    disagreement both start AND clear, or the log is exactly as ambiguous as
    it was before this fix for that reader), nothing while it persists.

    State is stored ON THE SCOPE INSTANCE, keyed by channel, rather than on
    `self` of the calling Transfer: make_transfer() builds a brand new
    ModernTransfer for every single acquire() call (see waveform.py's
    Waveform.acquire), so there is no longer-lived Transfer object to carry
    the previous call's state across. The Oscilloscope instance IS session-
    long, and keying by channel keeps a mismatching channel 1 and a healthy
    channel 2 from flapping each other's state.
    """
    # Sets `scope._data_interval_mismatch_state` (a private dict, keyed by
    # channel) on the Oscilloscope instance passed in as `scope` -- an
    # attribute this module injects rather than one declared in
    # Oscilloscope.__init__. It has to live somewhere that outlives a single
    # acquire() call, and the ModernTransfer instance calling this function
    # does not (see the docstring above); the scope instance is the only
    # object here that does.
    state = getattr(scope, _DATA_INTERVAL_STATE_ATTR, None)
    if state is None:
        state = {}
        setattr(scope, _DATA_INTERVAL_STATE_ATTR, state)
    mismatched = reported != requested
    was_mismatched = state.get(channel, False)
    if mismatched and not was_mismatched:
        logger.warning(
            "Requested :WAVeform:INTerval %d but PREamble reported DATA_INTERVAL %d (host %s:%s, channel %d) -- the returned record length/time axis may not be scaled the way this driver assumes.",
            requested,
            reported,
            scope.host,
            scope.port,
            channel,
        )
    elif not mismatched and was_mismatched:
        logger.warning(
            "DATA_INTERVAL now matches the requested :WAVeform:INTerval %d again (host %s:%s, channel %d) -- the prior mismatch has cleared.",
            requested,
            scope.host,
            scope.port,
            channel,
        )
    state[channel] = mismatched


class ModernTransfer:
    """:WAVeform: SOURce/PREamble/DATA/MAXPoint transfer for modern-dialect Siglent scopes.

    SDS Series Programming Guide EN11G pp.748-758 (audit H9, Task 18): the
    legacy "C{ch}:WF? DAT2" transfer has ZERO occurrences anywhere in this
    855-page guide (full-text search). This class replaces it for
    dialect="modern" scopes; SiglentTransfer above is unchanged and keeps
    serving dialect="legacy" scopes.

    Task 19 (deep-memory chunking, p.753): a single :WAVeform:DATA? transfer
    is capped at :WAVeform:MAXPoint points; acquire() below reads the
    PREamble's wave_array_count (the FULL record length) and loops
    :WAVeform:STARt in MAXPoint-sized windows until the whole record is read.

    Task 3 stride follow-up: that STARt-driven loop is only correct when
    stride is 1 (`start` is advanced by the count of points already
    delivered, which is the same space as :WAVeform:STARt only when nothing
    is being decimated). A stride > 1 therefore takes a DIFFERENT, narrower
    path below: a single, unlooped window sized to the (already strided)
    record length, since the live view's <= MAX_FRAME_POINTS request is far
    below any real :WAVeform:MAXPoint. If a strided record ever needed more
    than one window, acquire() raises rather than mis-assemble it -- the
    general chunking loop is deliberately NOT made stride-aware, so the
    proven stride=1/export path is untouched.
    """

    def __init__(self, scope: "Oscilloscope"):
        self._scope = scope

    def acquire(self, channel: int, format: str = "BYTE", stride: Optional[int] = None) -> WaveformData:
        """Acquire waveform data from a channel via :WAVeform:SOURce/PREamble/DATA.

        Args:
            channel: Channel number (1-4)
            format: Data format - 'BYTE' or 'WORD' (default: 'BYTE'); sets
                :WAVeform:WIDTh before the transfer so COMM_TYPE in the
                preamble matches what DATA? actually sends.
            stride: Sets :WAVeform:INTerval before the transfer so the
                instrument returns every Nth point instead of the driver
                pulling the full record and striding it down after the wire
                transfer. :WAVeform:INTerval is instrument state, not a
                per-request argument -- a value left over from a previous
                caller (e.g. the live view) would silently decimate the next
                export on this session. So this is ALWAYS written explicitly,
                including when stride is None, which writes 1 (no
                decimation) rather than leaving whatever was last set.

        Returns:
            WaveformData scaled by the PREamble's vertical_gain/
            vertical_offset/code_per_div (volts) and horiz_offset/
            horiz_interval (time). For a record longer than
            :WAVeform:MAXPoint, the codes from every window are concatenated
            in STARt order before scaling, so the returned arrays cover the
            entire record_length, not just the first window.

        Raises:
            InvalidParameterError: If a non-BYTE/WORD format is requested, or
                stride is not a positive integer.
            CommandError: If either binary block is malformed.
            FeatureNotSupportedError: If a stride > 1 would need more than one
                :WAVeform:DATA? window (see the class docstring) -- this is a
                loud refusal rather than a silently mis-assembled read.
        """
        format = format.upper()
        if format not in ("BYTE", "WORD"):
            raise exceptions.InvalidParameterError(f"Invalid format: {format}")
        if stride is not None and stride < 1:
            raise exceptions.InvalidParameterError(f"stride must be a positive integer (got {stride})")
        # int(...), not just `stride or 1`: a float stride (e.g. a caller's
        # ceil-division producing 2.5 -- or 2.0, benign here but not
        # guaranteed elsewhere) must not be written to the wire as-is, since
        # :WAVeform:INTerval is a real SCPI command argument, not a Python
        # value.
        effective_stride = int(stride) if stride else 1
        scope = self._scope

        # Source (and width) must be selected before PREamble?/DATA? read
        # them back -- both act "using the source specified by
        # :WAVeform:SOURce" (guide p.748/p.754).
        scope.write(scope._get_command("set_waveform_source", ch=channel))
        scope.write(scope._get_command("set_waveform_width", value=format))

        if scope._has_command("set_waveform_interval"):
            # Always explicit, never inherited: see the stride docstring note
            # above on interval being instrument state rather than a
            # per-request argument. Guarded so a future dialect without the
            # command (were one ever routed through ModernTransfer) is
            # unaffected rather than raising KeyError. Written BEFORE the
            # PREamble? read below -- load-bearing, not incidental: the
            # preamble must be read back under the interval this call asked
            # for, not whatever a previous caller (e.g. the live view) left
            # set, or that stride would leak into this read.
            #
            # DO NOT "optimize" this to skip the write when the value hasn't
            # changed, or when stride is None -- that reintroduces the exact
            # leak this comment warns about, silently. The guard is
            # tests/test_oscilloscope_waveform_stride.py::
            # test_a_stride_left_over_from_a_prior_read_does_not_leak_into_the_next_one,
            # which pins the observable failure (a strided read followed by a
            # plain read on the same connection must return the FULL record).
            # Confirmed by mutation test (Task 7): making this write
            # conditional on `stride is not None` makes that test fail with
            # 143 points back instead of 1000.
            scope.write(scope._get_command("set_waveform_interval", value=effective_stride))

        with scope._connection.lock:
            scope.write(scope._get_command("get_waveform_preamble"))
            preamble_raw = scope.read_raw()
        preamble_context = f"host {scope.host}:{scope.port}, command ':WAVeform:PREamble?'"
        preamble_payload = parse_ieee_block(preamble_raw, np.uint8, error_context=preamble_context).tobytes()
        meta = parse_modern_wavedesc(preamble_payload, error_context=preamble_context)

        if meta["code_per_div"] == 0:
            raise exceptions.CommandError(f"Modern WAVEDESC code_per_div is 0 ({preamble_context})")

        # The one thing code cannot settle: whether a real instrument's
        # DATA_INTERVAL echo (and therefore its HORIZ_INTERVAL scaling, used
        # below for the time axis) actually reflects the stride we requested.
        # A mismatch must not be invisible -- log it, but don't raise; a
        # disagreement here is a scaling risk, not a malformed read. This runs
        # on EVERY acquire(), including stride==1 on the export path, so the
        # cadence has to be once-per-transition rather than once-per-call: a
        # real instrument that disagreed persistently would otherwise log one
        # WARNING per frame, indefinitely, at up to four frames a second.
        _note_data_interval_mismatch(scope, channel, effective_stride, meta["data_interval"])

        dtype = np.int16 if meta["comm_type"] == 1 else np.int8
        # wave_array_count (WAVEDESC address 116-119, p.756) is "Number of
        # data points in the data array". ASSUMPTION (Task 3 stride
        # follow-up, not yet confirmed against real hardware): when stride >
        # 1, this is the STRIDED count, not the full record's -- see the
        # mock's build_waveform_preamble docstring for why. It is still the
        # FULL record when stride == 1, even when a single :WAVeform:DATA?
        # transfer cannot carry all of it at once.
        record_length = meta["wave_array_count"]

        # :WAVeform:MAXPoint? (p.753) is Query-only: the scope reports its own
        # per-transfer cap, there is no setter. int(float(...)) matches this
        # module's existing NR1/NR3-tolerant parsing (see TektronixTransfer's
        # get_wfm_nr_pt above).
        max_points = int(float(scope.query(scope._get_command("get_waveform_maxpoint"))))
        if max_points <= 0:
            # A malformed/zero response must not spin the loop forever --
            # fall back to reading the whole record in one window.
            max_points = max(record_length, 1)

        data_context = f"host {scope.host}:{scope.port}, command ':WAVeform:DATA?'"

        if effective_stride == 1:
            # The proven export path: completely unchanged from before
            # stride existed.
            chunks = []
            start = 0
            while start < record_length:
                # STARt and DATA? are coupled (DATA? answers "using the source
                # specified by :WAVeform:SOURce" AND the current STARt window),
                # so both live under one lock acquisition -- same reasoning as
                # the preamble read above, extended to cover the write that picks
                # which window DATA? answers with.
                with scope._connection.lock:
                    scope.write(scope._get_command("set_waveform_start", value=start))
                    scope.write(scope._get_command("get_waveform_data"))
                    data_raw = scope.read_raw()
                chunk = parse_ieee_block(data_raw, dtype, error_context=data_context)
                if chunk.size == 0:
                    # A well-behaved instrument only returns an empty window at
                    # end-of-record, which the `while` condition above already
                    # excludes -- this guards against a non-conformant one
                    # instead of looping forever.
                    break
                chunks.append(chunk)
                start += chunk.size

            codes = np.concatenate(chunks) if chunks else np.array([], dtype=dtype)
        else:
            # Deliberately NOT the general chunking loop, and deliberately not
            # made stride-aware: `start` there is advanced by chunk.size (points
            # already delivered, in the STRIDED/transmitted space) but written
            # to :WAVeform:STARt and compared against record_length -- the same
            # space as chunk.size only when stride is 1. Beyond one window, a
            # second iteration would re-request source points the first window
            # already delivered, silently duplicating a stretch of the record
            # (and building `time` over the wrong `n`). The live view's request
            # is always <= MAX_FRAME_POINTS, far below any real MAXPoint, so a
            # single window covers every case it actually needs; a strided read
            # that would not fit raises instead of mis-assembling.
            if record_length > max_points:
                raise exceptions.FeatureNotSupportedError(
                    f"Strided read of {record_length} points (stride={effective_stride}) exceeds "
                    f"this instrument's per-transfer cap of {max_points} points (:WAVeform:MAXPoint?); "
                    f"multi-window strided reads are not supported ({data_context})"
                )
            with scope._connection.lock:
                scope.write(scope._get_command("set_waveform_start", value=0))
                scope.write(scope._get_command("get_waveform_data"))
                data_raw = scope.read_raw()
            codes = parse_ieee_block(data_raw, dtype, error_context=data_context)

            # A short window here is the one failure that would otherwise be
            # INVISIBLE. Unlike the stride==1 branch above, nothing loops to
            # collect a remainder, and `n = len(codes)` below sizes the time
            # axis off whatever did arrive -- so a truncated record comes back
            # looking perfectly well-formed, just quietly missing its tail.
            # Nothing in this driver writes :WAVeform:POINt, but it is
            # instrument state like :WAVeform:INTerval, and another program on
            # the same scope (EasyScopeX, a colleague's LabVIEW driver) can
            # leave it small. Same principle as the interval write above: this
            # read verifies the state it depends on rather than trusting it.
            #
            # CAUTION: this compares against wave_array_count, which is only
            # the STRIDED count under the p.756 assumption flagged at
            # `record_length` above -- still unconfirmed on real hardware. If
            # a real instrument instead reports the FULL record here, this
            # raises on every strided frame (a live-view outage, the failure
            # mode waveform_max_points() warns about) rather than on the
            # truncation it is meant to catch. That is the FIRST thing to
            # check against the scope if the live view starts refusing.
            if codes.size < record_length:
                raise exceptions.CommandError(
                    f"Strided read returned {codes.size} points but the preamble's "
                    f"WAVE_ARRAY_COUNT says {record_length} (stride={effective_stride}); "
                    f"a :WAVeform:POINt window cap left set by another program is the "
                    f"likeliest cause -- refusing to scale a truncated record into a "
                    f"time axis that would look correct ({data_context})"
                )

        # SDS Series Programming Guide EN11G p.758 ("Read Waveform Data",
        # analog example, Step 3): "voltage value (V) = code value
        # *(vdiv /code_per_div) - voffset". vdiv/voffset/code_per_div are the
        # PREamble's vertical_gain/vertical_offset/code_per_div fields
        # (WAVEDESC addresses 156-159/160-163/164-167). Confirmed against the
        # guide's own worked numbers: code=-11, vdiv=10, code_per_div=30,
        # voffset=14.5 -> -11*(10/30)-14.5 = -18.167 V, matching the guide's
        # own printed "-18.167 V" exactly.
        voltage = codes.astype(np.float64) * (meta["vertical_gain"] / meta["code_per_div"]) - meta["vertical_offset"]

        # SDS Series Programming Guide EN11G p.759 ("Read Waveform Data",
        # Step 4): "time value(S) = delay-(timebase*grid/2)+index*interval".
        # delay/interval are the PREamble's horiz_offset/horiz_interval;
        # "timebase" (s/div) is read via the existing :TIMebase:SCALe? getter
        # rather than decoded from the WAVEDESC's Timebase field (address
        # 324-325), which is a MODEL-DEPENDENT enumerated index into a table
        # this guide explicitly says is not universal ("Different models have
        # different time base enumeration", p.756, Table 2) -- decoding it
        # would mean inventing a mapping the guide itself withholds.
        # grid=10 for the SDS800X HD/SDS5000X/SDS2000X families this project
        # targets (p.759); SHS800X/SHS1000X use 12 and are out of scope.
        #
        # NOTE: this is NOT "horiz_offset + i*interval" (a simpler-looking but
        # WRONG equivalence) -- verified against the guide's own worked
        # example (delay=1.72E-8, timebase=20E-9, interval=2E-10): the
        # documented first-point time is -8.28E-08 s, which only the
        # delay-(timebase*grid/2) form reproduces.
        grid = 10
        timebase = scope.waveform._get_timebase()
        n = len(codes)
        time = meta["horiz_offset"] - (timebase * grid / 2) + np.arange(n) * meta["horiz_interval"]

        logger.info(f"Acquired {n} samples from channel {channel} (modern)")
        return WaveformData(
            time=time,
            voltage=voltage,
            channel=channel,
            sample_rate=(1.0 / meta["horiz_interval"]) if meta["horiz_interval"] else None,
            record_length=n,
            timebase=timebase,
            voltage_scale=meta["vertical_gain"],
            voltage_offset=meta["vertical_offset"],
        )


def make_transfer(scope: "Oscilloscope"):
    """Select the waveform transfer strategy for a connected scope's dialect."""
    dialect = getattr(scope, "dialect", None) or "legacy"
    if dialect == "tektronix":
        return TektronixTransfer(scope)
    if dialect == "lecroy":
        return LeCroyTransfer(scope)
    if dialect == "modern":
        return ModernTransfer(scope)
    return SiglentTransfer(scope)
