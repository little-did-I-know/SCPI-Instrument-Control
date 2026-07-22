"""Builds TestReports from analyzed RunSets, plus the manifest/sign-off helpers
shared with the single-run report path."""

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from scpi_control.report_generator.models.comparison import Run
from scpi_control.report_generator.models.report_elements import DataManifest, ManifestEntry, SignoffBlock, SignoffRole

logger = logging.getLogger(__name__)

DEFAULT_SIGNOFF_ROLES = ["Tested by", "Reviewed by", "Approved by"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _instrument_string(provenance) -> Optional[str]:
    """'Manufacturer Model (Serial)' from an AcquisitionProvenance, or None."""
    if provenance is None or provenance.instrument is None:
        return None
    info = provenance.instrument
    parts = [p for p in (info.manufacturer, info.model) if p]
    if not parts and not info.serial:
        return None
    text = " ".join(parts) if parts else "Unknown instrument"
    if info.serial:
        text += f" ({info.serial})"
    return text


def build_manifest(runs: List[Run]) -> DataManifest:
    """One entry per source file per run. Timestamp: provenance acquired_at,
    else waveform capture_timestamp, else file mtime (ISO, UTC)."""
    entries: List[ManifestEntry] = []
    for run in runs:
        by_source: Dict[str, object] = {}
        for wf in run.waveforms:
            if wf.source_file is not None:
                by_source.setdefault(str(wf.source_file), wf)
        for filepath in run.files:
            path = Path(filepath)
            wf = by_source.get(str(path))
            provenance = getattr(wf, "provenance", None) if wf is not None else None
            timestamp = None
            if provenance is not None and provenance.acquired_at:
                timestamp = provenance.acquired_at
            elif wf is not None and getattr(wf, "capture_timestamp", None):
                timestamp = wf.capture_timestamp.isoformat()
            elif path.exists():
                timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
            entries.append(
                ManifestEntry(
                    run_label=run.label,
                    file_path=str(path),
                    size_bytes=path.stat().st_size if path.exists() else 0,
                    sha256=_sha256(path) if path.exists() else "",
                    capture_timestamp=timestamp,
                    instrument=_instrument_string(provenance),
                )
            )
    return DataManifest(entries=entries)


def build_signoff(roles: List[str], names: Optional[Dict[str, str]] = None) -> SignoffBlock:
    names = names or {}
    return SignoffBlock(roles=[SignoffRole(title=title, name=names.get(title)) for title in roles])
