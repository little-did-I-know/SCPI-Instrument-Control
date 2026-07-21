# Data Provenance

Every waveform you save now carries a record of the instrument and settings
that produced it. This guide covers what that record contains, where it
lives in each file format, and how to get it (and your raw data) back out
with `load_waveform()` or the `scpi-extract` command-line tool.

## What Provenance Is

When you acquire a waveform, the library snapshots the instrument state at
that moment and attaches it to the returned `WaveformData`:

- **Instrument**: manufacturer, model, serial number, firmware
- **Channel settings**: enabled, coupling, voltage scale, voltage offset,
  probe ratio, bandwidth limit, unit -- for the channel(s) acquired
- **Trigger settings**: mode, type, source, level, slope, coupling, holdoff
- **Timebase and sample rate**
- **`acquired_at`**: a UTC ISO-8601 timestamp
- **Connection details**: instrument address, SCPI dialect
- **Library version** that produced the file

```python
from scpi_control import Oscilloscope

with Oscilloscope('192.168.1.100') as scope:
    waveform = scope.get_waveform(channel=1)  # provenance=True by default

    prov = waveform.provenance
    print(prov.instrument.model)              # e.g. 'SDS824X HD'
    print(prov.channels[1].probe_ratio)        # e.g. 10.0
    print(prov.acquired_at)                    # UTC timestamp
```

The snapshot is taken at acquisition time, so it reflects the settings that
actually produced the trace -- not whatever the scope happens to be set to
later. Individual fields that a model can't answer come back as `None`
rather than failing the acquisition, and if the snapshot itself fails (a
communication hiccup, an unsupported query), the library logs a warning and
returns the waveform with `provenance=None` instead of losing the capture.

### Skipping Provenance

High-rate paths -- live view, streaming -- pass `provenance=False` to skip
the extra queries:

```python
waveform = scope.get_waveform(channel=1, provenance=False)
# or, calling the lower-level API directly:
waveform = scope.waveform.acquire(channel=1, provenance=False)
```

## Where It Lives in Each Format

Provenance is stored additively -- existing readers of these files (your own
scripts, other tools) that don't know about it simply ignore the new keys.

| Format | Where | Key/Field |
| --- | --- | --- |
| NPZ | Array key | `provenance_json` (JSON string) |
| MAT | Struct key | `provenance_json` (JSON string) |
| HDF5 | File attribute | `provenance_json` (JSON string) |
| Enhanced CSV (`CSV_ENHANCED`) | Header comment line | `# Provenance-JSON: {...}` |
| Plain CSV | Header comment line (only when provenance is present) | `# Provenance-JSON: {...}` |

All formats also gained three scale fields, written alongside the existing
`time`, `voltage`, `channel`, and `sample_rate` data:

| Field | NPZ/MAT/HDF5 key | CSV header line |
| --- | --- | --- |
| Timebase (s/div) | `timebase` | `# Timebase: <value> s/div` |
| Voltage scale (V/div) | `voltage_scale` | `# Voltage Scale: <value> V/div` |
| Voltage offset (V) | `voltage_offset` | `# Voltage Offset: <value> V` |

The binary formats (NPZ, MAT, HDF5) always write the scale fields. Plain CSV
only writes its header block -- title, `# Channel:`, `# Sample Rate:`, the
scale lines, `# Instrument:`, `# Acquired (UTC):`, and `# Provenance-JSON:`
-- when the waveform actually carries a provenance object. A capture saved
with `provenance=False` produces a plain CSV that is byte-for-byte identical
to what the library wrote before this feature existed.

### Restoring the Legacy CSV Layout

If you need the fully headerless plain-CSV layout regardless of whether
provenance is present -- for a downstream tool that chokes on comment
lines, for example -- pass `bare=True`:

```python
scope.waveform.save_waveform(waveform, "capture.csv", format="CSV", bare=True)
```

## Extracting Your Data

`scpi_control.waveform_io.load_waveform()` reads all five saved formats --
NPZ, plain CSV, enhanced CSV, MAT, HDF5 -- whether or not they carry
provenance:

```python
from scpi_control.waveform_io import load_waveform

lw = load_waveform("capture.npz")          # any of the 5 formats, old or new
lw.time, lw.voltage                        # numpy arrays
lw.provenance.instrument.model             # 'SDS824X HD'
lw.provenance.channels[1].probe_ratio      # 10.0
df = lw.to_dataframe()                     # pandas; metadata in df.attrs
```

`load_waveform()` auto-detects the format from the file extension
(`.npz`/`.npy`, `.csv`, `.mat`, `.h5`/`.hdf5`); pass `format="CSV"` (etc.) to
override it. The returned `LoadedWaveform` normalizes the three binary
formats' differing metadata conventions into one flat `metadata` dict, plus
`time`, `voltage`, `channel`, `sample_rate`, `provenance`, `source_format`,
and `source_path`.

`to_dataframe()` needs pandas installed (`pip install pandas`); it raises
`ImportError` with an install hint if it's missing.

## The `scpi-extract` Command

`scpi-extract` inspects and exports saved waveform files without writing any
Python:

```bash
scpi-extract capture.npz
```

```text
File:        capture.npz (NPZ)
Channel:     1
Samples:     256
Sample rate: 1000.0
Instrument:  Siglent Technologies SDS1104X-E (serial MOCK0001, firmware 1.0.0.0)
Acquired:    2026-07-21T16:09:04.840835+00:00
Address:     mock:5025  Dialect: legacy  Library: v3.0.0
Channel 1:   scale=1.0 V/div offset=0.0 V coupling=DC probe=10.0x bw=OFF
Timebase:    0.001 s/div
Metadata:
  timebase: 0.001
  timestamp: 2026-07-21T09:09:04.840835
  voltage_offset: 0.0
  voltage_scale: 1.0
```

`--info` (the default when no other flag is given) prints that summary.
`--csv OUT` dumps the raw `time,voltage` rows to a new CSV file:

```bash
scpi-extract capture.mat --csv out.csv
```

`--json` prints metadata and provenance as machine-readable JSON, for
piping into other tools:

```bash
scpi-extract capture.h5 --json
```

`--format {NPZ,CSV,MAT,HDF5}` overrides format auto-detection when a file's
extension doesn't match its contents. Errors (missing file, unparseable
format, missing optional dependency) print to stderr and exit with status 1.

## Legacy Files

Any file saved before this release loads exactly as before -- `load_waveform()`
and `scpi-extract` both handle it, and `provenance` simply comes back `None`:

```python
lw = load_waveform("old_capture.npz")
assert lw.provenance is None   # file predates provenance capture
lw.time, lw.voltage            # still there
```

## See Also

- [Waveform Capture](waveform-capture.md) for acquisition and saving basics
- `examples/waveform_provenance_and_extract.py` for a runnable, hardware-free
  walkthrough of this entire flow
