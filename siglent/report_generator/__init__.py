"""
Siglent Report Generator

A standalone application for generating professional test reports from
oscilloscope waveform data with optional AI-powered analysis.
"""

from siglent.report_generator.models.criteria import CriteriaResult, MeasurementCriteria
from siglent.report_generator.models.report_data import MeasurementResult, ReportMetadata, TestReport, TestSection, WaveformData
from siglent.report_generator.models.template import ReportTemplate

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

__version__ = "0.1.0"
