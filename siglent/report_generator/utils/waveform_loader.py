"""
Waveform file loader supporting multiple formats.

Supports loading waveform data from NPZ, CSV, MAT, and HDF5 files
created by the Siglent oscilloscope library.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from siglent.report_generator.models.report_data import WaveformData


class WaveformLoader:
    """Loader for various waveform file formats."""

    @staticmethod
    def load(filepath: Path) -> List[WaveformData]:
        """
        Load waveform data from a file.

        Automatically detects file format based on extension and
        loads the appropriate data.

        Args:
            filepath: Path to the waveform file

        Returns:
            List of WaveformData objects (may contain multiple channels)

        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file does not exist
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Waveform file not found: {filepath}")

        suffix = filepath.suffix.lower()

        if suffix == ".npz":
            return WaveformLoader._load_npz(filepath)
        elif suffix == ".csv":
            return WaveformLoader._load_csv(filepath)
        elif suffix == ".mat":
            return WaveformLoader._load_mat(filepath)
        elif suffix in [".h5", ".hdf5"]:
            return WaveformLoader._load_hdf5(filepath)
        else:
            raise ValueError(f"Unsupported file format: {suffix}. " "Supported formats: .npz, .csv, .mat, .h5, .hdf5")

    @staticmethod
    def _load_npz(filepath: Path) -> List[WaveformData]:
        """Load waveform data from NPZ file."""
        data = np.load(filepath, allow_pickle=True)
        waveforms = []

        # NPZ files can contain multiple channels
        # Expected structure: time, voltage, metadata for each channel

        # Try to find time and voltage arrays
        time_key = None
        voltage_keys = []

        for key in data.files:
            if "time" in key.lower():
                time_key = key
            elif "voltage" in key.lower() or key.startswith("C"):
                voltage_keys.append(key)

        if time_key is None:
            # Try using first array as time
            time_key = data.files[0] if data.files else None

        if not voltage_keys:
            # Use all arrays except time as voltage data
            voltage_keys = [k for k in data.files if k != time_key]

        if time_key is None or not voltage_keys:
            raise ValueError("Could not identify time and voltage data in NPZ file")

        time_data = data[time_key]

        # Load metadata if available
        metadata = data.get("metadata", {})
        if isinstance(metadata, np.ndarray):
            metadata = metadata.item() if metadata.size == 1 else {}

        for voltage_key in voltage_keys:
            voltage_data = data[voltage_key]

            # Determine channel name from key
            channel_name = voltage_key

            # Extract metadata for this channel
            sample_rate = metadata.get("sample_rate", 1e9)
            if isinstance(sample_rate, np.ndarray):
                sample_rate = float(sample_rate)

            waveform = WaveformData(
                channel_name=channel_name,
                time_data=time_data,
                voltage_data=voltage_data,
                sample_rate=sample_rate,
                record_length=len(voltage_data),
                timebase=metadata.get("timebase"),
                voltage_scale=metadata.get(f"{channel_name}_vscale"),
                voltage_offset=metadata.get(f"{channel_name}_voffset"),
                probe_ratio=metadata.get(f"{channel_name}_probe"),
                coupling=metadata.get(f"{channel_name}_coupling"),
                source_file=filepath,
            )

            waveforms.append(waveform)

        return waveforms

    @staticmethod
    def _load_csv(filepath: Path) -> List[WaveformData]:
        """Load waveform data from CSV file."""
        # CSV format: typically first column is time, subsequent columns are channels
        try:
            data = np.loadtxt(filepath, delimiter=",", skiprows=1)
        except Exception:
            # Try without header
            data = np.loadtxt(filepath, delimiter=",")

        if data.ndim == 1:
            # Single column - treat as voltage data, generate time
            voltage_data = data
            sample_rate = 1e9  # Default 1 GS/s
            time_data = np.arange(len(voltage_data)) / sample_rate

            waveform = WaveformData(
                channel_name="CH1",
                time_data=time_data,
                voltage_data=voltage_data,
                sample_rate=sample_rate,
                record_length=len(voltage_data),
                source_file=filepath,
            )
            return [waveform]

        # Multiple columns
        time_data = data[:, 0]
        waveforms = []

        for i in range(1, data.shape[1]):
            voltage_data = data[:, i]

            # Calculate sample rate from time data
            if len(time_data) > 1:
                dt = time_data[1] - time_data[0]
                sample_rate = 1.0 / dt if dt > 0 else 1e9
            else:
                sample_rate = 1e9

            waveform = WaveformData(
                channel_name=f"CH{i}",
                time_data=time_data,
                voltage_data=voltage_data,
                sample_rate=sample_rate,
                record_length=len(voltage_data),
                source_file=filepath,
            )
            waveforms.append(waveform)

        return waveforms

    @staticmethod
    def _load_mat(filepath: Path) -> List[WaveformData]:
        """Load waveform data from MATLAB file."""
        try:
            from scipy.io import loadmat
        except ImportError:
            raise ImportError("scipy is required to load MAT files. " "Install with: pip install scipy")

        data = loadmat(filepath)
        waveforms = []

        # Find time and voltage arrays (skip MATLAB metadata keys starting with __)
        time_key = None
        voltage_keys = []

        for key in data.keys():
            if key.startswith("__"):
                continue
            if "time" in key.lower():
                time_key = key
            elif "voltage" in key.lower() or key.startswith("C") or key.startswith("ch"):
                voltage_keys.append(key)

        if time_key is None:
            # Use first non-metadata key as time
            non_meta_keys = [k for k in data.keys() if not k.startswith("__")]
            time_key = non_meta_keys[0] if non_meta_keys else None

        if not voltage_keys:
            # Use all non-time, non-metadata keys as voltage
            voltage_keys = [k for k in data.keys() if not k.startswith("__") and k != time_key]

        if time_key is None or not voltage_keys:
            raise ValueError("Could not identify time and voltage data in MAT file")

        time_data = data[time_key].flatten()

        for voltage_key in voltage_keys:
            voltage_data = data[voltage_key].flatten()

            # Calculate sample rate
            if len(time_data) > 1:
                dt = time_data[1] - time_data[0]
                sample_rate = 1.0 / dt if dt > 0 else 1e9
            else:
                sample_rate = 1e9

            waveform = WaveformData(
                channel_name=voltage_key,
                time_data=time_data,
                voltage_data=voltage_data,
                sample_rate=sample_rate,
                record_length=len(voltage_data),
                source_file=filepath,
            )
            waveforms.append(waveform)

        return waveforms

    @staticmethod
    def _load_hdf5(filepath: Path) -> List[WaveformData]:
        """Load waveform data from HDF5 file."""
        try:
            import h5py
        except ImportError:
            raise ImportError("h5py is required to load HDF5 files. " "Install with: pip install h5py")

        waveforms = []

        with h5py.File(filepath, "r") as f:
            # Try to find time and voltage datasets
            time_data = None
            time_key = None

            # Look for time data
            for key in f.keys():
                if "time" in key.lower():
                    time_data = f[key][:]
                    time_key = key
                    break

            # If no time data found, look for any dataset
            if time_data is None and len(f.keys()) > 0:
                time_key = list(f.keys())[0]
                time_data = f[time_key][:]

            if time_data is None:
                raise ValueError("Could not find time data in HDF5 file")

            # Load voltage data from all other datasets
            for key in f.keys():
                if key == time_key:
                    continue

                dataset = f[key]
                voltage_data = dataset[:]

                # Try to read metadata from attributes
                attrs = dict(dataset.attrs)

                sample_rate = attrs.get("sample_rate", 1e9)
                if isinstance(sample_rate, np.ndarray):
                    sample_rate = float(sample_rate)

                waveform = WaveformData(
                    channel_name=key,
                    time_data=time_data,
                    voltage_data=voltage_data,
                    sample_rate=sample_rate,
                    record_length=len(voltage_data),
                    timebase=attrs.get("timebase"),
                    voltage_scale=attrs.get("voltage_scale"),
                    voltage_offset=attrs.get("voltage_offset"),
                    probe_ratio=attrs.get("probe_ratio"),
                    coupling=attrs.get("coupling"),
                    source_file=filepath,
                )
                waveforms.append(waveform)

        return waveforms

    @staticmethod
    def load_multiple(filepaths: List[Path]) -> List[WaveformData]:
        """
        Load waveforms from multiple files.

        Args:
            filepaths: List of file paths to load

        Returns:
            Combined list of all waveform data
        """
        all_waveforms = []

        for filepath in filepaths:
            try:
                waveforms = WaveformLoader.load(filepath)
                all_waveforms.extend(waveforms)
            except Exception as e:
                print(f"Warning: Failed to load {filepath}: {e}")
                continue

        return all_waveforms
