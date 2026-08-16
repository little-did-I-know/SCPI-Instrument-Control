"""Renderable section elements for comparison/batch reports.

These are presentation-layer values a TestSection can carry and both
generators know how to render: a status-aware table, multi-run overlay plot
specs, a raw-data manifest, and a sign-off block. They hold no analysis
logic — the comparison analyzer and report builder fill them in.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from scpi_control.report_generator.models.annotations import PlotAnnotation

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_INCOMPLETE = "incomplete"


@dataclass
class TableCell:
    """One cell: display text plus an optional pass/fail status for styling."""

    text: str
    status: Optional[str] = None  # STATUS_PASS, STATUS_FAIL, or None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"text": self.text}
        if self.status is not None:
            data["status"] = self.status
        return data


@dataclass
class ComparisonTable:
    """A generic status-aware table (comparison columns, batch summary, aggregates)."""

    title: str
    headers: List[str]
    rows: List[List[TableCell]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "headers": list(self.headers),
            "rows": [[cell.to_dict() for cell in row] for row in self.rows],
        }


@dataclass
class OverlayTrace:
    """One run's waveform in an overlay plot. `waveform` is a report
    WaveformData; typed Any to avoid a circular import with report_data."""

    run_label: str
    waveform: Any
    color: Optional[str] = None


@dataclass
class OverlayPlotSpec:
    """All runs' traces for one matched channel, drawn on a single axes."""

    channel_label: str
    traces: List[OverlayTrace] = field(default_factory=list)
    annotations: List[PlotAnnotation] = field(default_factory=list)
    caption: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        # Waveform arrays are not serializable; record what was plotted.
        data: Dict[str, Any] = {"channel_label": self.channel_label, "runs": [t.run_label for t in self.traces]}
        if self.annotations:
            data["annotations"] = [a.to_dict() for a in self.annotations]
        if self.caption:
            data["caption"] = self.caption
        return data


@dataclass
class ManifestEntry:
    """Provenance line for one source file of one run."""

    run_label: str
    file_path: str
    size_bytes: int
    sha256: str
    capture_timestamp: Optional[str] = None  # ISO string
    instrument: Optional[str] = None  # human-readable identity

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "run_label": self.run_label,
            "file_path": self.file_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }
        if self.capture_timestamp is not None:
            data["capture_timestamp"] = self.capture_timestamp
        if self.instrument is not None:
            data["instrument"] = self.instrument
        return data


@dataclass
class DataManifest:
    """Raw-data appendix: every source file with checksum and identity."""

    entries: List[ManifestEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"entries": [e.to_dict() for e in self.entries]}


@dataclass
class SignoffRole:
    """One approval line: role title plus an optional pre-filled name."""

    title: str
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"title": self.title}
        if self.name is not None:
            data["name"] = self.name
        return data


@dataclass
class SignoffBlock:
    """Printable approval block rendered at the end of a report."""

    roles: List[SignoffRole] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"roles": [r.to_dict() for r in self.roles]}
