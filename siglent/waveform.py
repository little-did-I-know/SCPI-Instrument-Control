"""Waveform acquisition and data processing for Siglent oscilloscopes."""

import logging
import re
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple, Union

import numpy as np

from siglent import exceptions

if TYPE_CHECKING:
    from siglent.oscilloscope import Oscilloscope

logger = logging.getLogger(__name__)

# Waveform conversion constants from Siglent SCPI programming manual
# These constants are used to convert raw ADC codes to voltage values
WAVEFORM_CODE_PER_DIV_8BIT = 25.0  # Codes per vertical division for 8-bit ADC
WAVEFORM_CODE_PER_DIV_16BIT = 6400.0  # Codes per vertical division for 16-bit ADC
WAVEFORM_CODE_CENTER = 0  # Center code value for signed integer ADC data


@dataclass
class WaveformData:
    """Container for waveform data and metadata.

    Attributes:
        time: Time values in seconds (numpy array)
        voltage: Voltage values in volts (numpy array)
        channel: Source channel number
        sample_rate: Sampling rate in samples/second
        record_length: Number of samples
        timebase: Timebase setting (seconds/division)
        voltage_scale: Voltage scale (volts/division)
        voltage_offset: Voltage offset in volts
    """

    time: np.ndarray
    voltage: np.ndarray
    channel: Union[int, str]
    sample_rate: Optional[float] = None
    record_length: Optional[int] = None
    timebase: Optional[float] = None
    voltage_scale: Optional[float] = None
    voltage_offset: float = 0.0
    source: Optional[str] = None
    description: Optional[str] = None

    def __len__(self) -> int:
        """Get number of samples."""
        return len(self.voltage)

    def __post_init__(self) -> None:
        """Validate and populate optional metadata."""
        if self.time.shape != self.voltage.shape:
            raise ValueError("Time and voltage arrays must have the same shape")

        # Ensure record length is always populated
        if self.record_length is None:
            self.record_length = len(self.voltage)

        # Estimate sample rate from time axis if not provided
        if self.sample_rate is None and len(self.time) > 1:
            dt = float(np.mean(np.diff(self.time)))
            if dt > 0:
                self.sample_rate = 1.0 / dt

        # Estimate timebase using standard 14 horizontal divisions if possible
        if self.timebase is None and self.sample_rate:
            total_time = self.record_length / self.sample_rate
            self.timebase = total_time / 14.0

        # Infer a reasonable voltage scale when none is supplied
        if self.voltage_scale is None:
            if len(self.voltage) > 0:
                span = float(np.max(self.voltage) - np.min(self.voltage))
                # Standard 8 vertical divisions on most scopes
                self.voltage_scale = span / 8.0 if span > 0 else 1.0
            else:
                self.voltage_scale = 1.0


