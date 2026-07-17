"""
Waveform file loader supporting multiple formats.

Supports loading waveform data from NPZ, CSV, MAT, and HDF5 files
created by scpi_control.
"""

import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np

from scpi_control import waveform_schema as ws
from scpi_control.report_generator.models.report_data import WaveformData

logger = logging.getLogger(__name__)


def _looks_like_ours(keys: Iterable[str]) -> bool:
    """True when a file carries all fields the schema readers unconditionally
    read: TIME, VOLTAGE, CHANNEL, and SAMPLE_RATE. Anything missing one of
    these must fall back to the heuristic reader instead of hitting a raw
    KeyError in the schema path."""
    keys = set(keys)
    return ws.TIME in keys and ws.VOLTAGE in keys and ws.CHANNEL in keys and ws.SAMPLE_RATE in keys


def _require_numeric_time(time_data: np.ndarray, filepath: Path) -> np.ndarray:
    """Reject a non-numeric time axis with the loader's own error.

    `_pick_time_key`'s last-resort branch can select a string key on a foreign
    file, and a foreign file can also name a dataset 'time' outright. Without
    this, `_rate_from_time` raises an opaque numpy TypeError instead of the
    ValueError callers expect. Shared by every path that derives a rate from a
    time axis it did not write (NPZ, MAT, HDF5) so the guard lives in one place.
    """
    time_data = np.asarray(time_data)
    if not np.issubdtype(time_data.dtype, np.number):
        raise ValueError(f"Time data in {filepath} is not numeric (found dtype {time_data.dtype})")
    return time_data


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
        voltage = np.asarray(data[ws.VOLTAGE])
        return WaveformData(
            channel=str(data[ws.CHANNEL]),
            time=np.asarray(data[ws.TIME]),
            voltage=voltage,
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

        time_data = _require_numeric_time(data[time_key], filepath)

        waveforms = []
        for voltage_key in voltage_keys:
            voltage = np.asarray(data[voltage_key])
            waveforms.append(
                WaveformData(
                    channel=voltage_key,
                    time=time_data,
                    voltage=voltage,
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
        """Load a CSV, honouring the CSV_ENHANCED '#' metadata header if present."""
        header = WaveformLoader._read_csv_header(filepath)

        # Skip the '#' block and the column-name row. Generic on purpose: files
        # written before the rename carry a different first line, and they must
        # still load. `comments=` alone is not enough -- the "Time (s),Voltage (V)"
        # row is not a comment and loadtxt chokes on it.
        skip = WaveformLoader._count_leading_non_numeric(filepath)
        data = np.loadtxt(filepath, delimiter=",", comments=ws.CSV_COMMENT, skiprows=skip, ndmin=2)
        if data.size == 0:
            raise ValueError(f"No numeric data found in {filepath}")
        if data.shape[1] < 2:
            raise ValueError(f"Expected a time column and at least one voltage column in {filepath}, found {data.shape[1]}")

        time_data = data[:, 0]
        derived_rate = WaveformLoader._rate_from_time(time_data)
        waveforms = []
        for i in range(1, data.shape[1]):
            voltage = data[:, i]
            # A single-channel enhanced CSV names its channel; multi-column CSVs
            # and plain CSVs cannot, so synthesize CHn.
            if data.shape[1] == 2 and header.get(ws.CSV_HEADER_CHANNEL):
                channel_name = header[ws.CSV_HEADER_CHANNEL]
            else:
                channel_name = f"CH{i}"
            waveforms.append(
                WaveformData(
                    channel=channel_name,
                    time=time_data,
                    voltage=voltage,
                    sample_rate=WaveformLoader._rate_from_header(header, derived_rate),
                    record_length=len(voltage),
                    source_file=filepath,
                )
            )
        return waveforms

    @staticmethod
    def _read_csv_header(filepath: Path) -> Dict[str, str]:
        """Parse a CSV_ENHANCED '# <label>: <value>' block. Empty for plain CSV."""
        header: Dict[str, str] = {}
        with open(filepath, "r") as f:
            for line in f:
                if not line.startswith(ws.CSV_COMMENT):
                    break
                body = line[len(ws.CSV_COMMENT) :].strip()
                if ":" in body:
                    label, _, value = body.partition(":")
                    label = label.strip()
                    # First write wins: the genuine header always precedes the
                    # "Additional Metadata" block, so a user metadata key that
                    # happens to be named e.g. "Channel" must not overwrite it.
                    if label not in header:
                        header[label] = value.strip()
        return header

    @staticmethod
    def _rate_from_header(header: Dict[str, str], fallback: float) -> float:
        """Use the header's stated sample rate when present; else the derived one."""
        raw = header.get(ws.CSV_HEADER_SAMPLE_RATE)
        if not raw:
            return fallback
        # Stored as e.g. "1000000.0 Sa/s"
        try:
            return float(raw.split()[0])
        except (ValueError, IndexError):
            return fallback

    @staticmethod
    def _count_leading_non_numeric(filepath: Path) -> int:
        """Rows to skip: the '#' block plus a column-name row, if any."""
        skip = 0
        with open(filepath, "r") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    skip += 1
                    continue
                if stripped.startswith(ws.CSV_COMMENT):
                    skip += 1
                    continue
                first = stripped.split(",")[0]
                try:
                    float(first)
                except ValueError:
                    skip += 1  # a column-name row like "Time (s),Voltage (V)"
                    continue
                break
        return skip

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
                    channel=str(np.asarray(data[ws.CHANNEL]).item()),
                    time=np.asarray(data[ws.TIME]).flatten(),
                    voltage=voltage,
                    sample_rate=float(np.asarray(data[ws.SAMPLE_RATE]).item()),
                    record_length=len(voltage),
                    source_file=filepath,
                )
            ]

        time_key = WaveformLoader._pick_time_key(keys)
        voltage_keys = [k for k in keys if k != time_key and np.issubdtype(np.asarray(data[k]).dtype, np.number) and np.asarray(data[k]).size > 1]
        if time_key is None or not voltage_keys:
            raise ValueError(f"Could not identify time and voltage data in {filepath}")

        time_data = _require_numeric_time(np.asarray(data[time_key]).flatten(), filepath)
        waveforms = []
        for voltage_key in voltage_keys:
            voltage = np.asarray(data[voltage_key]).flatten()
            waveforms.append(
                WaveformData(
                    channel=voltage_key,
                    time=time_data,
                    voltage=voltage,
                    sample_rate=WaveformLoader._rate_from_time(time_data),
                    record_length=len(voltage),
                    source_file=filepath,
                )
            )
        return waveforms

    @staticmethod
    def _load_hdf5(filepath: Path) -> List[WaveformData]:
        """Load an HDF5 file, reading this library's schema exactly when present."""
        try:
            import h5py
        except ImportError:
            raise ImportError("h5py is required to load HDF5 files. Install with: pip install h5py")

        with h5py.File(filepath, "r") as f:
            # Datasets only -- the writer also creates a 'metadata' GROUP, and
            # slicing a group raises TypeError.
            datasets = [k for k in f.keys() if isinstance(f[k], h5py.Dataset)]

            if ws.TIME in datasets and ws.VOLTAGE in datasets:
                # Core fields live on the FILE's attrs, not the dataset's.
                attrs = dict(f.attrs)
                voltage = f[ws.VOLTAGE][:]
                # Foreign files can name a dataset 'time' and fill it with strings;
                # the sample_rate default below feeds it to `_rate_from_time`.
                time_data = _require_numeric_time(f[ws.TIME][:], filepath)
                channel = attrs.get(ws.CHANNEL, ws.VOLTAGE)
                if isinstance(channel, bytes):
                    channel = channel.decode()
                return [
                    WaveformData(
                        channel=str(channel),
                        time=time_data,
                        voltage=voltage,
                        # Foreign files can name datasets 'time'/'voltage' without
                        # carrying our sample_rate attr; derive it from the
                        # numeric time axis instead of silently reporting 0.0,
                        # matching the heuristic path below.
                        sample_rate=float(attrs.get(ws.SAMPLE_RATE, WaveformLoader._rate_from_time(time_data))),
                        record_length=len(voltage),
                        source_file=filepath,
                    )
                ]

            time_key = WaveformLoader._pick_time_key(datasets)
            if time_key is None:
                raise ValueError(f"Could not find time data in {filepath}")
            time_data = _require_numeric_time(f[time_key][:], filepath)

            waveforms = []
            for key in datasets:
                if key == time_key:
                    continue
                voltage = f[key][:]
                attrs = dict(f[key].attrs)
                waveforms.append(
                    WaveformData(
                        channel=key,
                        time=time_data,
                        voltage=voltage,
                        sample_rate=float(attrs.get(ws.SAMPLE_RATE, WaveformLoader._rate_from_time(time_data))),
                        record_length=len(voltage),
                        source_file=filepath,
                    )
                )
            return waveforms

    @staticmethod
    def load_multiple(filepaths: List[Path], *, strict: bool = True) -> List[WaveformData]:
        """Load waveforms from several files.

        Args:
            filepaths: Files to load
            strict: Raise on the first failure (default). When False, skip the
                failed file and log a warning -- the historical behaviour, which
                silently turned a broken file into an empty report.

        Returns:
            Combined list of all waveform data

        Raises:
            Exception: The underlying load error, when strict is True
        """
        all_waveforms = []

        for filepath in filepaths:
            try:
                all_waveforms.extend(WaveformLoader.load(filepath))
            except Exception as e:
                if strict:
                    raise
                logger.warning(f"Failed to load {filepath}: {e}")

        return all_waveforms
