"""Base class for report generators."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from scpi_control.report_generator.models.report_data import TestReport


class BaseReportGenerator(ABC):
    """Abstract base class for report generators."""

    @abstractmethod
    def generate(self, report: TestReport, output_path: Path) -> bool:
        """
        Generate a report and save to file.

        Args:
            report: Test report to generate
            output_path: Path to save the generated report

        Returns:
            True if the report was written successfully. False means the
            report could not be written for an environmental reason -- an I/O
            failure such as permission denied, disk full, or a bad output
            path (anything an implementation catches as OSError). A
            programming error (AttributeError, TypeError, KeyError, etc.) is
            not reported as False: implementations let it propagate, so a
            defect in report rendering is never indistinguishable from an
            I/O failure.
        """
        pass

    @abstractmethod
    def get_file_extension(self) -> str:
        """
        Get the file extension for this report format.

        Returns:
            File extension (e.g., '.pdf', '.md')
        """
        pass

    def validate_report(self, report: TestReport) -> bool:
        """
        Validate that a report has minimum required content.

        Args:
            report: Report to validate

        Returns:
            True if valid, False otherwise
        """
        if not report.metadata:
            return False

        if not report.metadata.title:
            return False

        return True
