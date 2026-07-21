"""The on-disk contract for saved waveforms.

`scpi_control.waveform`'s savers write these names; the report generator's
loader reads them. Both import from here so the two cannot drift apart --
they previously described the same format independently, and did not agree
(the loader guessed keys heuristically and silently corrupted every binary
format it read).

The three binary formats genuinely use three different metadata conventions.
This module records that asymmetry rather than hiding it: normalising the
formats would break every file already on disk. Unifying them is a migration,
not a bug fix.
"""

from typing import Tuple

# ---- Core fields, written by every format that has a key space -------------
TIME = "time"
VOLTAGE = "voltage"
CHANNEL = "channel"
SAMPLE_RATE = "sample_rate"
TIMESTAMP = "timestamp"

CORE_FIELDS: Tuple[str, ...] = (TIME, VOLTAGE, CHANNEL, SAMPLE_RATE, TIMESTAMP)

# ---- Per-format user-metadata conventions ---------------------------------
# NPZ: flat keys, prefixed (np.savez takes no nested structures)
NPZ_META_PREFIX = "meta_"

# MAT: a nested struct under one key
MAT_META_KEY = "metadata"

# HDF5: a group whose attrs carry the metadata; core fields are FILE attrs,
# not dataset attrs -- the distinction the loader previously got wrong.
HDF5_META_GROUP = "metadata"
HDF5_NUM_SAMPLES = "num_samples"
HDF5_FILE_ATTRS: Tuple[str, ...] = (CHANNEL, SAMPLE_RATE, HDF5_NUM_SAMPLES, TIMESTAMP)

# ---- CSV -------------------------------------------------------------------
# Plain CSV carries no metadata at all. CSV_ENHANCED prefixes a comment block
# whose "# <label>: <value>" lines carry the channel and sample rate.
CSV_COMMENT = "#"
CSV_HEADER_CHANNEL = "Channel"
CSV_HEADER_SAMPLE_RATE = "Sample Rate"

# ---- Acquisition scale fields (added 2026-07; additive, may be absent) -----
TIMEBASE = "timebase"
VOLTAGE_SCALE = "voltage_scale"
VOLTAGE_OFFSET = "voltage_offset"
SCALE_FIELDS: Tuple[str, ...] = (TIMEBASE, VOLTAGE_SCALE, VOLTAGE_OFFSET)

# ---- Provenance (added 2026-07; additive, may be absent) -------------------
# One JSON document (scpi_control.provenance.AcquisitionProvenance.to_json()).
# NPZ/MAT: a string under this key. HDF5: a FILE attr. CSV (both variants):
# a "# Provenance-JSON: {...}" comment line.
PROVENANCE_JSON = "provenance_json"
CSV_HEADER_PROVENANCE = "Provenance-JSON"
CSV_HEADER_TIMEBASE = "Timebase"
CSV_HEADER_VOLTAGE_SCALE = "Voltage Scale"
CSV_HEADER_VOLTAGE_OFFSET = "Voltage Offset"
