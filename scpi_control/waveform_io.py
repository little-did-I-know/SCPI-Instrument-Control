"""Read saved waveform files back into numpy arrays + normalized metadata.

The public entry point for users who want their raw data out of the library's
five on-disk formats (NPZ, plain CSV, enhanced CSV, MAT, HDF5) for their own
analysis. Reads files written before provenance existed (provenance is then
None) and normalizes the three binary formats' differing metadata
conventions (see scpi_control.waveform_schema) into one flat dict.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

import numpy as np

from scpi_control import waveform_schema as ws
from scpi_control.provenance import AcquisitionProvenance

logger = logging.getLogger(__name__)

_EXTENSION_FORMATS = {".npz": "NPZ", ".npy": "NPZ", ".csv": "CSV", ".mat": "MAT", ".h5": "HDF5", ".hdf5": "HDF5"}


@dataclass
class LoadedWaveform:
    """One waveform read back from disk, format differences normalized away."""

    time: np.ndarray
    voltage: np.ndarray
    channel: Optional[Union[int, str]]
    sample_rate: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Optional[AcquisitionProvenance] = None
    source_format: str = "NPZ"
    source_path: Optional[Path] = None

    def to_dataframe(self):
        """Return a pandas DataFrame (columns: time, voltage; metadata in .attrs)."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for to_dataframe(). Install with: pip install pandas")
        df = pd.DataFrame({"time": self.time, "voltage": self.voltage})
        df.attrs["channel"] = self.channel
        df.attrs["sample_rate"] = self.sample_rate
        df.attrs["metadata"] = dict(self.metadata)
        if self.provenance is not None:
            df.attrs["provenance"] = self.provenance.to_dict()
        return df


