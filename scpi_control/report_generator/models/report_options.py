"""
Report options for runtime customization.

Allows users to customize report generation on a per-report basis
without saving as a template.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class ReportOptions:
    """Runtime options for report generation (not saved in templates)."""

    # Section inclusion
    include_executive_summary: bool = True
    include_key_findings: bool = True
    include_recommendations: bool = True
    include_waveform_plots: bool = True
    include_fft_analysis: bool = True
    include_ai_insights: bool = False

    # AI generation options
    auto_generate_summary: bool = False
    auto_generate_findings: bool = False
    auto_generate_recommendations: bool = False

    # Output format options
    page_size: str = "letter"  # "letter", "a4"
    plot_width_inches: float = 6.5
    plot_height_inches: float = 3.0
    plot_dpi: int = 150

    # Statistics table options
    include_statistics_table: bool = True
    include_frequency_stats: bool = True
    include_amplitude_stats: bool = True
    include_timing_stats: bool = True
    include_quality_stats: bool = True
    include_plateau_stability: bool = False  # Advanced: plateau noise analysis for periodic signals

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation of report options
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportOptions":
        """
        Create from dictionary.

        Args:
            data: Dictionary with report options

        Returns:
            ReportOptions instance
        """
        return cls(**data)
