"""
PDF report generator using ReportLab.

Generates professional PDF reports with waveform plots, measurements,
company branding, and AI-generated insights.
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image as RLImage
    from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")  # Use non-interactive backend
import numpy as np
from PIL import Image

from siglent.report_generator.generators.base import BaseReportGenerator
from siglent.report_generator.models.plot_style import PlotStyle
from siglent.report_generator.models.report_data import MeasurementResult, TestReport, TestSection, WaveformData, WaveformRegion
from siglent.report_generator.models.report_options import ReportOptions
from siglent.report_generator.utils.waveform_analyzer import WaveformAnalyzer


class PDFReportGenerator(BaseReportGenerator):
    """Generator for PDF format reports."""

    def __init__(
        self,
        page_size=None,
        include_plots: bool = True,
        plot_width: float = 6.5,
        plot_height: float = 3.0,
        plot_style: PlotStyle = None,
        report_options: ReportOptions = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ):
        """
        Initialize PDF generator.

        Args:
            page_size: Page size (letter, A4, etc.). Defaults to letter size.
            include_plots: Whether to include waveform plots
            plot_width: Plot width in inches
            plot_height: Plot height in inches
            plot_style: Plot style configuration for matplotlib plots
            report_options: Report options for statistics and other settings
            progress_callback: Optional callback function(progress_percent, status_message)
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation. " "Install with: pip install reportlab")

        # Set default page size if not specified
        if page_size is None:
            page_size = letter

        self.page_size = page_size
        self.include_plots = include_plots
        self.plot_width = plot_width * inch
        self.plot_height = plot_height * inch
        self.plot_style = plot_style or PlotStyle()
        self.report_options = report_options or ReportOptions()
        self.progress_callback = progress_callback

        # Set up styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        # Title style
        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Heading1"],
                fontSize=24,
                textColor=colors.HexColor("#1f77b4"),
                spaceAfter=30,
                alignment=TA_CENTER,
            )
        )

        # Section heading
        self.styles.add(
            ParagraphStyle(
                name="SectionHeading",
                parent=self.styles["Heading2"],
                fontSize=16,
                textColor=colors.HexColor("#1f77b4"),
                spaceAfter=12,
                spaceBefore=20,
            )
        )

        # Subsection heading
        self.styles.add(
            ParagraphStyle(
                name="SubsectionHeading",
                parent=self.styles["Heading3"],
                fontSize=14,
                textColor=colors.HexColor("#2ca02c"),
                spaceAfter=10,
                spaceBefore=15,
            )
        )

        # Waveform heading (for individual waveforms)
        # Only add if it doesn't exist
        if "Heading4" not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name="Heading4",
                    parent=self.styles["Heading3"],
                    fontSize=12,
                    textColor=colors.HexColor("#ff7f0e"),
                    spaceAfter=6,
                    spaceBefore=10,
                )
            )

        # Result PASS style
        self.styles.add(
            ParagraphStyle(
                name="ResultPass",
                parent=self.styles["Normal"],
                fontSize=18,
                textColor=colors.HexColor("#2ca02c"),
                alignment=TA_CENTER,
                spaceAfter=20,
            )
        )

        # Result FAIL style
        self.styles.add(
            ParagraphStyle(
                name="ResultFail",
                parent=self.styles["Normal"],
                fontSize=18,
                textColor=colors.HexColor("#d62728"),
                alignment=TA_CENTER,
                spaceAfter=20,
            )
        )

    def get_file_extension(self) -> str:
        """Get file extension."""
        return ".pdf"

    def _report_progress(self, percent: int, message: str = "") -> None:
        """
        Report progress to callback if available, otherwise print to console.

        Args:
            percent: Progress percentage (0-100)
            message: Optional status message
        """
        if self.progress_callback:
            self.progress_callback(percent, message)
        else:
            # Fallback to console output
            if message:
                print(f"Generating PDF... {percent}% - {message}")
            else:
                print(f"Generating PDF... {percent}%")

    def _markdown_to_reportlab(self, text: str) -> str:
        """
        Convert simple markdown to ReportLab XML tags.

        Args:
            text: Markdown text

        Returns:
            Text with ReportLab XML tags
        """
        if not text:
            return ""

        # Normalize unicode characters that might cause rendering issues
        # These are commonly used by LLMs but may not render properly in PDFs

        # Dashes and hyphens
        text = text.replace("\u2013", "-")  # en-dash
        text = text.replace("\u2014", "-")  # em-dash
        text = text.replace("\u2212", "-")  # minus sign
        text = text.replace("\u00ad", "")  # soft hyphen (remove)

        # Quotes
        text = text.replace("\u2018", "'")  # left single quote
        text = text.replace("\u2019", "'")  # right single quote
        text = text.replace("\u201a", "'")  # single low-9 quote
        text = text.replace("\u201c", '"')  # left double quote
        text = text.replace("\u201d", '"')  # right double quote
        text = text.replace("\u201e", '"')  # double low-9 quote

        # Bullets and symbols
        text = text.replace("\u2022", "*")  # bullet
        text = text.replace("\u2023", "*")  # triangular bullet
        text = text.replace("\u2043", "*")  # hyphen bullet
        text = text.replace("\u25e6", "*")  # white bullet
        text = text.replace("\u2219", "*")  # bullet operator

        # Ellipsis
        text = text.replace("\u2026", "...")  # horizontal ellipsis

        # Spaces
        text = text.replace("\u00a0", " ")  # non-breaking space
        text = text.replace("\u2009", " ")  # thin space
        text = text.replace("\u200a", " ")  # hair space

        # Mathematical symbols
        text = text.replace("\u00d7", "x")  # multiplication sign
        text = text.replace("\u00f7", "/")  # division sign
        text = text.replace("\u2264", "<=")  # less than or equal
        text = text.replace("\u2265", ">=")  # greater than or equal
        text = text.replace("\u2260", "!=")  # not equal

        # Degrees and other symbols
        text = text.replace("\u00b0", " deg")  # degree symbol
        text = text.replace("\u2103", " C")  # degree celsius
        text = text.replace("\u2109", " F")  # degree fahrenheit

        # Store markdown patterns before escaping
        # We'll process them in order to avoid conflicts

        # First, protect code blocks (they shouldn't be processed)
        code_blocks = {}

        def save_code(match):
            key = f"__CODE_{len(code_blocks)}__"
            code_blocks[key] = match.group(1)
            return key

        text = re.sub(r"`(.+?)`", save_code, text)

        # Escape XML characters (but not in our saved code blocks)
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")

        # Convert markdown bold (**text** or __text__)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

        # Convert markdown italic (*text* or _text_)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
        text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<i>\1</i>", text)

        # Restore code blocks with proper formatting
        for key, code in code_blocks.items():
            # Escape the code content too
            code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            text = text.replace(key, f'<font face="Courier">{code}</font>')

        # Convert line breaks
        text = text.replace("\n", "<br/>")

        return text

    def generate(self, report: TestReport, output_path: Path) -> bool:
        """
        Generate PDF report.

        Args:
            report: Test report
            output_path: Path to save the report

        Returns:
            True if successful, False otherwise
        """
        if not self.validate_report(report):
            print("Report validation failed")
            return False

        try:
            output_path = Path(output_path)

            self._report_progress(0, "Starting PDF generation")

            # Create PDF document
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=self.page_size,
                rightMargin=0.75 * inch,
                leftMargin=0.75 * inch,
                topMargin=1 * inch,
                bottomMargin=0.75 * inch,
            )

            self._report_progress(5, "Building document structure")

            # Calculate progress steps
            # 5% - setup
            # 10% - header/metadata
            # 15% - overall result/summary
            # 20-80% - sections (divided among sections)
            # 85% - recommendations
            # 90% - building PDF
            # 100% - complete

            # Build content
            story = []
            story.extend(self._generate_header(report))
            self._report_progress(10, "Generated header")

            story.extend(self._generate_metadata_section(report))
            story.extend(self._generate_overall_result(report))
            self._report_progress(12, "Generated metadata")

            # Executive summary
            if report.executive_summary:
                story.extend(self._generate_executive_summary(report))
                self._report_progress(15, "Generated summary")

            # Key findings
            if report.key_findings:
                story.extend(self._generate_key_findings(report))
                self._report_progress(18, "Generated key findings")

            # Sections - track progress through them
            num_sections = len(report.sections)
            if num_sections > 0:
                # Count total waveforms for more granular progress
                total_waveforms = sum(len(s.waveforms) for s in report.sections)
                waveforms_processed = 0

                section_progress_range = 60  # 20% to 80%
                for i, section in enumerate(report.sections):
                    section_percent = 20 + int((i / num_sections) * section_progress_range)
                    self._report_progress(section_percent, f"Processing section {i+1}/{num_sections}")

                    # Pass waveform progress tracking
                    story.extend(
                        self._generate_section(
                            section,
                            section_index=i,
                            waveforms_processed_before=waveforms_processed,
                            total_waveforms=total_waveforms,
                            progress_start=section_percent,
                            progress_range=section_progress_range / num_sections,
                        )
                    )

                    waveforms_processed += len(section.waveforms)

            self._report_progress(82, "Sections complete")

            # Recommendations
            if report.recommendations:
                story.extend(self._generate_recommendations(report))

            # Footer
            story.extend(self._generate_footer(report))

            self._report_progress(88, "Building PDF document")

            # Build PDF
            doc.build(story)

            self._report_progress(100, "PDF generation complete")

            return True

        except Exception as e:
            print(f"Failed to generate PDF report: {e}")
            import traceback

            traceback.print_exc()
            return False

    def _generate_header(self, report: TestReport) -> List:
        """Generate report header."""
        story = []

        # Company logo if available
        if report.metadata.company_logo_path and Path(report.metadata.company_logo_path).exists():
            try:
                logo = RLImage(str(report.metadata.company_logo_path), width=2 * inch, height=1 * inch)
                logo.hAlign = "CENTER"
                story.append(logo)
                story.append(Spacer(1, 0.2 * inch))
            except Exception:
                pass  # Skip logo if it fails to load

        # Company name
        if report.metadata.company_name:
            story.append(Paragraph(report.metadata.company_name, self.styles["Normal"]))
            story.append(Spacer(1, 0.1 * inch))

        # Title
        story.append(Paragraph(report.metadata.title, self.styles["ReportTitle"]))
        story.append(Spacer(1, 0.3 * inch))

        return story

    def _generate_metadata_section(self, report: TestReport) -> List:
        """Generate metadata table."""
        story = []
        meta = report.metadata

        data = [
            ["Technician:", meta.technician],
            ["Test Date:", meta.test_date.strftime("%Y-%m-%d %H:%M:%S")],
        ]

        if meta.equipment_model:
            data.append(["Equipment:", meta.equipment_model])
        if meta.equipment_id:
            data.append(["Equipment ID:", meta.equipment_id])
        if meta.test_procedure:
            data.append(["Test Procedure:", meta.test_procedure])
        if meta.project_name:
            data.append(["Project:", meta.project_name])
        if meta.customer:
            data.append(["Customer:", meta.customer])
        if meta.temperature:
            data.append(["Temperature:", meta.temperature])
        if meta.humidity:
            data.append(["Humidity:", meta.humidity])
        if meta.location:
            data.append(["Location:", meta.location])

        table = Table(data, colWidths=[2 * inch, 4.5 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),  # Left-align labels
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),  # Left-align values
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),  # Top-align vertically
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    # Add grid borders
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        story.append(table)
        story.append(Spacer(1, 0.3 * inch))

        return story

    def _generate_overall_result(self, report: TestReport) -> List:
        """Generate overall result section."""
        story = []

        overall = report.overall_result or report.calculate_overall_result()

        if overall == "PASS":
            style = self.styles["ResultPass"]
            text = f"<b>Overall Result: PASS</b>"
        elif overall == "FAIL":
            style = self.styles["ResultFail"]
            text = f"<b>Overall Result: FAIL</b>"
        else:
            style = self.styles["Normal"]
            text = f"<b>Overall Result: {overall}</b>"

        story.append(Paragraph(text, style))

        # Measurement summary
        measurements = report.get_all_measurements()
        if measurements:
            passed = sum(1 for m in measurements if m.passed is True)
            failed = sum(1 for m in measurements if m.passed is False)

            summary_text = f"Measurements: {len(measurements)} total, {passed} passed, {failed} failed"
            story.append(Paragraph(summary_text, self.styles["Normal"]))
            story.append(Spacer(1, 0.2 * inch))

        return story

    def _generate_executive_summary(self, report: TestReport) -> List:
        """Generate executive summary section."""
        story = []

        story.append(Paragraph("Executive Summary", self.styles["SectionHeading"]))

        # Convert markdown to ReportLab XML
        summary_text = self._markdown_to_reportlab(report.executive_summary)
        story.append(Paragraph(summary_text, self.styles["Normal"]))

        if report.ai_generated_summary:
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph("<i>Summary generated by AI</i>", self.styles["Normal"]))

        story.append(Spacer(1, 0.2 * inch))

        return story

    def _generate_key_findings(self, report: TestReport) -> List:
        """Generate key findings section."""
        story = []

        story.append(Paragraph("Key Findings", self.styles["SectionHeading"]))

        for finding in report.key_findings:
            # Convert markdown to ReportLab XML
            finding_text = self._markdown_to_reportlab(finding)
            story.append(Paragraph(f"• {finding_text}", self.styles["Normal"]))

        story.append(Spacer(1, 0.2 * inch))

        return story

    def _generate_section(
        self,
        section: TestSection,
        section_index: int = 0,
        waveforms_processed_before: int = 0,
        total_waveforms: int = 1,
        progress_start: int = 20,
        progress_range: float = 60,
    ) -> List:
        """Generate a report section with progress tracking."""
        story = []

        story.append(Paragraph(section.title, self.styles["SectionHeading"]))

        if section.content:
            content_text = section.content.replace("\n", "<br/>")
            story.append(Paragraph(content_text, self.styles["Normal"]))
            story.append(Spacer(1, 0.1 * inch))

        # AI insights
        if section.ai_summary:
            story.append(Paragraph("AI Analysis", self.styles["SubsectionHeading"]))
            # Normalize Unicode characters from AI-generated text
            ai_text = self._markdown_to_reportlab(section.ai_summary)
            story.append(Paragraph(ai_text, self.styles["Normal"]))
            story.append(Spacer(1, 0.1 * inch))

        if section.ai_insights:
            story.append(Paragraph("AI Insights", self.styles["SubsectionHeading"]))
            # Normalize Unicode characters from AI-generated text
            insights_text = self._markdown_to_reportlab(section.ai_insights)
            story.append(Paragraph(insights_text, self.styles["Normal"]))
            story.append(Spacer(1, 0.1 * inch))

        # Waveforms
        if section.waveforms:
            story.append(Paragraph("Waveforms", self.styles["SubsectionHeading"]))
            for i, waveform in enumerate(section.waveforms):
                # Calculate progress for this waveform
                waveform_global_index = waveforms_processed_before + i
                if total_waveforms > 0:
                    # Progress within the section range
                    waveform_progress = progress_start + int((waveform_global_index / total_waveforms) * progress_range)
                    self._report_progress(waveform_progress, f"Generating waveform {waveform_global_index + 1}/{total_waveforms}")

                # Generate waveform with title+plot kept together
                waveform_elements = self._generate_waveform(waveform, index=i + 1)
                story.extend(waveform_elements)

        # Measurements
        if section.measurements:
            story.append(Paragraph("Measurements", self.styles["SubsectionHeading"]))
            story.append(self._generate_measurements_table(section.measurements))
            story.append(Spacer(1, 0.1 * inch))

        # FFT
        if section.include_fft and section.fft_frequency is not None:
            story.append(Paragraph("FFT Analysis", self.styles["SubsectionHeading"]))
            fft_img = self._generate_fft_plot(section.fft_frequency, section.fft_magnitude)
            if fft_img:
                story.append(fft_img)
                story.append(Spacer(1, 0.1 * inch))

        # Images
        if section.images:
            story.append(Paragraph("Images", self.styles["SubsectionHeading"]))
            for img_path in section.images:
                if Path(img_path).exists():
                    try:
                        img = RLImage(str(img_path), width=self.plot_width, height=self.plot_height)
                        story.append(img)
                        story.append(Spacer(1, 0.1 * inch))
                    except Exception:
                        pass

        story.append(Spacer(1, 0.2 * inch))

        return story

    def _generate_waveform(self, waveform: WaveformData, index: int = 1) -> List:
        """
        Generate waveform plot and info with title+plot kept together.

        Args:
            waveform: Waveform data
            index: Waveform index number for the title

        Returns:
            List of flowable elements
        """
        story = []

        # Elements to keep together (title + plot)
        keep_together_elements = []

        # Waveform title (e.g., "Waveform 1: CH1")
        waveform_title = f"Waveform {index}: {waveform.label}"
        keep_together_elements.append(Paragraph(waveform_title, self.styles["Heading4"]))
        keep_together_elements.append(Spacer(1, 0.05 * inch))

        # Plot
        if self.include_plots:
            plot_img = self._generate_waveform_plot(waveform)
            if plot_img:
                keep_together_elements.append(plot_img)

        # Use KeepTogether to prevent title and plot from being separated
        if keep_together_elements:
            story.append(KeepTogether(keep_together_elements))

        # Info table (can be on next page if needed)
        v_min = np.min(waveform.voltage_data)
        v_max = np.max(waveform.voltage_data)
        v_pp = v_max - v_min

        data = [
            ["Channel:", waveform.label],
            ["Sample Rate:", f"{waveform.sample_rate / 1e6:.2f} MS/s"],
            ["Record Length:", f"{waveform.record_length} samples"],
            ["Peak-to-Peak:", f"{v_pp:.4f} V"],
            ["Min:", f"{v_min:.4f} V"],
            ["Max:", f"{v_max:.4f} V"],
        ]

        if waveform.timebase:
            data.insert(2, ["Timebase:", f"{waveform.timebase * 1e6:.2f} µs/div"])

        table = Table(data, colWidths=[1.5 * inch, 3 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        story.append(table)
        story.append(Spacer(1, 0.1 * inch))

        # Statistics table (can split across pages if needed)
        stats_table = self._generate_statistics_table(waveform)
        if stats_table:
            story.append(stats_table)
            story.append(Spacer(1, 0.15 * inch))

        # Generate region subsections if present
        if waveform.regions:
            region_elements = self._generate_regions(waveform)
            story.extend(region_elements)

        return story

    def _generate_regions(self, waveform: WaveformData) -> List:
        """
        Generate detailed subsections for each region of interest.

        Creates separate subsections with zoomed plots, analysis metrics,
        and calibration guidance for each detected region.

        Args:
            waveform: WaveformData with regions to generate

        Returns:
            List of flowable elements for all regions
        """
        story = []

        # Add header for regions section
        story.append(Paragraph("Detailed Region Analysis", self.styles["Heading4"]))
        story.append(Spacer(1, 0.1 * inch))

        for i, region in enumerate(waveform.regions, 1):
            region_elements = self._generate_single_region(waveform, region, i)
            story.extend(region_elements)

        return story

    def _generate_single_region(self, waveform: WaveformData, region: "WaveformRegion", index: int) -> List:
        """
        Generate a single region subsection with plot and analysis.

        Args:
            waveform: Parent waveform
            region: Region to generate
            index: Region index number

        Returns:
            List of flowable elements for this region
        """
        from reportlab.lib import colors

        story = []

        # Region title (keep with plot)
        keep_elements = []

        # Format region title with auto-detect indicator
        auto_indicator = " (Auto-detected)" if region.auto_detected else ""
        region_title = f"Region {index}: {region.label}{auto_indicator}"
        keep_elements.append(Paragraph(region_title, self.styles["Heading5"]))

        if region.description:
            desc_text = self._markdown_to_reportlab(region.description)
            keep_elements.append(Paragraph(desc_text, self.styles["BodyText"]))

        keep_elements.append(Spacer(1, 0.05 * inch))

        # Generate zoomed region plot
        if self.include_plots:
            region_plot = self._generate_region_plot(waveform, region)
            if region_plot:
                keep_elements.append(region_plot)

        # Keep title and plot together
        if keep_elements:
            story.append(KeepTogether(keep_elements))

        story.append(Spacer(1, 0.1 * inch))

        # Region analysis table
        analysis_data = [["Analysis", "Value"]]

        # Time range
        duration_ms = (region.end_time - region.start_time) * 1e3
        analysis_data.append(["Time Range:", f"{region.start_time*1e3:.3f}ms to {region.end_time*1e3:.3f}ms ({duration_ms:.3f}ms)"])

        # Region type
        if region.region_type:
            type_label = region.region_type.replace("_", " ").title()
            analysis_data.append(["Region Type:", type_label])

        # Slope
        if region.slope is not None:
            slope_formatted = f"{region.slope:.0f} V/s"
            analysis_data.append(["Slope:", slope_formatted])

        # Flatness
        if region.flatness is not None:
            flatness_formatted = f"{region.flatness*1e3:.2f} mV"
            analysis_data.append(["Flatness (σ):", flatness_formatted])

        # Noise level
        if region.noise_level is not None:
            noise_formatted = f"{region.noise_level*1e3:.2f} mV RMS"
            analysis_data.append(["Noise Level:", noise_formatted])

        # Drift
        if region.drift is not None:
            drift_formatted = f"{region.drift*1e3:.2f} mV"
            analysis_data.append(["Total Drift:", drift_formatted])

        # Ideal value comparison
        if region.ideal_value is not None:
            ideal_formatted = f"{region.ideal_value:.4f} V"
            analysis_data.append(["Ideal Value:", ideal_formatted])

            if region.deviation_from_ideal is not None:
                dev_formatted = f"{region.deviation_from_ideal*1e3:.2f} mV"
                analysis_data.append(["Deviation:", dev_formatted])

        # Pass/fail status
        if region.passes_spec is not None:
            status = "✓ PASS" if region.passes_spec else "✗ FAIL"
            analysis_data.append(["Spec Check:", status])

        # Create analysis table
        analysis_table = Table(analysis_data, colWidths=[1.5 * inch, 3.5 * inch])
        analysis_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f4f8")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )

        story.append(analysis_table)
        story.append(Spacer(1, 0.1 * inch))

        # Calibration recommendation (highlighted box)
        if region.calibration_recommendation:
            # Normalize Unicode characters
            recommendation_text = self._markdown_to_reportlab(region.calibration_recommendation)

            # Determine box color based on severity
            if "✓" in region.calibration_recommendation or "good" in region.calibration_recommendation.lower():
                box_color = colors.HexColor("#d4edda")  # Light green
            elif "⚠⚠⚠" in region.calibration_recommendation or "severe" in region.calibration_recommendation.lower():
                box_color = colors.HexColor("#f8d7da")  # Light red
            elif "⚠" in region.calibration_recommendation:
                box_color = colors.HexColor("#fff3cd")  # Light yellow
            else:
                box_color = colors.HexColor("#e8f4f8")  # Light blue

            recommendation_para = Paragraph(f"<b>Calibration Guidance:</b> {recommendation_text}", self.styles["BodyText"])

            # Create a table for the colored box
            rec_table = Table([[recommendation_para]], colWidths=[5 * inch])
            rec_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, 0), box_color),
                        ("BOX", (0, 0), (0, 0), 1, colors.grey),
                        ("LEFTPADDING", (0, 0), (0, 0), 10),
                        ("RIGHTPADDING", (0, 0), (0, 0), 10),
                        ("TOPPADDING", (0, 0), (0, 0), 8),
                        ("BOTTOMPADDING", (0, 0), (0, 0), 8),
                    ]
                )
            )

            story.append(rec_table)
            story.append(Spacer(1, 0.1 * inch))

        # AI insights (if available)
        if region.ai_insights:
            story.append(Paragraph("<b>AI Analysis:</b>", self.styles["Heading6"]))
            insights_text = self._markdown_to_reportlab(region.ai_insights)
            story.append(Paragraph(insights_text, self.styles["BodyText"]))
            story.append(Spacer(1, 0.1 * inch))

        # Separator between regions
        story.append(Spacer(1, 0.15 * inch))

        return story

    def _generate_region_plot(self, waveform: WaveformData, region: "WaveformRegion") -> Optional[RLImage]:
        """
        Generate a zoomed plot for a specific region.

        Args:
            waveform: Parent waveform
            region: Region to plot

        Returns:
            ReportLab Image object, or None if generation fails
        """
        try:
            from io import BytesIO

            import matplotlib.pyplot as plt

            # Extract region data
            t, v = waveform.get_region_data(region)

            if len(t) == 0:
                return None

            # Apply plot style
            if self.plot_style.matplotlib_style != "default":
                plt.style.use(self.plot_style.matplotlib_style)

            fig, ax = plt.subplots(figsize=(6, 3))

            # Plot the region
            ax.plot(t * 1e3, v, color=region.highlight_color or self.plot_style.waveform_color, linewidth=self.plot_style.waveform_linewidth)

            # Add reference line for ideal value
            if region.ideal_value is not None:
                ax.axhline(y=region.ideal_value, color="red", linestyle="--", linewidth=1, label=f"Ideal: {region.ideal_value:.4f}V", alpha=0.6)
                ax.legend(fontsize=8)

            # Apply style to axes
            self.plot_style.apply_to_axes(ax)

            # Labels
            ax.set_xlabel("Time (ms)", fontsize=self.plot_style.label_fontsize)
            ax.set_ylabel("Voltage (V)", fontsize=self.plot_style.label_fontsize)
            ax.set_title(f"{region.label} - Zoomed View", fontsize=self.plot_style.title_fontsize)

            ax.grid(True, alpha=0.3)

            plt.tight_layout()

            # Convert to image
            buf = BytesIO()
            plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)

            # Create ReportLab image
            img = RLImage(buf, width=5 * inch, height=2.5 * inch)
            return img

        except Exception as e:
            print(f"Error generating region plot: {e}")
            return None

    def _generate_statistics_table(self, waveform: WaveformData) -> Optional[Table]:
        """
        Generate statistics table for a waveform.

        Args:
            waveform: Waveform data to analyze

        Returns:
            Table with calculated statistics, or None if disabled
        """
        if not self.report_options.include_statistics_table:
            return None

        # Calculate all statistics using WaveformAnalyzer
        stats = WaveformAnalyzer.analyze(waveform, include_plateau_stability=self.report_options.include_plateau_stability)

        # Build table data based on enabled categories
        data = [["Statistic", "Value"]]  # Header

        # Signal Type (always show if detected)
        if stats.get("signal_type"):
            signal_type_str = WaveformAnalyzer.format_stat_value("signal_type", stats["signal_type"])
            if stats.get("signal_type_confidence"):
                confidence_str = WaveformAnalyzer.format_stat_value("signal_type_confidence", stats["signal_type_confidence"])
                signal_type_str = f"{signal_type_str} ({confidence_str})"
            data.append(["Signal Type:", signal_type_str])

        # Frequency and Period
        if self.report_options.include_frequency_stats:
            if stats.get("frequency") is not None:
                data.append(["Frequency:", WaveformAnalyzer.format_stat_value("frequency", stats["frequency"])])
            if stats.get("period") is not None:
                data.append(["Period:", WaveformAnalyzer.format_stat_value("period", stats["period"])])

        # Amplitude Measurements
        if self.report_options.include_amplitude_stats:
            if stats.get("vmax") is not None:
                data.append(["Vmax:", WaveformAnalyzer.format_stat_value("vmax", stats["vmax"])])
            if stats.get("vmin") is not None:
                data.append(["Vmin:", WaveformAnalyzer.format_stat_value("vmin", stats["vmin"])])
            if stats.get("vpp") is not None:
                data.append(["Vpp:", WaveformAnalyzer.format_stat_value("vpp", stats["vpp"])])
            if stats.get("vmean") is not None:
                data.append(["Vmean:", WaveformAnalyzer.format_stat_value("vmean", stats["vmean"])])
            if stats.get("vrms") is not None:
                data.append(["Vrms:", WaveformAnalyzer.format_stat_value("vrms", stats["vrms"])])
            if stats.get("vamp") is not None:
                data.append(["Vamp:", WaveformAnalyzer.format_stat_value("vamp", stats["vamp"])])
            if stats.get("dc_offset") is not None:
                data.append(["DC Offset:", WaveformAnalyzer.format_stat_value("dc_offset", stats["dc_offset"])])

        # Timing Measurements
        if self.report_options.include_timing_stats:
            if stats.get("rise_time") is not None:
                data.append(["Rise Time:", WaveformAnalyzer.format_stat_value("rise_time", stats["rise_time"])])
            if stats.get("fall_time") is not None:
                data.append(["Fall Time:", WaveformAnalyzer.format_stat_value("fall_time", stats["fall_time"])])
            if stats.get("pulse_width") is not None:
                data.append(["Pulse Width:", WaveformAnalyzer.format_stat_value("pulse_width", stats["pulse_width"])])
            if stats.get("duty_cycle") is not None:
                data.append(["Duty Cycle:", WaveformAnalyzer.format_stat_value("duty_cycle", stats["duty_cycle"])])

        # Signal Quality Metrics
        if self.report_options.include_quality_stats:
            if stats.get("noise_level") is not None:
                data.append(["Noise Level:", WaveformAnalyzer.format_stat_value("noise_level", stats["noise_level"])])
            if stats.get("snr") is not None:
                data.append(["SNR:", WaveformAnalyzer.format_stat_value("snr", stats["snr"])])
            if stats.get("thd") is not None:
                data.append(["THD:", WaveformAnalyzer.format_stat_value("thd", stats["thd"])])
            if stats.get("overshoot") is not None:
                data.append(["Overshoot:", WaveformAnalyzer.format_stat_value("overshoot", stats["overshoot"])])
            if stats.get("undershoot") is not None:
                data.append(["Undershoot:", WaveformAnalyzer.format_stat_value("undershoot", stats["undershoot"])])
            if stats.get("jitter") is not None:
                data.append(["Jitter:", WaveformAnalyzer.format_stat_value("jitter", stats["jitter"])])

        # Plateau Stability (if enabled and calculated)
        if self.report_options.include_plateau_stability:
            if stats.get("plateau_stability") is not None:
                data.append(["Plateau Stability:", WaveformAnalyzer.format_stat_value("plateau_stability", stats["plateau_stability"])])
            if stats.get("plateau_high_noise") is not None:
                data.append(["High Plateau Noise:", WaveformAnalyzer.format_stat_value("plateau_high_noise", stats["plateau_high_noise"])])
            if stats.get("plateau_low_noise") is not None:
                data.append(["Low Plateau Noise:", WaveformAnalyzer.format_stat_value("plateau_low_noise", stats["plateau_low_noise"])])

        # If only header row exists, don't create table
        if len(data) <= 1:
            return None

        # Create table with styling
        table = Table(data, colWidths=[2 * inch, 2 * inch])
        table.setStyle(
            TableStyle(
                [
                    # Header styling
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2ca02c")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    # Data rows styling
                    ("ALIGN", (0, 1), (0, -1), "LEFT"),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                    ("TOPPADDING", (0, 1), (-1, -1), 4),
                    ("LEFTPADDING", (0, 1), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 1), (-1, -1), 8),
                    # Borders
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BOX", (0, 0), (-1, -1), 1, colors.black),
                    # Alternating row colors
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]
            )
        )

        return table

    def _generate_measurements_table(self, measurements: List[MeasurementResult]) -> Table:
        """Generate measurements table."""
        data = [["Measurement", "Value", "Status", "Criteria"]]

        for meas in measurements:
            name = meas.name
            if meas.channel:
                name += f" ({meas.channel})"

            value = meas.format_value()

            if meas.passed is True:
                status = "PASS"
            elif meas.passed is False:
                status = "FAIL"
            else:
                status = "N/A"

            criteria_parts = []
            if meas.criteria_min is not None:
                criteria_parts.append(f"min: {meas.criteria_min:.6g}")
            if meas.criteria_max is not None:
                criteria_parts.append(f"max: {meas.criteria_max:.6g}")
            criteria = "\n".join(criteria_parts) if criteria_parts else "N/A"

            data.append([name, value, status, criteria])

        table = Table(data, colWidths=[2 * inch, 1.5 * inch, 1 * inch, 2 * inch])

        # Style
        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f77b4")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ]

        # Color code pass/fail rows
        for i, meas in enumerate(measurements, start=1):
            if meas.passed is True:
                style_commands.append(("TEXTCOLOR", (2, i), (2, i), colors.HexColor("#2ca02c")))
            elif meas.passed is False:
                style_commands.append(("TEXTCOLOR", (2, i), (2, i), colors.HexColor("#d62728")))

        table.setStyle(TableStyle(style_commands))

        return table

    def _generate_waveform_plot(self, waveform: WaveformData) -> Optional[RLImage]:
        """Generate waveform plot as image with custom style."""
        try:
            # Apply matplotlib style preset
            if self.plot_style.matplotlib_style != "default":
                plt.style.use(self.plot_style.matplotlib_style)

            fig, ax = plt.subplots(figsize=(self.plot_width / inch, self.plot_height / inch))

            # Use plot style colors and settings
            ax.plot(waveform.time_data * 1e6, waveform.voltage_data, color=waveform.color or self.plot_style.waveform_color, linewidth=self.plot_style.waveform_linewidth)

            # Apply style to axes
            self.plot_style.apply_to_axes(ax)

            # Set labels with custom font sizes
            ax.set_xlabel("Time (µs)", fontsize=self.plot_style.label_fontsize)
            ax.set_ylabel("Voltage (V)", fontsize=self.plot_style.label_fontsize)
            ax.set_title(waveform.label, fontsize=self.plot_style.title_fontsize, fontweight="bold")

            plt.tight_layout()

            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)

            # Create ReportLab image
            img = RLImage(buf, width=self.plot_width, height=self.plot_height)
            return img

        except Exception as e:
            print(f"Failed to generate waveform plot: {e}")
            return None

    def _generate_fft_plot(self, frequency: np.ndarray, magnitude: np.ndarray) -> Optional[RLImage]:
        """Generate FFT plot as image with custom style."""
        try:
            # Apply matplotlib style preset
            if self.plot_style.matplotlib_style != "default":
                plt.style.use(self.plot_style.matplotlib_style)

            fig, ax = plt.subplots(figsize=(self.plot_width / inch, self.plot_height / inch))

            # Use plot style colors and settings
            ax.plot(frequency / 1e6, magnitude, color=self.plot_style.fft_color, linewidth=self.plot_style.waveform_linewidth)

            # Apply style to axes
            self.plot_style.apply_to_axes(ax)

            # Set labels with custom font sizes
            ax.set_xlabel("Frequency (MHz)", fontsize=self.plot_style.label_fontsize)
            ax.set_ylabel("Magnitude (dB)", fontsize=self.plot_style.label_fontsize)
            ax.set_title("FFT Analysis", fontsize=self.plot_style.title_fontsize, fontweight="bold")

            plt.tight_layout()

            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)

            # Create ReportLab image
            img = RLImage(buf, width=self.plot_width, height=self.plot_height)
            return img

        except Exception as e:
            print(f"Failed to generate FFT plot: {e}")
            return None

    def _generate_recommendations(self, report: TestReport) -> List:
        """Generate recommendations section."""
        story = []

        story.append(Paragraph("Recommendations", self.styles["SectionHeading"]))

        for i, rec in enumerate(report.recommendations, 1):
            # Convert markdown to ReportLab XML
            rec_text = self._markdown_to_reportlab(rec)
            story.append(Paragraph(f"{i}. {rec_text}", self.styles["Normal"]))

        story.append(Spacer(1, 0.2 * inch))

        return story

    def _generate_footer(self, report: TestReport) -> List:
        """Generate report footer."""
        story = []

        story.append(Spacer(1, 0.3 * inch))

        footer_text = f"Report generated on {report.metadata.test_date.strftime('%Y-%m-%d at %H:%M:%S')}"
        if report.metadata.company_name:
            footer_text += f" by {report.metadata.company_name}"

        story.append(Paragraph(footer_text, self.styles["Normal"]))

        return story
