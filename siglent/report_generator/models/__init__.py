"""Data models for report generation."""

from siglent.report_generator.models.report_data import (
    TestReport,
    TestSection,
    WaveformData,
    MeasurementResult,
    ReportMetadata,
)
from siglent.report_generator.models.template import ReportTemplate
from siglent.report_generator.models.criteria import MeasurementCriteria, CriteriaResult

__all__ = [
    "TestReport",
    "TestSection",
    "WaveformData",
    "MeasurementResult",
    "ReportMetadata",
    "ReportTemplate",
    "MeasurementCriteria",
    "CriteriaResult",
]
