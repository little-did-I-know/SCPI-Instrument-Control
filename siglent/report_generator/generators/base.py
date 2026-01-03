"""Base class for report generators."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from siglent.report_generator.models.report_data import TestReport


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
            True if successful, False otherwise
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
