"""Per-dialect waveform transfer strategies.

Siglent (both dialects) speaks WF? DAT2 with fixed code-per-division scaling;
Tektronix speaks the CURVe protocol scaled by the WFMOutpre preamble; LeCroy
(Task 15) speaks WF? ALL scaled by the WAVEDESC descriptor. The IEEE-488.2
definite-length block framing is shared by all of them.
"""

import logging
import re
import struct
from typing import TYPE_CHECKING

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

    def acquire(self, channel: int, format: str = "BYTE") -> WaveformData:
        """Acquire waveform data from a channel via WF? DAT2.

        Args:
            channel: Channel number (1-4)
            format: Data format - 'BYTE' or 'WORD' (default: 'BYTE')

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

    def acquire(self, channel: int, format: str = "BYTE") -> WaveformData:
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
_WAVEDESC_COMM_TYPE = 32       # int16: 0 = byte, 1 = word
_WAVEDESC_DESC_LEN = 36        # int32: descriptor block length (typ. 346)
_WAVEDESC_USER_TEXT_LEN = 40   # int32
_WAVEDESC_TRIGTIME_LEN = 48    # int32: TRIGTIME_ARRAY byte length (0 unless sequence/segment mode)
_WAVEDESC_RISTIME_LEN = 52     # int32: RIS_TIME_ARRAY byte length (0 unless RIS mode)
_WAVEDESC_ARRAY_COUNT = 116    # int32: number of samples
_WAVEDESC_VERTICAL_GAIN = 156  # float32
_WAVEDESC_VERTICAL_OFFSET = 160  # float32
_WAVEDESC_HORIZ_INTERVAL = 176   # float32
_WAVEDESC_HORIZ_OFFSET = 180     # float64


def parse_wavedesc(payload: bytes, *, error_context: str = "") -> dict:
    """Parse the WAVEDESC descriptor out of a LeCroy WF? ALL payload (CORD LO)."""
    start = payload.find(b"WAVEDESC")
    if start == -1:
        raise exceptions.CommandError(f"Invalid LeCroy waveform: no WAVEDESC descriptor found ({error_context})")
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

    def acquire(self, channel: int, format: str = "BYTE") -> WaveformData:
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


def make_transfer(scope: "Oscilloscope"):
    """Select the waveform transfer strategy for a connected scope's dialect."""
    dialect = getattr(scope, "dialect", None) or "legacy"
    if dialect == "tektronix":
        return TektronixTransfer(scope)
    if dialect == "lecroy":
        return LeCroyTransfer(scope)
    return SiglentTransfer(scope)
