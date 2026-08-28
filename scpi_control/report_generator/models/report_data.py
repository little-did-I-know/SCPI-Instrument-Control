"""
Data models for test reports.

This module defines the core data structures used to represent test reports,
including waveform data, measurements, metadata, and report sections.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np

from scpi_control.waveform import WaveformData as CaptureWaveform
from scpi_control.report_generator.models.annotations import PlotAnnotation
from scpi_control.report_generator.models.report_elements import ComparisonTable, DataManifest, OverlayPlotSpec, SignoffBlock

if TYPE_CHECKING:
    from scpi_control.quantities import Quantity

SUMMARY_SOURCE_MANUAL = "manual"
SUMMARY_SOURCE_AI = "ai"
SUMMARY_SOURCE_COMPUTED = "computed"


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
            "equipment_id",
            "equipment_model",
            "test_procedure",
            "notes",
            "temperature",
            "humidity",
            "location",
            "project_name",
            "customer",
            "revision",
            "test_type",
            "company_name",
            "header_text",
            "footer_text",
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
class WaveformRegion:
    """
    Represents a region of interest within a waveform for detailed analysis.

    Regions can be automatically detected (plateaus, edges, transients) or
    manually defined. Each region can have its own analysis, annotations,
    and AI-generated insights.
    """

    # Region identification
    start_time: float  # Start time in seconds
    end_time: float  # End time in seconds
    label: str = "Region"
    description: Optional[str] = None

    # Region type classification
    region_type: Optional[str] = None  # 'plateau_high', 'plateau_low', 'edge_rising', 'edge_falling', 'transient', 'noise', 'custom'
    auto_detected: bool = False

    # Analysis results specific to this region
    slope: Optional[float] = None  # V/s
    flatness: Optional[float] = None  # Standard deviation
    noise_level: Optional[float] = None  # RMS noise
    drift: Optional[float] = None  # Linear drift over region

    # Ideal/reference comparison
    ideal_value: Optional[float] = None  # Expected voltage level
    deviation_from_ideal: Optional[float] = None  # Difference from ideal
    tolerance_min: Optional[float] = None  # Minimum acceptable value
    tolerance_max: Optional[float] = None  # Maximum acceptable value
    passes_spec: Optional[bool] = None  # Whether region meets spec

    # Calibration guidance (for probe calibration, etc.)
    calibration_recommendation: Optional[str] = None

    # Visual annotations
    highlight_color: Optional[str] = None

    # AI analysis
    ai_insights: Optional[str] = None

    # Statistics (subset of waveform statistics for this region only)
    statistics: Optional[Dict[str, Any]] = None

    def get_duration(self) -> float:
        """Get region duration in seconds."""
        return self.end_time - self.start_time

    def contains_time(self, time: float) -> bool:
        """Check if a time point falls within this region."""
        return self.start_time <= time <= self.end_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "label": self.label,
            "auto_detected": self.auto_detected,
        }

        # Add optional fields
        optional_fields = [
            "description",
            "region_type",
            "slope",
            "flatness",
            "noise_level",
            "drift",
            "ideal_value",
            "deviation_from_ideal",
            "tolerance_min",
            "tolerance_max",
            "passes_spec",
            "calibration_recommendation",
            "highlight_color",
            "ai_insights",
        ]

        for field_name in optional_fields:
            value = getattr(self, field_name)
            if value is not None:
                data[field_name] = value

        if self.statistics:
            data["statistics"] = self.statistics

        return data


@dataclass
class WaveformData(CaptureWaveform):
    """A captured waveform plus everything a report needs to present it.

    Subclasses the library's WaveformData so the physics -- time, voltage, channel,
    sample_rate, record_length and the instrument's timebase/voltage_scale -- is
    defined once, in scpi_control.waveform. Only report concerns live here.
    """

    # `field()` with no default is REQUIRED, and is the only spelling that works.
    # A bare `sample_rate: float` does NOT re-require the field: @dataclass keeps
    # defaults as class attributes, so the annotation inherits the base's None and
    # the field silently stays optional. Losing that would not raise at runtime --
    # the base's __post_init__ derives both sample_rate and record_length from the
    # arrays anyway -- so what field() actually protects is the explicit contract:
    # callers must state these rather than let them be silently inferred.
    sample_rate: float = field()
    record_length: int = field()

    # Instrument metadata the library does not carry
    probe_ratio: Optional[float] = None
    coupling: Optional[str] = None

    # Source file information
    source_file: Optional[Path] = None
    capture_timestamp: Optional[datetime] = None

    # Display options
    color: Optional[str] = "#1f77b4"  # Default matplotlib blue
    label: Optional[str] = None

    # Signal analysis results
    signal_type: Optional[str] = None
    signal_type_confidence: Optional[float] = None
    statistics: Optional[Dict[str, Any]] = None

    # Uncertainty-carrying statistics, additive alongside `statistics` above.
    # Never set by analyze() (a single capture has no spread to measure) --
    # a caller populates this from WaveformAnalyzer.compute_statistical_quantity
    # across repeated captures. String-annotated so this file never needs the
    # optional `uncertainty` extra just to import.
    uncertain_statistics: Optional[Dict[str, "Quantity"]] = None

    # Regions of interest for detailed analysis
    regions: List[WaveformRegion] = field(default_factory=list)

    # User-supplied plot annotations and figure caption
    annotations: List[PlotAnnotation] = field(default_factory=list)
    caption: Optional[str] = None

    def __post_init__(self):
        """Validate via the library's rules, then apply report defaults."""
        super().__post_init__()
        self.channel = str(self.channel)
        if self.label is None:
            self.label = self.channel

    def analyze(self) -> None:
        """
        Analyze the waveform and populate signal type and statistics.

        This method uses the WaveformAnalyzer to detect signal type and
        calculate comprehensive statistics, storing them in the instance.
        """
        # Import here to avoid circular dependency
        from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer

        # Calculate all statistics including signal type
        self.statistics = WaveformAnalyzer.analyze(self)

        # Extract signal type info to dedicated fields for easy access
        if self.statistics:
            self.signal_type = self.statistics.get("signal_type")
            self.signal_type_confidence = self.statistics.get("signal_type_confidence")

    def get_statistic(self, name: str) -> Optional[Any]:
        """
        Get a specific statistic by name.

        Args:
            name: Statistic name (e.g., 'vmax', 'frequency', 'rise_time')

        Returns:
            The statistic value, or None if not calculated
        """
        if self.statistics is None:
            return None
        return self.statistics.get(name)

    def format_statistic(self, name: str) -> str:
        """
        Get a formatted string for a statistic.

        Args:
            name: Statistic name

        Returns:
            Formatted string with value and units
        """
        from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer

        value = self.get_statistic(name)
        return WaveformAnalyzer.format_stat_value(name, value)

    def add_region(self, start_time: float, end_time: float, label: str = "Region", **kwargs) -> WaveformRegion:
        """
        Add a region of interest to this waveform.

        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            label: Region label
            **kwargs: Additional WaveformRegion parameters

        Returns:
            The created WaveformRegion object
        """
        region = WaveformRegion(start_time=start_time, end_time=end_time, label=label, **kwargs)
        self.regions.append(region)
        return region

    def get_region_data(self, region: WaveformRegion) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract time and voltage data for a specific region.

        Args:
            region: WaveformRegion to extract

        Returns:
            Tuple of (time, voltage) for the region
        """
        # Find indices for this time range
        mask = (self.time >= region.start_time) & (self.time <= region.end_time)
        return self.time[mask], self.voltage[mask]

    def remove_region(self, region: WaveformRegion) -> bool:
        """
        Remove a region from this waveform.

        Args:
            region: WaveformRegion to remove

        Returns:
            True if removed, False if not found
        """
        try:
            self.regions.remove(region)
            return True
        except ValueError:
            return False

    def clear_regions(self) -> None:
        """Remove all regions from this waveform."""
        self.regions.clear()

    def get_regions_by_type(self, region_type: str) -> List[WaveformRegion]:
        """
        Get all regions of a specific type.

        Args:
            region_type: Type to filter by (e.g., 'plateau_high', 'edge_rising')

        Returns:
            List of matching regions
        """
        return [r for r in self.regions if r.region_type == region_type]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excludes numpy arrays for JSON serialization)."""
        data = {
            "channel_name": self.channel,
            "sample_rate": self.sample_rate,
            "record_length": self.record_length,
            "color": self.color,
            "label": self.label,
        }

        # Add optional fields
        optional_fields = ["timebase", "voltage_scale", "voltage_offset", "probe_ratio", "coupling", "signal_type", "signal_type_confidence"]

        for field_name in optional_fields:
            value = getattr(self, field_name)
            if value is not None:
                data[field_name] = value

        if self.source_file:
            data["source_file"] = str(self.source_file)
        if self.capture_timestamp:
            data["capture_timestamp"] = self.capture_timestamp.isoformat()

        # Add statistics (exclude numpy arrays and convert values to basic types)
        if self.statistics:
            stats_serializable = {}
            for key, value in self.statistics.items():
                if value is not None and not isinstance(value, np.ndarray):
                    # Convert numpy types to Python types
                    if isinstance(value, (np.integer, np.floating)):
                        stats_serializable[key] = float(value)
                    else:
                        stats_serializable[key] = value
            if stats_serializable:
                data["statistics"] = stats_serializable

        # Add uncertain_statistics (each Quantity -> a JSON-safe {value, uncertainty, unit} dict)
        if self.uncertain_statistics:
            uncertain_serializable = {}
            for key, q in self.uncertain_statistics.items():
                magnitude = q.magnitude
                if hasattr(magnitude, "nominal_value"):
                    value, uncertainty = float(magnitude.nominal_value), float(magnitude.std_dev)
                else:
                    value, uncertainty = float(magnitude), None
                uncertain_serializable[key] = {"value": value, "uncertainty": uncertainty, "unit": format(q.units, "~")}
            data["uncertain_statistics"] = uncertain_serializable

        # Add regions
        if self.regions:
            data["regions"] = [region.to_dict() for region in self.regions]

        if self.annotations:
            data["annotations"] = [a.to_dict() for a in self.annotations]
        if self.caption:
            data["caption"] = self.caption

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

    # Comparison/batch elements (rendered by both generators when set)
    comparison_table: Optional[ComparisonTable] = None
    overlay_plots: List[OverlayPlotSpec] = field(default_factory=list)
    manifest: Optional[DataManifest] = None
    signoff: Optional[SignoffBlock] = None

    # FFT plot annotations and figure caption
    fft_annotations: List[PlotAnnotation] = field(default_factory=list)
    fft_caption: Optional[str] = None

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

        if self.comparison_table:
            data["comparison_table"] = self.comparison_table.to_dict()
        if self.overlay_plots:
            data["overlay_plots"] = [p.to_dict() for p in self.overlay_plots]
        if self.manifest:
            data["manifest"] = self.manifest.to_dict()
        if self.signoff:
            data["signoff"] = self.signoff.to_dict()

        if self.fft_annotations:
            data["fft_annotations"] = [a.to_dict() for a in self.fft_annotations]
        if self.fft_caption:
            data["fft_caption"] = self.fft_caption

        return data


