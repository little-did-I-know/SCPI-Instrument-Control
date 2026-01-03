"""
Report template system for saving and reusing report configurations.

Templates allow users to save report settings, criteria, and formatting
preferences for reuse across multiple test sessions.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from datetime import datetime

from siglent.report_generator.models.criteria import CriteriaSet


@dataclass
class SectionTemplate:
    """Template for a report section."""

    title: str
    content: str = ""
    include_waveforms: bool = True
    include_measurements: bool = True
    include_fft: bool = False
    include_ai_insights: bool = False
    order: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "content": self.content,
            "include_waveforms": self.include_waveforms,
            "include_measurements": self.include_measurements,
            "include_fft": self.include_fft,
            "include_ai_insights": self.include_ai_insights,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SectionTemplate":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class BrandingTemplate:
    """Template for report branding."""

    company_name: Optional[str] = None
    company_logo_path: Optional[Path] = None
    header_text: Optional[str] = None
    footer_text: Optional[str] = None

    # Color scheme
    primary_color: str = "#1f77b4"
    secondary_color: str = "#ff7f0e"
    success_color: str = "#2ca02c"
    failure_color: str = "#d62728"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "success_color": self.success_color,
            "failure_color": self.failure_color,
        }

        if self.company_name:
            data["company_name"] = self.company_name
        if self.company_logo_path:
            data["company_logo_path"] = str(self.company_logo_path)
        if self.header_text:
            data["header_text"] = self.header_text
        if self.footer_text:
            data["footer_text"] = self.footer_text

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrandingTemplate":
        """Create from dictionary."""
        data = data.copy()
        if "company_logo_path" in data and data["company_logo_path"]:
            data["company_logo_path"] = Path(data["company_logo_path"])
        return cls(**data)


@dataclass
class ReportTemplate:
    """
    Complete template for generating reports.

    Templates store all configuration needed to generate a report,
    including sections, criteria, branding, and AI settings.
    """

    name: str
    description: Optional[str] = None

    # Sections to include
    sections: List[SectionTemplate] = field(default_factory=list)

    # Measurement criteria
    criteria_set: Optional[CriteriaSet] = None

    # Branding
    branding: BrandingTemplate = field(default_factory=BrandingTemplate)

    # Default metadata fields
    default_equipment_model: Optional[str] = None
    default_test_procedure: Optional[str] = None

    # AI settings
    enable_ai_summary: bool = False
    enable_ai_insights: bool = False
    enable_ai_interpretation: bool = False

    # Metadata
    created_date: datetime = field(default_factory=datetime.now)
    modified_date: datetime = field(default_factory=datetime.now)
    author: Optional[str] = None
    version: str = "1.0"

    def add_section(self, section: SectionTemplate) -> None:
        """Add a section template."""
        self.sections.append(section)
        self._sort_sections()

    def _sort_sections(self) -> None:
        """Sort sections by order."""
        self.sections.sort(key=lambda s: s.order)

    def save(self, filepath: Path) -> None:
        """
        Save template to JSON file.

        Args:
            filepath: Path to save the template
        """
        self.modified_date = datetime.now()

        data = self.to_dict()

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: Path) -> "ReportTemplate":
        """
        Load template from JSON file.

        Args:
            filepath: Path to the template file

        Returns:
            ReportTemplate instance
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            "name": self.name,
            "sections": [s.to_dict() for s in self.sections],
            "branding": self.branding.to_dict(),
            "enable_ai_summary": self.enable_ai_summary,
            "enable_ai_insights": self.enable_ai_insights,
            "enable_ai_interpretation": self.enable_ai_interpretation,
            "created_date": self.created_date.isoformat(),
            "modified_date": self.modified_date.isoformat(),
            "version": self.version,
        }

        # Optional fields
        if self.description:
            data["description"] = self.description
        if self.criteria_set:
            data["criteria_set"] = self.criteria_set.to_dict()
        if self.default_equipment_model:
            data["default_equipment_model"] = self.default_equipment_model
        if self.default_test_procedure:
            data["default_test_procedure"] = self.default_test_procedure
        if self.author:
            data["author"] = self.author

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportTemplate":
        """Create from dictionary."""
        data = data.copy()

        # Parse sections
        data["sections"] = [
            SectionTemplate.from_dict(s) for s in data.get("sections", [])
        ]

        # Parse branding
        data["branding"] = BrandingTemplate.from_dict(data.get("branding", {}))

        # Parse criteria set
        if "criteria_set" in data and data["criteria_set"]:
            data["criteria_set"] = CriteriaSet.from_dict(data["criteria_set"])

        # Parse dates
        if "created_date" in data:
            data["created_date"] = datetime.fromisoformat(data["created_date"])
        if "modified_date" in data:
            data["modified_date"] = datetime.fromisoformat(data["modified_date"])

        return cls(**data)

    @classmethod
    def create_default_template(cls) -> "ReportTemplate":
        """Create a default template with standard sections."""
        template = cls(
            name="Default Report Template",
            description="Standard oscilloscope test report with all common sections",
        )

        # Add standard sections
        template.add_section(
            SectionTemplate(
                title="Executive Summary",
                content="Overview of test results and key findings.",
                include_waveforms=False,
                include_measurements=True,
                include_ai_insights=True,
                order=0,
            )
        )

        template.add_section(
            SectionTemplate(
                title="Test Setup",
                content="Equipment configuration and test conditions.",
                include_waveforms=False,
                include_measurements=False,
                order=1,
            )
        )

        template.add_section(
            SectionTemplate(
                title="Waveform Captures",
                content="Captured waveforms and time-domain analysis.",
                include_waveforms=True,
                include_measurements=True,
                order=2,
            )
        )

        template.add_section(
            SectionTemplate(
                title="Frequency Analysis",
                content="FFT analysis and frequency domain measurements.",
                include_waveforms=False,
                include_measurements=True,
                include_fft=True,
                order=3,
            )
        )

        template.add_section(
            SectionTemplate(
                title="Measurement Results",
                content="Detailed measurement results with pass/fail criteria.",
                include_waveforms=False,
                include_measurements=True,
                order=4,
            )
        )

        template.add_section(
            SectionTemplate(
                title="Conclusions",
                content="Summary of findings and recommendations.",
                include_waveforms=False,
                include_measurements=False,
                include_ai_insights=True,
                order=5,
            )
        )

        return template
