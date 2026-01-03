"""
Data models for test reports.

This module defines the core data structures used to represent test reports,
including waveform data, measurements, metadata, and report sections.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import numpy as np


@dataclass
class ReportMetadata:
    """Metadata for a test report."""

    title: str
    technician: str
    test_date: datetime
    equipment_id: Optional[str] = None
    equipment_model: Optional[str] = None
    test_procedure: Optional[str] = None
    notes: Optional[str] = None
    temperature: Optional[str] = None
    humidity: Optional[str] = None
    location: Optional[str] = None
    project_name: Optional[str] = None
    customer: Optional[str] = None
    revision: Optional[str] = None

    # Test type context for AI analysis
    test_type: Optional[str] = "general"  # Test type ID from test_types module

    # Branding
    company_name: Optional[str] = None
    company_logo_path: Optional[Path] = None
    header_text: Optional[str] = None
    footer_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        data = {
            "title": self.title,
            "technician": self.technician,
            "test_date": self.test_date.isoformat(),
        }

        # Add optional fields if present
        optional_fields = [
            "equipment_id", "equipment_model", "test_procedure", "notes",
            "temperature", "humidity", "location", "project_name",
            "customer", "revision", "test_type",
            "company_name", "header_text", "footer_text"
        ]

        for field_name in optional_fields:
            value = getattr(self, field_name)
            if value is not None:
                data[field_name] = value

        if self.company_logo_path:
            data["company_logo_path"] = str(self.company_logo_path)

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportMetadata":
        """Create metadata from dictionary."""
        data = data.copy()
        data["test_date"] = datetime.fromisoformat(data["test_date"])
        if "company_logo_path" in data and data["company_logo_path"]:
            data["company_logo_path"] = Path(data["company_logo_path"])
        return cls(**data)


@dataclass
class WaveformData:
    """Waveform data for inclusion in reports."""

    channel_name: str
    time_data: np.ndarray
    voltage_data: np.ndarray
    sample_rate: float
    record_length: int

    # Optional metadata
    timebase: Optional[float] = None
    voltage_scale: Optional[float] = None
    voltage_offset: Optional[float] = None
    probe_ratio: Optional[float] = None
    coupling: Optional[str] = None

    # Source file information
    source_file: Optional[Path] = None
    capture_timestamp: Optional[datetime] = None

    # Display options
    color: Optional[str] = "#1f77b4"  # Default matplotlib blue
    label: Optional[str] = None

    def __post_init__(self):
        """Set default label if not provided."""
        if self.label is None:
            self.label = self.channel_name

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excludes numpy arrays for JSON serialization)."""
        data = {
            "channel_name": self.channel_name,
            "sample_rate": self.sample_rate,
            "record_length": self.record_length,
            "color": self.color,
            "label": self.label,
        }

        # Add optional fields
        optional_fields = [
            "timebase", "voltage_scale", "voltage_offset",
            "probe_ratio", "coupling"
        ]

        for field_name in optional_fields:
            value = getattr(self, field_name)
            if value is not None:
                data[field_name] = value

        if self.source_file:
            data["source_file"] = str(self.source_file)
        if self.capture_timestamp:
            data["capture_timestamp"] = self.capture_timestamp.isoformat()

        return data


@dataclass
class MeasurementResult:
    """A measurement result with optional pass/fail status."""

    name: str
    value: float
    unit: str
    channel: Optional[str] = None

    # Pass/fail information
    passed: Optional[bool] = None
    criteria_min: Optional[float] = None
    criteria_max: Optional[float] = None

    # AI-generated insights
    ai_interpretation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
        }

        if self.channel:
            data["channel"] = self.channel
        if self.passed is not None:
            data["passed"] = self.passed
        if self.criteria_min is not None:
            data["criteria_min"] = self.criteria_min
        if self.criteria_max is not None:
            data["criteria_max"] = self.criteria_max
        if self.ai_interpretation:
            data["ai_interpretation"] = self.ai_interpretation

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MeasurementResult":
        """Create from dictionary."""
        return cls(**data)

    def format_value(self) -> str:
        """Format the measurement value with unit."""
        return f"{self.value:.6g} {self.unit}"

    def get_status_symbol(self) -> str:
        """Get a status symbol (✓, ✗, or -)."""
        if self.passed is None:
            return "—"
        return "✓" if self.passed else "✗"


@dataclass
class TestSection:
    """A section in a test report."""

    title: str
    content: str = ""
    waveforms: List[WaveformData] = field(default_factory=list)
    measurements: List[MeasurementResult] = field(default_factory=list)
    images: List[Path] = field(default_factory=list)

    # FFT data
    include_fft: bool = False
    fft_frequency: Optional[np.ndarray] = None
    fft_magnitude: Optional[np.ndarray] = None
    fft_channel: Optional[str] = None

    # AI-generated content
    ai_summary: Optional[str] = None
    ai_insights: Optional[str] = None

    order: int = 0  # For sorting sections

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excludes numpy arrays)."""
        data = {
            "title": self.title,
            "content": self.content,
            "include_fft": self.include_fft,
            "order": self.order,
            "waveforms": [w.to_dict() for w in self.waveforms],
            "measurements": [m.to_dict() for m in self.measurements],
            "images": [str(p) for p in self.images],
        }

        if self.fft_channel:
            data["fft_channel"] = self.fft_channel
        if self.ai_summary:
            data["ai_summary"] = self.ai_summary
        if self.ai_insights:
            data["ai_insights"] = self.ai_insights

        return data


@dataclass
class TestReport:
    """Complete test report containing metadata, sections, and results."""

    metadata: ReportMetadata
    sections: List[TestSection] = field(default_factory=list)

    # Overall AI analysis
    executive_summary: Optional[str] = None
    ai_generated_summary: bool = False
    key_findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Overall pass/fail
    overall_result: Optional[str] = None  # "PASS", "FAIL", "INCONCLUSIVE"

    def add_section(self, section: TestSection) -> None:
        """Add a section to the report."""
        self.sections.append(section)
        self._sort_sections()

    def _sort_sections(self) -> None:
        """Sort sections by order."""
        self.sections.sort(key=lambda s: s.order)

    def get_all_measurements(self) -> List[MeasurementResult]:
        """Get all measurements from all sections."""
        measurements = []
        for section in self.sections:
            measurements.extend(section.measurements)
        return measurements

    def get_all_waveforms(self) -> List[WaveformData]:
        """Get all waveforms from all sections."""
        waveforms = []
        for section in self.sections:
            waveforms.extend(section.waveforms)
        return waveforms

    def calculate_overall_result(self) -> str:
        """Calculate overall pass/fail result based on measurements."""
        measurements = self.get_all_measurements()

        if not measurements:
            return "INCONCLUSIVE"

        # Check if any measurements have pass/fail criteria
        has_criteria = any(m.passed is not None for m in measurements)

        if not has_criteria:
            return "INCONCLUSIVE"

        # If any measurement failed, overall is FAIL
        if any(m.passed is False for m in measurements):
            return "FAIL"

        # If all measurements with criteria passed
        return "PASS"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            "metadata": self.metadata.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "ai_generated_summary": self.ai_generated_summary,
            "key_findings": self.key_findings,
            "recommendations": self.recommendations,
        }

        if self.executive_summary:
            data["executive_summary"] = self.executive_summary
        if self.overall_result:
            data["overall_result"] = self.overall_result
        else:
            data["overall_result"] = self.calculate_overall_result()

        return data