@dataclass
class TestReport:
    """Complete test report containing metadata, sections, and results."""

    metadata: ReportMetadata
    sections: List[TestSection] = field(default_factory=list)

    # Overall AI analysis
    executive_summary: Optional[str] = None
    summary_source: str = SUMMARY_SOURCE_MANUAL
    key_findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Overall pass/fail
    overall_result: Optional[str] = None  # "PASS", "FAIL", "INCONCLUSIVE"

    # Provenance for the generated narrative. Same three values as summary_source
    # (the SUMMARY_SOURCE_* constants are generic despite their names). Appended at
    # the end of the dataclass deliberately: inserting mid-class would reorder
    # positional construction.
    findings_source: str = SUMMARY_SOURCE_MANUAL
    recommendations_source: str = SUMMARY_SOURCE_MANUAL

    def summary_attribution(self) -> Optional[str]:
        """The provenance note to show under the executive summary, or None.

        None for a hand-authored (manual) summary; a labelled note for an
        AI-generated or a deterministically-computed one.
        """
        if self.summary_source == SUMMARY_SOURCE_AI:
            return "Summary generated by AI"
        if self.summary_source == SUMMARY_SOURCE_COMPUTED:
            return "Computed automatically from measurements"
        return None

    def findings_attribution(self) -> Optional[str]:
        """The provenance note to show under Key Findings, or None if hand-authored."""
        if self.findings_source == SUMMARY_SOURCE_AI:
            return "Key findings generated by AI"
        if self.findings_source == SUMMARY_SOURCE_COMPUTED:
            return "Computed automatically from measurements"
        return None

    def recommendations_attribution(self) -> Optional[str]:
        """The provenance note to show under Recommendations, or None if hand-authored."""
        if self.recommendations_source == SUMMARY_SOURCE_AI:
            return "Recommendations generated by AI"
        if self.recommendations_source == SUMMARY_SOURCE_COMPUTED:
            return "Computed automatically from measurements"
        return None

    def apply_ai_content(self, ai_content: Dict[str, Any]) -> None:
        """Copy AI-generated narrative into this report, marking each field's source.

        Text and attribution are set together so a caller cannot transfer one
        without the other -- copying the text while dropping the flag is what made
        AI-written findings ship unlabelled in exported reports (Task 4 review, C1).

        ai_content keys are all optional: "executive_summary", "key_findings",
        "recommendations". Only keys present with truthy values are applied.
        """
        if ai_content.get("executive_summary"):
            self.executive_summary = ai_content["executive_summary"]
            self.summary_source = SUMMARY_SOURCE_AI

        if ai_content.get("key_findings"):
            self.key_findings = ai_content["key_findings"]
            self.findings_source = SUMMARY_SOURCE_AI

        if ai_content.get("recommendations"):
            self.recommendations = ai_content["recommendations"]
            self.recommendations_source = SUMMARY_SOURCE_AI

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
            "summary_source": self.summary_source,
            "ai_generated_summary": self.summary_source == SUMMARY_SOURCE_AI,
            "findings_source": self.findings_source,
            "recommendations_source": self.recommendations_source,
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
