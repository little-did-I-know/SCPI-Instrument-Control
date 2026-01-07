"""Report generators for various output formats."""

from scpi_control.report_generator.generators.base import BaseReportGenerator
from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator

# PDF generator imported conditionally since reportlab might not be installed
try:
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator

    __all__ = ["BaseReportGenerator", "MarkdownReportGenerator", "PDFReportGenerator"]
except ImportError:
    __all__ = ["BaseReportGenerator", "MarkdownReportGenerator"]
