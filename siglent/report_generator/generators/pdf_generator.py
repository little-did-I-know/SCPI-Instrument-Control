"""
PDF report generator using ReportLab.

Generates professional PDF reports with waveform plots, measurements,
company branding, and AI-generated insights.
"""

from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime
import io

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
        Image as RLImage,
        KeepTogether,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import numpy as np
from PIL import Image

from siglent.report_generator.generators.base import BaseReportGenerator
from siglent.report_generator.models.report_data import (
    TestReport,
    TestSection,
    MeasurementResult,
    WaveformData,
)


class PDFReportGenerator(BaseReportGenerator):
    """Generator for PDF format reports."""

    def __init__(
        self,
        page_size=None,
        include_plots: bool = True,
        plot_width: float = 6.5,
        plot_height: float = 3.0,
    ):
        """
        Initialize PDF generator.

        Args:
            page_size: Page size (letter, A4, etc.). Defaults to letter size.
            include_plots: Whether to include waveform plots
            plot_width: Plot width in inches
            plot_height: Plot height in inches
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "reportlab is required for PDF generation. "
                "Install with: pip install reportlab"
            )

        # Set default page size if not specified
        if page_size is None:
            page_size = letter

        self.page_size = page_size
        self.include_plots = include_plots
        self.plot_width = plot_width * inch
        self.plot_height = plot_height * inch

        # Set up styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f77b4'),
            spaceAfter=30,
            alignment=TA_CENTER,
        ))

        # Section heading
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1f77b4'),
            spaceAfter=12,
            spaceBefore=20,
        ))

        # Subsection heading
        self.styles.add(ParagraphStyle(
            name='SubsectionHeading',
            parent=self.styles['Heading3'],
            fontSize=14,
            textColor=colors.HexColor('#2ca02c'),
            spaceAfter=10,
            spaceBefore=15,
        ))

        # Result PASS style
        self.styles.add(ParagraphStyle(
            name='ResultPass',
            parent=self.styles['Normal'],
            fontSize=18,
            textColor=colors.HexColor('#2ca02c'),
            alignment=TA_CENTER,
            spaceAfter=20,
        ))

        # Result FAIL style
        self.styles.add(ParagraphStyle(
            name='ResultFail',
            parent=self.styles['Normal'],
            fontSize=18,
            textColor=colors.HexColor('#d62728'),
            alignment=TA_CENTER,
            spaceAfter=20,
        ))

    def get_file_extension(self) -> str:
        """Get file extension."""
        return ".pdf"

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

            # Create PDF document
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=self.page_size,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=1*inch,
                bottomMargin=0.75*inch,
            )

            # Build content
            story = []
            story.extend(self._generate_header(report))
            story.extend(self._generate_metadata_section(report))
            story.extend(self._generate_overall_result(report))

            # Executive summary
            if report.executive_summary:
                story.extend(self._generate_executive_summary(report))

            # Key findings
            if report.key_findings:
                story.extend(self._generate_key_findings(report))

            # Sections
            for section in report.sections:
                story.extend(self._generate_section(section))

            # Recommendations
            if report.recommendations:
                story.extend(self._generate_recommendations(report))

            # Footer
            story.extend(self._generate_footer(report))

            # Build PDF
            doc.build(story)

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
                logo = RLImage(str(report.metadata.company_logo_path), width=2*inch, height=1*inch)
                logo.hAlign = 'CENTER'
                story.append(logo)
                story.append(Spacer(1, 0.2*inch))
            except Exception:
                pass  # Skip logo if it fails to load

        # Company name
        if report.metadata.company_name:
            story.append(Paragraph(report.metadata.company_name, self.styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

        # Title
        story.append(Paragraph(report.metadata.title, self.styles['ReportTitle']))
        story.append(Spacer(1, 0.3*inch))

        return story

    def _generate_metadata_section(self, report: TestReport) -> List:
        """Generate metadata table."""
        story = []
        meta = report.metadata

        data = [
            ['Technician:', meta.technician],
            ['Test Date:', meta.test_date.strftime('%Y-%m-%d %H:%M:%S')],
        ]

        if meta.equipment_model:
            data.append(['Equipment:', meta.equipment_model])
        if meta.equipment_id:
            data.append(['Equipment ID:', meta.equipment_id])
        if meta.test_procedure:
            data.append(['Test Procedure:', meta.test_procedure])
        if meta.project_name:
            data.append(['Project:', meta.project_name])
        if meta.customer:
            data.append(['Customer:', meta.customer])
        if meta.temperature:
            data.append(['Temperature:', meta.temperature])
        if meta.humidity:
            data.append(['Humidity:', meta.humidity])
        if meta.location:
            data.append(['Location:', meta.location])

        table = Table(data, colWidths=[2*inch, 4.5*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.3*inch))

        return story

    def _generate_overall_result(self, report: TestReport) -> List:
        """Generate overall result section."""
        story = []

        overall = report.overall_result or report.calculate_overall_result()

        if overall == "PASS":
            style = self.styles['ResultPass']
            text = f"<b>Overall Result: PASS</b>"
        elif overall == "FAIL":
            style = self.styles['ResultFail']
            text = f"<b>Overall Result: FAIL</b>"
        else:
            style = self.styles['Normal']
            text = f"<b>Overall Result: {overall}</b>"

        story.append(Paragraph(text, style))

        # Measurement summary
        measurements = report.get_all_measurements()
        if measurements:
            passed = sum(1 for m in measurements if m.passed is True)
            failed = sum(1 for m in measurements if m.passed is False)

            summary_text = f"Measurements: {len(measurements)} total, {passed} passed, {failed} failed"
            story.append(Paragraph(summary_text, self.styles['Normal']))
            story.append(Spacer(1, 0.2*inch))

        return story

    def _generate_executive_summary(self, report: TestReport) -> List:
        """Generate executive summary section."""
        story = []

        story.append(Paragraph("Executive Summary", self.styles['SectionHeading']))

        summary_text = report.executive_summary.replace('\n', '<br/>')
        story.append(Paragraph(summary_text, self.styles['Normal']))

        if report.ai_generated_summary:
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph("<i>Summary generated by AI</i>", self.styles['Normal']))

        story.append(Spacer(1, 0.2*inch))

        return story

    def _generate_key_findings(self, report: TestReport) -> List:
        """Generate key findings section."""
        story = []

        story.append(Paragraph("Key Findings", self.styles['SectionHeading']))

        for finding in report.key_findings:
            story.append(Paragraph(f"• {finding}", self.styles['Normal']))

        story.append(Spacer(1, 0.2*inch))

        return story

    def _generate_section(self, section: TestSection) -> List:
        """Generate a report section."""
        story = []

        story.append(Paragraph(section.title, self.styles['SectionHeading']))

        if section.content:
            content_text = section.content.replace('\n', '<br/>')
            story.append(Paragraph(content_text, self.styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

        # AI insights
        if section.ai_summary:
            story.append(Paragraph("AI Analysis", self.styles['SubsectionHeading']))
            ai_text = section.ai_summary.replace('\n', '<br/>')
            story.append(Paragraph(ai_text, self.styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

        if section.ai_insights:
            story.append(Paragraph("AI Insights", self.styles['SubsectionHeading']))
            insights_text = section.ai_insights.replace('\n', '<br/>')
            story.append(Paragraph(insights_text, self.styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

        # Waveforms
        if section.waveforms:
            story.append(Paragraph("Waveforms", self.styles['SubsectionHeading']))
            for waveform in section.waveforms:
                story.extend(self._generate_waveform(waveform))

        # Measurements
        if section.measurements:
            story.append(Paragraph("Measurements", self.styles['SubsectionHeading']))
            story.append(self._generate_measurements_table(section.measurements))
            story.append(Spacer(1, 0.1*inch))

        # FFT
        if section.include_fft and section.fft_frequency is not None:
            story.append(Paragraph("FFT Analysis", self.styles['SubsectionHeading']))
            fft_img = self._generate_fft_plot(section.fft_frequency, section.fft_magnitude)
            if fft_img:
                story.append(fft_img)
                story.append(Spacer(1, 0.1*inch))

        # Images
        if section.images:
            story.append(Paragraph("Images", self.styles['SubsectionHeading']))
            for img_path in section.images:
                if Path(img_path).exists():
                    try:
                        img = RLImage(str(img_path), width=self.plot_width, height=self.plot_height)
                        story.append(img)
                        story.append(Spacer(1, 0.1*inch))
                    except Exception:
                        pass

        story.append(Spacer(1, 0.2*inch))

        return story

    def _generate_waveform(self, waveform: WaveformData) -> List:
        """Generate waveform plot and info."""
        story = []

        # Plot
        if self.include_plots:
            plot_img = self._generate_waveform_plot(waveform)
            if plot_img:
                story.append(plot_img)

        # Info table
        v_min = np.min(waveform.voltage_data)
        v_max = np.max(waveform.voltage_data)
        v_pp = v_max - v_min

        data = [
            ['Channel:', waveform.label],
            ['Sample Rate:', f"{waveform.sample_rate / 1e6:.2f} MS/s"],
            ['Record Length:', f"{waveform.record_length} samples"],
            ['Peak-to-Peak:', f"{v_pp:.4f} V"],
            ['Min:', f"{v_min:.4f} V"],
            ['Max:', f"{v_max:.4f} V"],
        ]

        if waveform.timebase:
            data.insert(2, ['Timebase:', f"{waveform.timebase * 1e6:.2f} µs/div"])

        table = Table(data, colWidths=[1.5*inch, 3*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.15*inch))

        return story

    def _generate_measurements_table(self, measurements: List[MeasurementResult]) -> Table:
        """Generate measurements table."""
        data = [['Measurement', 'Value', 'Status', 'Criteria']]

        for meas in measurements:
            name = meas.name
            if meas.channel:
                name += f" ({meas.channel})"

            value = meas.format_value()

            if meas.passed is True:
                status = 'PASS'
            elif meas.passed is False:
                status = 'FAIL'
            else:
                status = 'N/A'

            criteria_parts = []
            if meas.criteria_min is not None:
                criteria_parts.append(f"min: {meas.criteria_min:.6g}")
            if meas.criteria_max is not None:
                criteria_parts.append(f"max: {meas.criteria_max:.6g}")
            criteria = '\n'.join(criteria_parts) if criteria_parts else 'N/A'

            data.append([name, value, status, criteria])

        table = Table(data, colWidths=[2*inch, 1.5*inch, 1*inch, 2*inch])

        # Style
        style_commands = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ]

        # Color code pass/fail rows
        for i, meas in enumerate(measurements, start=1):
            if meas.passed is True:
                style_commands.append(('TEXTCOLOR', (2, i), (2, i), colors.HexColor('#2ca02c')))
            elif meas.passed is False:
                style_commands.append(('TEXTCOLOR', (2, i), (2, i), colors.HexColor('#d62728')))

        table.setStyle(TableStyle(style_commands))

        return table

    def _generate_waveform_plot(self, waveform: WaveformData) -> Optional[RLImage]:
        """Generate waveform plot as image."""
        try:
            fig, ax = plt.subplots(figsize=(self.plot_width/inch, self.plot_height/inch))
            ax.plot(waveform.time_data * 1e6, waveform.voltage_data,
                   color=waveform.color or "#1f77b4", linewidth=0.8)
            ax.set_xlabel("Time (µs)", fontsize=10)
            ax.set_ylabel("Voltage (V)", fontsize=10)
            ax.set_title(waveform.label, fontsize=11, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.tick_params(labelsize=9)

            plt.tight_layout()

            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)

            # Create ReportLab image
            img = RLImage(buf, width=self.plot_width, height=self.plot_height)
            return img

        except Exception as e:
            print(f"Failed to generate waveform plot: {e}")
            return None

    def _generate_fft_plot(self, frequency: np.ndarray, magnitude: np.ndarray) -> Optional[RLImage]:
        """Generate FFT plot as image."""
        try:
            fig, ax = plt.subplots(figsize=(self.plot_width/inch, self.plot_height/inch))
            ax.plot(frequency / 1e6, magnitude, color="#ff7f0e", linewidth=0.8)
            ax.set_xlabel("Frequency (MHz)", fontsize=10)
            ax.set_ylabel("Magnitude (dB)", fontsize=10)
            ax.set_title("FFT Analysis", fontsize=11, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.tick_params(labelsize=9)

            plt.tight_layout()

            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
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

        story.append(Paragraph("Recommendations", self.styles['SectionHeading']))

        for i, rec in enumerate(report.recommendations, 1):
            story.append(Paragraph(f"{i}. {rec}", self.styles['Normal']))

        story.append(Spacer(1, 0.2*inch))

        return story

    def _generate_footer(self, report: TestReport) -> List:
        """Generate report footer."""
        story = []

        story.append(Spacer(1, 0.3*inch))

        footer_text = f"Report generated on {report.metadata.test_date.strftime('%Y-%m-%d at %H:%M:%S')}"
        if report.metadata.company_name:
            footer_text += f" by {report.metadata.company_name}"

        story.append(Paragraph(footer_text, self.styles['Normal']))

        return story
