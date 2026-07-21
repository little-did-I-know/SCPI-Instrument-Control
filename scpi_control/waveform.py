"""Waveform acquisition and data processing for Siglent oscilloscopes."""

import logging
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple, Union

import numpy as np

from scpi_control import exceptions
from scpi_control import waveform_schema as ws
from scpi_control.models import validate_channel
from scpi_control.provenance import AcquisitionProvenance
from scpi_control.scpi_commands import BARE_NR3_DIALECTS

if TYPE_CHECKING:
    from scpi_control.oscilloscope import Oscilloscope

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
        provenance: Instrument settings snapshot at acquisition time (optional)
    """

    time: np.ndarray
    voltage: np.ndarray
    channel: Union[int, str]
    sample_rate: Optional[float] = None
    record_length: Optional[int] = None
    timebase: Optional[float] = None
    voltage_scale: Optional[float] = None
    voltage_offset: float = 0.0
    provenance: Optional[AcquisitionProvenance] = None

    def __len__(self) -> int:
        """Get number of samples."""
        return len(self.voltage)

    def __post_init__(self) -> None:
        """Validate the arrays and derive what they determine.

        Only values the samples actually determine are derived here: record_length
        is the array's length, and sample_rate is 1/dt off the time axis. Timebase
        and voltage_scale are NOT derived -- they depend on the scope's display
        grid, which the samples do not carry. A real acquisition supplies both.
        """
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

    @property
    def _dialect(self) -> str:
        """Wire dialect of the parent scope; defaults to legacy before connect."""
        return getattr(self._scope, "dialect", None) or "legacy"

    def acquire(self, channel: int, format: str = "BYTE", provenance: bool = True) -> WaveformData:
        """Acquire waveform data from a channel.

        Args:
            channel: Channel number (1-4)
            format: Data format - 'BYTE' or 'WORD' (default: 'BYTE')
            provenance: Snapshot instrument settings alongside the data
                (default True; pass False on high-rate paths)

        Returns:
            WaveformData object with time and voltage arrays

        Raises:
            InvalidParameterError: If channel number is invalid
            CommandError: If acquisition fails
        """
        validate_channel(self._scope, channel)

        logger.info(f"Acquiring waveform from channel {channel}")

        from scpi_control.waveform_transfer import make_transfer

        data = make_transfer(self._scope).acquire(channel, format)
        if provenance:
            try:
                data.provenance = AcquisitionProvenance.from_scope(self._scope, channels=[channel])
            except Exception:
                logger.warning("Provenance snapshot failed; waveform returned without provenance", exc_info=True)
        return data

    def _get_voltage_scale(self, channel: str) -> float:
        """Get voltage scale for channel.

        Args:
            channel: Channel name (e.g., 'C1')

        Returns:
            Voltage scale in V/div
        """
        command = self._scope._get_command("get_voltage_div", ch=int(channel[1]))
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
        command = self._scope._get_command("get_voltage_offset", ch=int(channel[1]))
        response = self._scope.query(command)
        logger.debug(f"Voltage offset response: '{response}'")

        return self._parse_value_with_units(response, ("V",), "voltage offset", command=command)

    def _get_timebase(self) -> float:
        """Get timebase setting.

        Returns:
            Timebase in seconds/division
        """
        command = self._scope._get_command("get_time_div")
        response = self._scope.query(command)
        logger.debug(f"Timebase response: '{response}'")

        return self._parse_value_with_units(response, ("S",), "timebase", command=command)

    def _get_sample_rate(self) -> float:
        """Get sample rate.

        Returns:
            Sample rate in samples/second
        """
        command = self._scope._get_command("get_sample_rate")
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

        Compatibility wrapper around waveform_transfer.parse_ieee_block, kept
        for callers (internal and external) that still use the format-string
        + command-string signature.

        Args:
            raw_data: Raw binary data from oscilloscope
            format: Data format - 'BYTE' or 'WORD'
            command: Command that produced raw_data (used for error context)

        Returns:
            Numpy array of raw data codes
        """
        from scpi_control.waveform_transfer import parse_ieee_block

        if format == "BYTE":
            dtype = np.int8
        elif format == "WORD":
            dtype = np.int16
        else:
            raise exceptions.InvalidParameterError(f"Invalid format: {format}")

        context = f"host {self._scope.host}:{self._scope.port}" + (f", command '{command}'" if command else "")
        return parse_ieee_block(raw_data, dtype, error_context=context)

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

        # Bare-NR3 dialects return a numeric value with no unit suffix at
        # all: modern Siglent (:CHANnel:SCALe?, :CHANnel:OFFSet?,
        # :TIMebase:SCALe?, :ACQuire:SRATe? -- guide pp.46,56,58,476),
        # Tektronix (HEADer OFF strips the echo, leaving a bare NR3), and
        # LeCroy (CHDR OFF). Legacy Siglent always echoes a unit and keeps
        # the strict check above (audit-pinned, see
        # test_value_parsing_requires_units).
        if self._dialect in BARE_NR3_DIALECTS:
            try:
                value = float(cleaned)
                logger.debug(f"Parsed {quantity}: {value} (bare NR3, {self._dialect} dialect)")
                return value
            except ValueError:
                pass

        expected = " or ".join(expected_units)
        raise exceptions.CommandError(self._format_scope_error(f"Invalid {quantity} response: '{response}' (expected units: {expected})", command))

    def get_waveform_preamble(self, channel: int) -> dict:
        """Get waveform preamble information.

        Args:
            channel: Channel number (1-4)

        Returns:
            Dictionary with waveform metadata
        """
        validate_channel(self._scope, channel)

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
                f.write(f"{ws.CSV_COMMENT} SCPI Instrument Control Waveform Data\n")
                f.write(f"{ws.CSV_COMMENT} Captured: {datetime.now().isoformat()}\n")
                f.write(f"{ws.CSV_COMMENT} {ws.CSV_HEADER_CHANNEL}: {waveform.channel}\n")
                f.write(f"{ws.CSV_COMMENT} {ws.CSV_HEADER_SAMPLE_RATE}: {waveform.sample_rate} Sa/s\n")
                f.write(f"{ws.CSV_COMMENT} Samples: {len(waveform.time)}\n")

                if metadata:
                    f.write(f"{ws.CSV_COMMENT}\n{ws.CSV_COMMENT} Additional Metadata:\n")
                    for key, value in metadata.items():
                        f.write(f"{ws.CSV_COMMENT} {key}: {value}\n")

                f.write(f"{ws.CSV_COMMENT}\n")

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
            ws.TIME: waveform.time,
            ws.VOLTAGE: waveform.voltage,
            ws.CHANNEL: waveform.channel,
            ws.SAMPLE_RATE: waveform.sample_rate,
            ws.TIMESTAMP: datetime.now().isoformat(),
        }

        # Add optional metadata
        if metadata:
            for key, value in metadata.items():
                # Convert to numpy-compatible types
                if isinstance(value, (str, int, float)):
                    data[f"{ws.NPZ_META_PREFIX}{key}"] = value

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
            ws.TIME: waveform.time,
            ws.VOLTAGE: waveform.voltage,
            ws.CHANNEL: waveform.channel,
            ws.SAMPLE_RATE: waveform.sample_rate,
            ws.TIMESTAMP: datetime.now().isoformat(),
        }

        # Add metadata
        if metadata:
            meta_dict = {}
            for key, value in metadata.items():
                # MATLAB doesn't like some characters in field names
                safe_key = key.replace(" ", "_").replace("-", "_")
                if isinstance(value, (int, float, str)):
                    meta_dict[safe_key] = value
            data[ws.MAT_META_KEY] = meta_dict

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
            f.create_dataset(ws.TIME, data=waveform.time, compression="gzip")
            f.create_dataset(ws.VOLTAGE, data=waveform.voltage, compression="gzip")

            # Store metadata as attributes
            f.attrs[ws.CHANNEL] = waveform.channel
            f.attrs[ws.SAMPLE_RATE] = waveform.sample_rate
            f.attrs[ws.HDF5_NUM_SAMPLES] = len(waveform.time)
            f.attrs[ws.TIMESTAMP] = datetime.now().isoformat()

            # Add optional metadata
            if metadata:
                meta_group = f.create_group(ws.HDF5_META_GROUP)
                for key, value in metadata.items():
                    if isinstance(value, (int, float, str, bool)):
                        meta_group.attrs[key] = value
                    elif isinstance(value, (list, tuple)):
                        meta_group.attrs[key] = str(value)

        logger.info(f"Waveform saved to {filename} (HDF5 format)")

    def __repr__(self) -> str:
        """String representation."""
        return "Waveform()"