class Waveform:
    """Waveform acquisition and data processing.

    Handles downloading waveform data from oscilloscope channels and
    converting to voltage/time arrays.
    """

    def __init__(self, oscilloscope: "Oscilloscope"):
        """Initialize waveform acquisition.

        Args:
            oscilloscope: Parent Oscilloscope instance
        """
        self._scope = oscilloscope

    def acquire(self, channel: int, format: str = "BYTE") -> WaveformData:
        """Acquire waveform data from a channel.

        Args:
            channel: Channel number (1-4)
            format: Data format - 'BYTE' or 'WORD' (default: 'BYTE')

        Returns:
            WaveformData object with time and voltage arrays

        Raises:
            InvalidParameterError: If channel number is invalid
            CommandError: If acquisition fails
        """
        if not 1 <= channel <= 4:
            raise exceptions.InvalidParameterError(f"Invalid channel number: {channel}. Must be 1-4.")

        logger.info(f"Acquiring waveform from channel {channel}")

        # Get channel configuration
        ch = f"C{channel}"
        voltage_scale = self._get_voltage_scale(ch)
        voltage_offset = self._get_voltage_offset(ch)
        timebase = self._get_timebase()
        sample_rate = self._get_sample_rate()

        # Request waveform data
        waveform_command = f"{ch}:WF? DAT2"  # DAT2 is binary format
        self._scope.write(waveform_command)

        # Read waveform data header and data
        raw_data = self._scope.read_raw()

        # Parse waveform data
        voltage_data = self._parse_waveform(raw_data, format, waveform_command)
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

    def _get_voltage_scale(self, channel: str) -> float:
        """Get voltage scale for channel.

        Args:
            channel: Channel name (e.g., 'C1')

        Returns:
            Voltage scale in V/div
        """
        command = f"{channel}:VDIV?"
        response = self._scope.query(command)
        logger.debug(f"Voltage scale response: '{response}'")

        return self._parse_value_with_units(response, ("V",), "voltage scale", command=command)

    def _get_voltage_offset(self, channel: str) -> float:
        """Get voltage offset for channel.

        Args:
            channel: Channel name (e.g., 'C1')

        Returns:
            Voltage offset in volts
        """
        command = f"{channel}:OFST?"
        response = self._scope.query(command)
        logger.debug(f"Voltage offset response: '{response}'")

        return self._parse_value_with_units(response, ("V",), "voltage offset", command=command)

    def _get_timebase(self) -> float:
        """Get timebase setting.

        Returns:
            Timebase in seconds/division
        """
        command = "TDIV?"
        response = self._scope.query(command)
        logger.debug(f"Timebase response: '{response}'")

        return self._parse_value_with_units(response, ("S",), "timebase", command=command)

    def _get_sample_rate(self) -> float:
        """Get sample rate.

        Returns:
            Sample rate in samples/second
        """
        command = "SARA?"
        response = self._scope.query(command)
        logger.debug(f"Sample rate response: '{response}'")

        return self._parse_value_with_units(response, ("SA/S", "SPS"), "sample rate", command=command)

    def _format_scope_error(self, message: str, command: Optional[str] = None) -> str:
        """Append host/command context to error messages for clarity."""

        context = f"{self._scope.host}:{self._scope.port}"
        if command:
            return f"{message} (host {context}, command '{command}')"
        return f"{message} (host {context})"

    def _parse_waveform(self, raw_data: bytes, format: str = "BYTE", command: Optional[str] = None) -> np.ndarray:
        """Parse waveform data from oscilloscope.

        Args:
            raw_data: Raw binary data from oscilloscope
            format: Data format - 'BYTE' or 'WORD'

        Returns:
            Numpy array of raw data codes
        """
        # Siglent waveform format:
        # Header: DESC,#9000000346...
        # Find the start of binary data (after header)

        if not raw_data:
            raise exceptions.CommandError(self._format_scope_error("Invalid waveform format: empty response", command))

        # Look for the # character indicating block data
        header_end = raw_data.find(b"#")
        if header_end == -1:
            raise exceptions.CommandError(self._format_scope_error("Invalid waveform format: no # found in block header", command))

        if header_end + 2 > len(raw_data):
            raise exceptions.CommandError(self._format_scope_error("Invalid waveform format: truncated block header", command))

        # Parse IEEE 488.2 definite length block
        # Format: #<n><length><data>
        # where n is number of digits in length
        n_digit_char = chr(raw_data[header_end + 1])
        if not n_digit_char.isdigit():
            raise exceptions.CommandError(self._format_scope_error(f"Invalid waveform format: non-numeric length digit '{n_digit_char}'", command))

        n_digits = int(n_digit_char)
        if n_digits <= 0:
            raise exceptions.CommandError(
                self._format_scope_error(
                    f"Invalid waveform format: length digit must be positive (got {n_digits})",
                    command,
                )
            )

        length_field_start = header_end + 2
        length_field_end = length_field_start + n_digits
        if length_field_end > len(raw_data):
            raise exceptions.CommandError(self._format_scope_error("Invalid waveform format: truncated length field", command))

        length_field = raw_data[length_field_start:length_field_end]
        if not re.fullmatch(rb"\d+", length_field):
            raise exceptions.CommandError(
                self._format_scope_error(
                    f"Invalid waveform format: non-numeric length field '{length_field.decode(errors='ignore')}'",
                    command,
                )
            )

        data_length = int(length_field)
        data_start = length_field_end
        data_end = data_start + data_length

        if data_end > len(raw_data):
            raise exceptions.CommandError(self._format_scope_error("Invalid waveform format: declared data length exceeds available data", command))

        # Extract binary data
        binary_data = raw_data[data_start:data_end]

        # Convert to numpy array
        if format == "BYTE":
            # 8-bit signed data
            data = np.frombuffer(binary_data, dtype=np.int8)
        elif format == "WORD":
            # 16-bit signed data
            if data_length % 2:
                raise exceptions.CommandError(self._format_scope_error("Invalid waveform format: WORD data length must be even", command))
            data = np.frombuffer(binary_data, dtype=np.int16)
        else:
            raise exceptions.InvalidParameterError(f"Invalid format: {format}")

        return data

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

    def _parse_value_with_units(
        self,
        response: str,
        expected_units: Tuple[str, ...],
        quantity: str,
        command: Optional[str] = None,
    ) -> float:
        """Parse numeric values with expected units from SCPI responses.

        Args:
            response: Raw response string from the oscilloscope.
            expected_units: Tuple of acceptable unit suffixes (case-insensitive).
            quantity: Human-readable name of the value being parsed (for error messages).

        Returns:
            Parsed floating-point value.

        Raises:
            CommandError: If parsing fails or expected units are missing.
        """
        logger.debug(f"Parsing {quantity} from response '{response}' with expected units {expected_units}")

        def _strip_prefix(value: str) -> str:
            value = value.strip()
            if ":" in value:
                value = value.split(":", 1)[1].strip()
            if " " in value:
                parts = value.split(None, 1)
                if len(parts) > 1:
                    value = parts[1].strip()
            return value

        cleaned = _strip_prefix(response)
        cleaned_upper = cleaned.upper()

        for unit in expected_units:
            unit_upper = unit.upper()
            if cleaned_upper.endswith(unit_upper):
                numeric_part = cleaned_upper[: -len(unit_upper)].strip()
                try:
                    value = float(numeric_part)
                    logger.debug(f"Parsed {quantity}: {value} {unit}")
                    return value
                except ValueError as exc:
                    raise exceptions.CommandError(self._format_scope_error(f"Invalid {quantity} response: '{response}'", command)) from exc

        expected = " or ".join(expected_units)
        raise exceptions.CommandError(self._format_scope_error(f"Invalid {quantity} response: '{response}' (expected units: {expected})", command))

    def get_waveform_preamble(self, channel: int) -> dict:
        """Get waveform preamble information.

        Args:
            channel: Channel number (1-4)

        Returns:
            Dictionary with waveform metadata
        """
        if not 1 <= channel <= 4:
            raise exceptions.InvalidParameterError(f"Invalid channel number: {channel}. Must be 1-4.")

        ch = f"C{channel}"

        return {
            "channel": channel,
            "voltage_scale": self._get_voltage_scale(ch),
            "voltage_offset": self._get_voltage_offset(ch),
            "timebase": self._get_timebase(),
            "sample_rate": self._get_sample_rate(),
        }

    def save_waveform(
        self,
        waveform: WaveformData,
        filename: str,
        format: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Save waveform data to file.

        Args:
            waveform: WaveformData object to save
            filename: Output filename
            format: File format - 'CSV', 'CSV_ENHANCED', 'NPY', 'MAT', 'HDF5'
                   If None, auto-detect from file extension
            metadata: Optional metadata dictionary to include in file

        Supported formats:
            - CSV: Simple CSV with time and voltage columns
            - CSV_ENHANCED: CSV with metadata header
            - NPY: NumPy compressed archive (.npz)
            - MAT: MATLAB format (.mat) - requires scipy
            - HDF5: HDF5 format (.h5, .hdf5) - requires h5py
        """
        # Auto-detect format from extension if not specified
        if format is None:
            import os

            ext = os.path.splitext(filename)[1].lower()
            format_map = {
                ".csv": "CSV",
                ".npz": "NPY",
                ".npy": "NPY",
                ".mat": "MAT",
                ".h5": "HDF5",
                ".hdf5": "HDF5",
            }
            format = format_map.get(ext, "CSV")
            logger.debug(f"Auto-detected format: {format} from extension {ext}")

        format = format.upper()

        if format == "CSV":
            self._save_csv(waveform, filename, include_metadata=False, metadata=metadata)

        elif format == "CSV_ENHANCED":
            self._save_csv(waveform, filename, include_metadata=True, metadata=metadata)

        elif format == "NPY":
            self._save_npy(waveform, filename, metadata=metadata)

        elif format == "MAT":
            self._save_mat(waveform, filename, metadata=metadata)

        elif format == "HDF5":
            self._save_hdf5(waveform, filename, metadata=metadata)

        else:
            raise exceptions.InvalidParameterError(f"Invalid format: {format}. Supported: CSV, CSV_ENHANCED, NPY, MAT, HDF5")

    def _save_csv(
        self,
        waveform: WaveformData,
        filename: str,
        include_metadata: bool = False,
        metadata: Optional[dict] = None,
    ) -> None:
        """Save waveform as CSV file.

        Args:
            waveform: WaveformData object
            filename: Output filename
            include_metadata: Whether to include metadata header
            metadata: Optional additional metadata
        """
        import csv
        from datetime import datetime

        with open(filename, "w", newline="") as f:
            if include_metadata:
                # Write metadata header as comments
                f.write("# Siglent Oscilloscope Waveform Data\n")
                f.write(f"# Captured: {datetime.now().isoformat()}\n")
                f.write(f"# Channel: {waveform.channel}\n")
                f.write(f"# Sample Rate: {waveform.sample_rate} Sa/s\n")
                f.write(f"# Samples: {len(waveform.time)}\n")

                if metadata:
                    f.write("#\n# Additional Metadata:\n")
                    for key, value in metadata.items():
                        f.write(f"# {key}: {value}\n")

                f.write("#\n")

            # Write data
            writer = csv.writer(f)
            writer.writerow(["Time (s)", "Voltage (V)"])
            for t, v in zip(waveform.time, waveform.voltage):
                writer.writerow([t, v])

        logger.info(f"Waveform saved to {filename} (CSV format, metadata={'included' if include_metadata else 'excluded'})")

    def _save_npy(self, waveform: WaveformData, filename: str, metadata: Optional[dict] = None) -> None:
        """Save waveform as NumPy compressed archive.

        Args:
            waveform: WaveformData object
            filename: Output filename
            metadata: Optional additional metadata
        """
        from datetime import datetime

        # Build data dictionary
        data = {
            "time": waveform.time,
            "voltage": waveform.voltage,
            "channel": waveform.channel,
            "sample_rate": waveform.sample_rate,
            "timestamp": datetime.now().isoformat(),
        }

        # Add optional metadata
        if metadata:
            for key, value in metadata.items():
                # Convert to numpy-compatible types
                if isinstance(value, (str, int, float)):
                    data[f"meta_{key}"] = value

        np.savez(filename, **data)
        logger.info(f"Waveform saved to {filename} (NPY format)")

    def _save_mat(self, waveform: WaveformData, filename: str, metadata: Optional[dict] = None) -> None:
        """Save waveform as MATLAB format.

        Args:
            waveform: WaveformData object
            filename: Output filename
            metadata: Optional additional metadata

        Raises:
            ImportError: If scipy is not installed
        """
        try:
            from scipy.io import savemat
        except ImportError:
            raise ImportError("scipy is required for MAT file export. Install with: pip install scipy")

        from datetime import datetime

        # Build data dictionary for MATLAB
        data = {
            "time": waveform.time,
            "voltage": waveform.voltage,
            "channel": waveform.channel,
            "sample_rate": waveform.sample_rate,
            "timestamp": datetime.now().isoformat(),
        }

        # Add metadata
        if metadata:
            meta_dict = {}
            for key, value in metadata.items():
                # MATLAB doesn't like some characters in field names
                safe_key = key.replace(" ", "_").replace("-", "_")
                if isinstance(value, (int, float, str)):
                    meta_dict[safe_key] = value
            data["metadata"] = meta_dict

        savemat(filename, data)
        logger.info(f"Waveform saved to {filename} (MAT format)")

    def _save_hdf5(self, waveform: WaveformData, filename: str, metadata: Optional[dict] = None) -> None:
        """Save waveform as HDF5 format.

        Args:
            waveform: WaveformData object
            filename: Output filename
            metadata: Optional additional metadata

        Raises:
            ImportError: If h5py is not installed
        """
        try:
            import h5py
        except ImportError:
            raise ImportError("h5py is required for HDF5 file export. Install with: pip install h5py")

        from datetime import datetime

        with h5py.File(filename, "w") as f:
            # Create datasets
            f.create_dataset("time", data=waveform.time, compression="gzip")
            f.create_dataset("voltage", data=waveform.voltage, compression="gzip")

            # Store metadata as attributes
            f.attrs["channel"] = waveform.channel
            f.attrs["sample_rate"] = waveform.sample_rate
            f.attrs["num_samples"] = len(waveform.time)
            f.attrs["timestamp"] = datetime.now().isoformat()

            # Add optional metadata
            if metadata:
                meta_group = f.create_group("metadata")
                for key, value in metadata.items():
                    if isinstance(value, (int, float, str, bool)):
                        meta_group.attrs[key] = value
                    elif isinstance(value, (list, tuple)):
                        meta_group.attrs[key] = str(value)

        logger.info(f"Waveform saved to {filename} (HDF5 format)")

    def __repr__(self) -> str:
        """String representation."""
        return "Waveform()"
