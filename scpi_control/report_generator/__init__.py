"""
Siglent Report Generator

A standalone application for generating professional test reports from
oscilloscope waveform data with optional AI-powered analysis.
"""

from scpi_control.report_generator.models.criteria import CriteriaResult, MeasurementCriteria
from scpi_control.report_generator.models.report_data import MeasurementResult, ReportMetadata, TestReport, TestSection, WaveformData
from scpi_control.report_generator.models.template import ReportTemplate

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
