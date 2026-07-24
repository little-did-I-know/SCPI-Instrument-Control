"""One-shot conversion of pre-5.0 pickled reference files.

Reference waveforms used to store their metadata dict as a pickled numpy
object array; loading one required allow_pickle=True, which meant loading
*any* .npz someone handed you could execute arbitrary code. That format is
no longer written (see scpi_control/reference_waveform.py, which now stores
metadata as a JSON string under REFERENCE_META_KEY and always loads with
allow_pickle=False), but files saved before the change still exist on disk
in the old, pickled format and now refuse to load at all.

This module is -- deliberately -- the only place left in the codebase that
passes allow_pickle=True. It runs exactly once per file, only when the user
explicitly invokes 'scpi-web references migrate', against files that are
already sitting in their own reference storage directory. It is not reachable
from any network-facing code path. Do not add allow_pickle=True anywhere
else, and do not lift this pattern into new code -- every other loader in
this codebase depends on allow_pickle=False to keep a hostile .npz from
smuggling in pickled bytecode.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict

import numpy as np

from scpi_control.reference_waveform import REFERENCE_META_KEY

logger = logging.getLogger(__name__)


def migrate_references(storage_dir: str) -> Dict[str, int]:
    """Convert every pre-5.0 pickled .npz reference file in storage_dir.

    A file already in the new format (REFERENCE_META_KEY present) or one
    with no metadata block at all is counted as skipped and left untouched
    -- migration never rewrites a file it doesn't need to, which is what
    makes running it twice a no-op. A file that can't be read or converted
    is counted as failed and, crucially, also left untouched: conversion
    writes to a temporary file first and only replaces the original once
    the write fully succeeds, so a failure never leaves a truncated or
    half-written file where a readable (if old-format) one used to be.

    Args:
        storage_dir: Directory to scan for *.npz reference files.

    Returns:
        {"converted": n, "skipped": n, "failed": n}. The three counts always
        sum to the number of .npz files examined.
    """
    result = {"converted": 0, "skipped": 0, "failed": 0}

    for filepath in sorted(Path(storage_dir).glob("*.npz")):
        try:
            payload = _build_payload(filepath)
        except Exception:
            logger.warning("could not read %s, leaving it untouched", filepath, exc_info=True)
            result["failed"] += 1
            continue

        if payload is None:
            result["skipped"] += 1
            continue

        try:
            _atomic_savez(filepath, payload)
        except Exception:
            logger.warning("could not convert %s, leaving it untouched", filepath, exc_info=True)
            result["failed"] += 1
            continue

        result["converted"] += 1

    return result


def _build_payload(filepath: Path):
    """Read filepath and return its arrays with metadata re-encoded as JSON.

    Returns None if the file is already migrated or has no metadata to
    migrate (both count as "skipped" by the caller). Raises if the file
    can't be read at all (counted as "failed" by the caller).
    """
    with np.load(filepath, allow_pickle=True) as data:
        if REFERENCE_META_KEY in data.files or "metadata" not in data.files:
            return None

        payload = {key: data[key] for key in data.files if key != "metadata"}
        payload[REFERENCE_META_KEY] = json.dumps(data["metadata"].item())
        return payload


def _atomic_savez(filepath: Path, payload: Dict) -> None:
    """Write payload as a new .npz and swap it in only once fully written.

    np.savez_compressed writes directly to whatever path it's given; pointed
    straight at the original file, a failure partway through (disk full,
    interrupted process) would destroy the last readable copy. Writing to a
    sibling temp file and swapping it in with os.replace -- atomic on both
    POSIX and Windows for a same-directory rename -- means a failure here
    always leaves the original file exactly as it was.
    """
    fd, tmp_name = tempfile.mkstemp(prefix="{0}.".format(filepath.stem), suffix=".npz", dir=str(filepath.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        np.savez_compressed(str(tmp_path), **payload)
        os.replace(str(tmp_path), str(filepath))
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
