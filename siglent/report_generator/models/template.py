"""
Report template system for saving and reusing report configurations.

Templates allow users to save report settings, criteria, and formatting
preferences for reuse across multiple test sessions.
"""

import json
import os
import platform
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from siglent.report_generator.models.criteria import CriteriaSet
from siglent.report_generator.models.plot_style import PlotStyle


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

    # Report section inclusion
    include_executive_summary: bool = True
    include_key_findings: bool = True
    include_recommendations: bool = True
    include_waveform_plots: bool = True
    include_fft_analysis: bool = True

    # AI/LLM settings
    llm_provider: Optional[str] = None  # "ollama", "lm_studio", "openai", "custom"
    llm_endpoint: Optional[str] = None
    llm_model: Optional[str] = None
    auto_generate_summary: bool = False
    auto_generate_findings: bool = False
    auto_generate_recommendations: bool = False

    # Output format preferences
    page_size: str = "letter"  # "letter", "a4"
    plot_width_inches: float = 6.5
    plot_height_inches: float = 3.0
    plot_dpi: int = 150

    # Plot style
    plot_style: PlotStyle = field(default_factory=PlotStyle)

    # Default metadata fields (extended)
    default_equipment_model: Optional[str] = None
    default_test_procedure: Optional[str] = None
    default_test_type: Optional[str] = "general"  # Default test type
    default_company_name: Optional[str] = None
    default_technician: Optional[str] = None
    default_temperature: Optional[str] = None
    default_humidity: Optional[str] = None
    default_location: Optional[str] = None

    # Legacy AI settings (kept for backward compatibility)
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
            # Report section inclusion
            "include_executive_summary": self.include_executive_summary,
            "include_key_findings": self.include_key_findings,
            "include_recommendations": self.include_recommendations,
            "include_waveform_plots": self.include_waveform_plots,
            "include_fft_analysis": self.include_fft_analysis,
            # AI/LLM settings
            "auto_generate_summary": self.auto_generate_summary,
            "auto_generate_findings": self.auto_generate_findings,
            "auto_generate_recommendations": self.auto_generate_recommendations,
            # Output format preferences
            "page_size": self.page_size,
            "plot_width_inches": self.plot_width_inches,
            "plot_height_inches": self.plot_height_inches,
            "plot_dpi": self.plot_dpi,
            # Plot style
            "plot_style": self.plot_style.to_dict(),
            # Legacy AI settings (for backward compatibility)
            "enable_ai_summary": self.enable_ai_summary,
            "enable_ai_insights": self.enable_ai_insights,
            "enable_ai_interpretation": self.enable_ai_interpretation,
            # Metadata
            "created_date": self.created_date.isoformat(),
            "modified_date": self.modified_date.isoformat(),
            "version": self.version,
        }

        # Optional fields
        if self.description:
            data["description"] = self.description
        if self.criteria_set:
            data["criteria_set"] = self.criteria_set.to_dict()
        if self.llm_provider:
            data["llm_provider"] = self.llm_provider
        if self.llm_endpoint:
            data["llm_endpoint"] = self.llm_endpoint
        if self.llm_model:
            data["llm_model"] = self.llm_model
        if self.default_equipment_model:
            data["default_equipment_model"] = self.default_equipment_model
        if self.default_test_procedure:
            data["default_test_procedure"] = self.default_test_procedure
        if self.default_test_type:
            data["default_test_type"] = self.default_test_type
        if self.default_company_name:
            data["default_company_name"] = self.default_company_name
        if self.default_technician:
            data["default_technician"] = self.default_technician
        if self.default_temperature:
            data["default_temperature"] = self.default_temperature
        if self.default_humidity:
            data["default_humidity"] = self.default_humidity
        if self.default_location:
            data["default_location"] = self.default_location
        if self.author:
            data["author"] = self.author

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportTemplate":
        """Create from dictionary with backward compatibility."""
        data = data.copy()

        # Parse sections
        data["sections"] = [SectionTemplate.from_dict(s) for s in data.get("sections", [])]

        # Parse branding
        data["branding"] = BrandingTemplate.from_dict(data.get("branding", {}))

        # Parse criteria set
        if "criteria_set" in data and data["criteria_set"]:
            data["criteria_set"] = CriteriaSet.from_dict(data["criteria_set"])

        # Parse plot style (new field, default if missing for backward compatibility)
        if "plot_style" in data and data["plot_style"]:
            data["plot_style"] = PlotStyle.from_dict(data["plot_style"])
        else:
            data["plot_style"] = PlotStyle()

        # Parse dates
        if "created_date" in data:
            data["created_date"] = datetime.fromisoformat(data["created_date"])
        if "modified_date" in data:
            data["modified_date"] = datetime.fromisoformat(data["modified_date"])

        # Remove any keys that aren't in the dataclass fields (for forward compatibility)
        # This allows newer versions to add fields without breaking older templates
        valid_fields = {
            "name",
            "description",
            "sections",
            "criteria_set",
            "branding",
            "include_executive_summary",
            "include_key_findings",
            "include_recommendations",
            "include_waveform_plots",
            "include_fft_analysis",
            "llm_provider",
            "llm_endpoint",
            "llm_model",
            "auto_generate_summary",
            "auto_generate_findings",
            "auto_generate_recommendations",
            "page_size",
            "plot_width_inches",
            "plot_height_inches",
            "plot_dpi",
            "plot_style",
            "default_equipment_model",
            "default_test_procedure",
            "default_test_type",
            "default_company_name",
            "default_technician",
            "default_temperature",
            "default_humidity",
            "default_location",
            "enable_ai_summary",
            "enable_ai_insights",
            "enable_ai_interpretation",
            "created_date",
            "modified_date",
            "author",
            "version",
        }
        data = {k: v for k, v in data.items() if k in valid_fields}

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

    @staticmethod
    def get_templates_directory() -> Path:
        """
        Get the directory for storing templates.

        Returns platform-appropriate configuration directory:
        - Windows: %APPDATA%/SiglentReportGenerator/templates
        - macOS: ~/Library/Application Support/SiglentReportGenerator/templates
        - Linux: ~/.config/SiglentReportGenerator/templates

        Returns:
            Path to templates directory
        """
        if platform.system() == "Windows":
            base = Path(os.environ.get("APPDATA", Path.home()))
        elif platform.system() == "Darwin":  # macOS
            base = Path.home() / "Library" / "Application Support"
        else:  # Linux and others
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

        templates_dir = base / "SiglentReportGenerator" / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)
        return templates_dir

    def save_to_library(self) -> None:
        """Save template to user's template library."""
        templates_dir = self.get_templates_directory()
        # Sanitize filename - replace spaces and special chars
        safe_name = self.name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        filename = f"{safe_name}.json"
        self.save(templates_dir / filename)

    @classmethod
    def load_from_library(cls, name: str) -> "ReportTemplate":
        """
        Load template from user's template library.

        Args:
            name: Template name (with or without .json extension)

        Returns:
            ReportTemplate instance
        """
        templates_dir = cls.get_templates_directory()
        # Handle both "Template Name" and "Template_Name.json"
        safe_name = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        if not safe_name.endswith(".json"):
            safe_name = f"{safe_name}.json"
        return cls.load(templates_dir / safe_name)

    @classmethod
    def list_templates(cls) -> List[str]:
        """
        List all available templates in the library.

        Returns:
            List of template names (without .json extension)
        """
        templates_dir = cls.get_templates_directory()
        if not templates_dir.exists():
            return []
        # Return names with underscores replaced by spaces
        return [f.stem.replace("_", " ") for f in templates_dir.glob("*.json")]

    @classmethod
    def delete_from_library(cls, name: str) -> bool:
        """
        Delete template from library.

        Args:
            name: Template name

        Returns:
            True if deleted, False if not found
        """
        templates_dir = cls.get_templates_directory()
        safe_name = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        if not safe_name.endswith(".json"):
            safe_name = f"{safe_name}.json"

        filepath = templates_dir / safe_name
        if filepath.exists():
            filepath.unlink()
            return True
        return False