def load_waveform(path: Union[str, Path], format: Optional[str] = None) -> LoadedWaveform:
    """Load a waveform file saved by scpi_control (any version, any format).

    Args:
        path: File to read.
        format: Force a format ("NPZ", "CSV", "MAT", "HDF5"); None auto-detects
            from the extension.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If the format is unknown or the file cannot be parsed.
        ImportError: If the format needs an uninstalled optional dependency.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Waveform file not found: {path}")
    if format is None:
        format = _EXTENSION_FORMATS.get(path.suffix.lower())
        if format is None:
            raise ValueError(f"Cannot detect format from extension {path.suffix!r}. Pass format= explicitly (NPZ, CSV, MAT, HDF5).")
    format = format.upper()
    if format in ("NPY", "NPZ"):
        return _load_npz(path)
    if format in ("CSV", "CSV_ENHANCED"):
        return _load_csv(path)
    if format == "MAT":
        return _load_mat(path)
    if format == "HDF5":
        return _load_hdf5(path)
    raise ValueError(f"Unknown format: {format}. Supported: NPZ, CSV, MAT, HDF5")


def _parse_provenance(text: Optional[str]) -> Optional[AcquisitionProvenance]:
    if not text:
        return None
    try:
        return AcquisitionProvenance.from_json(str(text))
    except Exception:
        logger.warning("Corrupt provenance block ignored", exc_info=True)
        return None


def _scalar(value: Any) -> Any:
    """Collapse the 0-d / 1x1 array wrappers numpy and scipy.io put around scalars."""
    arr = np.asarray(value)
    if arr.size == 1:
        item = arr.reshape(-1)[0]
        if isinstance(item, np.generic):
            item = item.item()
        if isinstance(item, bytes):
            item = item.decode()
        return item
    return arr


def _channel_value(raw: Any) -> Optional[Union[int, str]]:
    value = _scalar(raw)
    if value is None:
        return None
    text = str(value)
    return int(text) if text.isdigit() else text


def _load_npz(path: Path) -> LoadedWaveform:
    data = np.load(path, allow_pickle=False)
    if ws.TIME not in data.files or ws.VOLTAGE not in data.files:
        raise ValueError(f"{path} does not contain '{ws.TIME}'/'{ws.VOLTAGE}' arrays; not a scpi_control waveform file")
    metadata: Dict[str, Any] = {}
    for key in data.files:
        if key.startswith(ws.NPZ_META_PREFIX):
            metadata[key[len(ws.NPZ_META_PREFIX) :]] = _scalar(data[key])
    for key in (ws.TIMESTAMP,) + ws.SCALE_FIELDS:
        if key in data.files:
            metadata[key] = _scalar(data[key])
    sample_rate = _scalar(data[ws.SAMPLE_RATE]) if ws.SAMPLE_RATE in data.files else None
    return LoadedWaveform(
        time=np.asarray(data[ws.TIME]),
        voltage=np.asarray(data[ws.VOLTAGE]),
        channel=_channel_value(data[ws.CHANNEL]) if ws.CHANNEL in data.files else None,
        sample_rate=float(sample_rate) if sample_rate is not None else None,
        metadata=metadata,
        provenance=_parse_provenance(_scalar(data[ws.PROVENANCE_JSON]) if ws.PROVENANCE_JSON in data.files else None),
        source_format="NPZ",
        source_path=path,
    )


def _load_csv(path: Path) -> LoadedWaveform:
    header: Dict[str, str] = {}
    times, volts = [], []
    with open(path, "r", newline="") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith(ws.CSV_COMMENT):
                text = line[len(ws.CSV_COMMENT) :].strip()
                key, sep, value = text.partition(":")
                if sep:
                    header[key.strip()] = value.strip()
                continue
            first = line.split(",", 1)[0]
            try:
                t = float(first)
            except ValueError:
                continue  # the "Time (s),Voltage (V)" column-header row
            _, _, rest = line.partition(",")
            times.append(t)
            volts.append(float(rest.split(",", 1)[0]))
    if not times:
        raise ValueError(f"No numeric data rows found in {path}")

    def _header_float(name: str) -> Optional[float]:
        raw = header.get(name)
        if raw is None:
            return None
        try:
            return float(raw.split()[0])
        except (ValueError, IndexError):
            return None

    metadata = {k: v for k, v in header.items() if k not in (ws.CSV_HEADER_PROVENANCE,)}
    for name, key in ((ws.CSV_HEADER_TIMEBASE, ws.TIMEBASE), (ws.CSV_HEADER_VOLTAGE_SCALE, ws.VOLTAGE_SCALE), (ws.CSV_HEADER_VOLTAGE_OFFSET, ws.VOLTAGE_OFFSET)):
        value = _header_float(name)
        if value is not None:
            metadata[key] = value
    channel_raw = header.get(ws.CSV_HEADER_CHANNEL)
    return LoadedWaveform(
        time=np.asarray(times),
        voltage=np.asarray(volts),
        channel=_channel_value(channel_raw) if channel_raw is not None else None,
        sample_rate=_header_float(ws.CSV_HEADER_SAMPLE_RATE),
        metadata=metadata,
        provenance=_parse_provenance(header.get(ws.CSV_HEADER_PROVENANCE)),
        source_format="CSV",
        source_path=path,
    )


def _load_mat(path: Path) -> LoadedWaveform:
    try:
        from scipy.io import loadmat
    except ImportError:
        raise ImportError("scipy is required to load MAT files. Install with: pip install scipy")
    mat = loadmat(str(path), squeeze_me=True)
    if ws.TIME not in mat or ws.VOLTAGE not in mat:
        raise ValueError(f"{path} does not contain '{ws.TIME}'/'{ws.VOLTAGE}' arrays; not a scpi_control waveform file")
    metadata: Dict[str, Any] = {}
    raw_meta = mat.get(ws.MAT_META_KEY)
    if raw_meta is not None and getattr(raw_meta, "dtype", None) is not None and raw_meta.dtype.names:
        for name in raw_meta.dtype.names:
            metadata[name] = _scalar(raw_meta[name])
    for key in (ws.TIMESTAMP,) + ws.SCALE_FIELDS:
        if key in mat:
            metadata[key] = _scalar(mat[key])
    sample_rate = _scalar(mat[ws.SAMPLE_RATE]) if ws.SAMPLE_RATE in mat else None
    return LoadedWaveform(
        time=np.asarray(mat[ws.TIME]).flatten(),
        voltage=np.asarray(mat[ws.VOLTAGE]).flatten(),
        channel=_channel_value(mat[ws.CHANNEL]) if ws.CHANNEL in mat else None,
        sample_rate=float(sample_rate) if sample_rate is not None else None,
        metadata=metadata,
        provenance=_parse_provenance(_scalar(mat[ws.PROVENANCE_JSON]) if ws.PROVENANCE_JSON in mat else None),
        source_format="MAT",
        source_path=path,
    )


def _load_hdf5(path: Path) -> LoadedWaveform:
    try:
        import h5py
    except ImportError:
        raise ImportError("h5py is required to load HDF5 files. Install with: pip install h5py")
    with h5py.File(path, "r") as f:
        if ws.TIME not in f or ws.VOLTAGE not in f:
            raise ValueError(f"{path} does not contain '{ws.TIME}'/'{ws.VOLTAGE}' datasets; not a scpi_control waveform file")
        attrs = {k: _scalar(v) for k, v in f.attrs.items()}
        metadata: Dict[str, Any] = {}
        if ws.HDF5_META_GROUP in f and isinstance(f[ws.HDF5_META_GROUP], h5py.Group):
            metadata.update({k: _scalar(v) for k, v in f[ws.HDF5_META_GROUP].attrs.items()})
        for key in (ws.TIMESTAMP, ws.HDF5_NUM_SAMPLES) + ws.SCALE_FIELDS:
            if key in attrs:
                metadata[key] = attrs[key]
        return LoadedWaveform(
            time=np.asarray(f[ws.TIME][:]),
            voltage=np.asarray(f[ws.VOLTAGE][:]),
            channel=_channel_value(attrs[ws.CHANNEL]) if ws.CHANNEL in attrs else None,
            sample_rate=float(attrs[ws.SAMPLE_RATE]) if ws.SAMPLE_RATE in attrs else None,
            metadata=metadata,
            provenance=_parse_provenance(attrs.get(ws.PROVENANCE_JSON)),
            source_format="HDF5",
            source_path=path,
        )
