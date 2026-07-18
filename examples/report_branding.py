"""Apply company branding to a generated report.

Builds a synthetic report, applies a BrandingTemplate (company name, header and
footer text, and a brand colour scheme), then renders a branded Markdown report
plus a colour-branded PDF. Text (company/header/footer) rides on the report
metadata; the brand colours reach the PDF via PDFReportGenerator(branding=...).

Requirements: SCPI-Instrument-Control[report-generator] (no hardware). The PDF
step is skipped with a message if reportlab is not installed.
"""

from datetime import datetime
from pathlib import Path

import numpy as np

from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.models.report_data import MeasurementResult, ReportMetadata, TestReport, TestSection, WaveformData
from scpi_control.report_generator.models.template import BrandingTemplate

try:
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


def build_report() -> TestReport:
    sample_rate = 1e6
    t = np.arange(2000) / sample_rate
    v = 3.3 * np.sin(2 * np.pi * 1000 * t)
    waveform = WaveformData(channel="C1", time=t, voltage=v, sample_rate=sample_rate, record_length=t.size, label="Output")
    measurement = MeasurementResult(name="Peak-to-Peak", value=6.6, unit="V", channel="C1", passed=True, criteria_min=6.0, criteria_max=7.0)
    report = TestReport(
        metadata=ReportMetadata(title="Branded Report Demo", technician="Lab Tech", test_date=datetime.now()),
        sections=[TestSection(title="Captures", waveforms=[waveform], measurements=[measurement], order=1)],
    )
    report.overall_result = report.calculate_overall_result()
    return report


def main():
    print("=" * 60)
    print("Report branding demo")
    print("=" * 60)

    report = build_report()

    # Text (company/header/footer) goes onto the metadata; colours go to the PDF.
    branding = BrandingTemplate(
        company_name="Acme Test Labs",
        header_text="Acme Test Labs - Confidential",
        footer_text="(c) 2026 Acme Test Labs",
        primary_color="#0b5394",
        secondary_color="#674ea7",
        success_color="#38761d",
        failure_color="#cc0000",
    )
    # To add a logo, set company_logo_path=Path("logo.png") on the branding above.
    branding.apply_to_metadata(report.metadata)

    output_dir = Path("branded_reports")
    output_dir.mkdir(exist_ok=True)

    print("Rendering branded Markdown...")
    md_path = output_dir / "branded_report.md"
    if MarkdownReportGenerator(include_plots=False).generate(report, md_path):
        print(f"  [OK] {md_path}")

    print("Rendering colour-branded PDF...")
    try:
        pdf_path = output_dir / "branded_report.pdf"
        if PDFReportGenerator(branding=branding, include_plots=False).generate(report, pdf_path):
            print(f"  [OK] {pdf_path}")
    except ImportError:
        print("  PDF skipped (reportlab not installed).")

    print("=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
