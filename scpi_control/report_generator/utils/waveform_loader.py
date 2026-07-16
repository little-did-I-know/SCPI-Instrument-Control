"""
Waveform file loader supporting multiple formats.

Supports loading waveform data from NPZ, CSV, MAT, and HDF5 files
created by the Siglent oscilloscope library.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from scpi_control import waveform_schema as ws
from scpi_control.report_generator.models.report_data import WaveformData


def _looks_like_ours(keys: Iterable[str]) -> bool:
    """True when a file carries this library's core schema fields."""
    keys = set(keys)
    return ws.TIME in keys and ws.VOLTAGE in keys and ws.CHANNEL in keys


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
        """Load an NPZ, reading this library's schema exactly when present."""
        data = np.load(filepath, allow_pickle=True)

        if _looks_like_ours(data.files):
            return [WaveformLoader._npz_from_schema(data, filepath)]
        return WaveformLoader._npz_heuristic(data, filepath)

    @staticmethod
    def _npz_from_schema(data, filepath: Path) -> WaveformData:
        """Read an NPZ written by scpi_control.waveform's _save_npy."""
        metadata = {k[len(ws.NPZ_META_PREFIX) :]: data[k] for k in data.files if k.startswith(ws.NPZ_META_PREFIX)}
        voltage = np.asarray(data[ws.VOLTAGE])
        return WaveformData(
            channel_name=str(data[ws.CHANNEL]),
            time_data=np.asarray(data[ws.TIME]),
            voltage_data=voltage,
            sample_rate=float(data[ws.SAMPLE_RATE]),
            record_length=len(voltage),
            source_file=filepath,
        )

    @staticmethod
    def _npz_heuristic(data, filepath: Path) -> List[WaveformData]:
        """Best-effort read of a third-party NPZ. Values here are inferred."""
        time_key = WaveformLoader._pick_time_key(data.files)
        voltage_keys = [k for k in data.files if k != time_key and np.asarray(data[k]).ndim == 1 and np.issubdtype(np.asarray(data[k]).dtype, np.number)]
        if time_key is None or not voltage_keys:
            raise ValueError(f"Could not identify time and voltage data in {filepath}")

        time_data = np.asarray(data[time_key])
        waveforms = []
        for voltage_key in voltage_keys:
            voltage = np.asarray(data[voltage_key])
            waveforms.append(
                WaveformData(
                    channel_name=voltage_key,
                    time_data=time_data,
                    voltage_data=voltage,
                    sample_rate=WaveformLoader._rate_from_time(time_data),
                    record_length=len(voltage),
                    source_file=filepath,
                )
            )
        return waveforms

    @staticmethod
    def _pick_time_key(keys: Iterable[str]) -> Optional[str]:
        """Choose a time key without letting 'timestamp' shadow 'time'.

        An exact match always wins; only then do we fall back to a substring
        guess, and never onto a timestamp-ish key. If nothing looks
        time-related at all, fall back to the first non-timestamp-ish key
        (best-effort, for files with no recognizable time key whatsoever) --
        but a "stamp"-suffixed key is never eligible, even as a last resort.
        """
        keys = list(keys)
        if ws.TIME in keys:
            return ws.TIME
        for key in keys:
            lowered = key.lower()
            if "time" in lowered and "stamp" not in lowered:
                return key
        for key in keys:
            if "stamp" not in key.lower():
                return key
        return None

    @staticmethod
    def _rate_from_time(time_data: np.ndarray) -> float:
        """Derive the sample rate from a time axis; 0.0 when it cannot be known."""
        time_data = np.asarray(time_data)
        if time_data.ndim != 1 or len(time_data) < 2:
            return 0.0
        dt = float(time_data[1] - time_data[0])
        return 1.0 / dt if dt > 0 else 0.0

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
        """Load a MAT file, reading this library's schema exactly when present."""
        try:
            from scipy.io import loadmat
        except ImportError:
            raise ImportError("scipy is required to load MAT files. Install with: pip install scipy")

        data = loadmat(filepath)
        keys = [k for k in data.keys() if not k.startswith("__")]

        if _looks_like_ours(keys):
            voltage = np.asarray(data[ws.VOLTAGE]).flatten()
            # loadmat returns even scalars as 2-D arrays; .item() unwraps them.
            return [
                WaveformData(
                    channel_name=str(np.asarray(data[ws.CHANNEL]).item()),
                    time_data=np.asarray(data[ws.TIME]).flatten(),
                    voltage_data=voltage,
                    sample_rate=float(np.asarray(data[ws.SAMPLE_RATE]).item()),
                    record_length=len(voltage),
                    source_file=filepath,
                )
            ]

        time_key = WaveformLoader._pick_time_key(keys)
        voltage_keys = [k for k in keys if k != time_key and np.issubdtype(np.asarray(data[k]).dtype, np.number)]
        if time_key is None or not voltage_keys:
            raise ValueError(f"Could not identify time and voltage data in {filepath}")

        time_data = np.asarray(data[time_key]).flatten()
        waveforms = []
        for voltage_key in voltage_keys:
            voltage = np.asarray(data[voltage_key]).flatten()
            waveforms.append(
                WaveformData(
                    channel_name=voltage_key,
                    time_data=time_data,
                    voltage_data=voltage,
                    sample_rate=WaveformLoader._rate_from_time(time_data),
                    record_length=len(voltage),
                    source_file=filepath,
                )
            )
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
