"""
Example: Generating Professional Test Reports

This example demonstrates how to use the Report Generator to create
professional PDF and Markdown reports from oscilloscope data.

Features demonstrated:
- Loading waveform data from files
- Creating report metadata
- Adding measurements with pass/fail criteria
- Using AI for report analysis (optional)
- Generating PDF and Markdown reports
"""

from datetime import datetime
from pathlib import Path

import numpy as np

from siglent.report_generator.generators.markdown_generator import MarkdownReportGenerator
from siglent.report_generator.models.criteria import ComparisonType, CriteriaSet, MeasurementCriteria
from siglent.report_generator.models.report_data import MeasurementResult, ReportMetadata, TestReport, TestSection, WaveformData

# Import PDF generator if available
try:
    from siglent.report_generator.generators.pdf_generator import PDFReportGenerator

    PDF_AVAILABLE = True
except ImportError:
    print("Warning: reportlab not installed - PDF generation will be skipped")
    PDF_AVAILABLE = False

from siglent.report_generator.llm.analyzer import ReportAnalyzer

# Import LLM components if you want AI features
from siglent.report_generator.llm.client import LLMClient, LLMConfig


def create_sample_waveform() -> WaveformData:
    """Create a sample waveform for demonstration."""
    # Generate a simple sine wave with some noise
    sample_rate = 1e9  # 1 GS/s
    duration = 1e-3  # 1 ms
    frequency = 1e3  # 1 kHz

    num_samples = int(sample_rate * duration)
    time_data = np.linspace(0, duration, num_samples)

    # Generate sine wave with noise
    voltage_data = 2.0 * np.sin(2 * np.pi * frequency * time_data)
    voltage_data += 0.1 * np.random.randn(num_samples)  # Add noise

    return WaveformData(
        channel_name="CH1",
        time_data=time_data,
        voltage_data=voltage_data,
        sample_rate=sample_rate,
        record_length=num_samples,
        timebase=100e-6,  # 100 μs/div
        voltage_scale=1.0,  # 1 V/div
        probe_ratio=1.0,
        coupling="DC",
        label="Power Supply Output",
    )


def create_sample_measurements() -> list[MeasurementResult]:
    """Create sample measurements with pass/fail status."""
    measurements = [
        MeasurementResult(
            name="Frequency",
            value=1.002e3,  # 1.002 kHz (slightly off)
            unit="Hz",
            channel="CH1",
            passed=True,
            criteria_min=990,
            criteria_max=1010,
        ),
        MeasurementResult(
            name="Peak-to-Peak",
            value=3.98,
            unit="V",
            channel="CH1",
            passed=True,
            criteria_min=3.8,
            criteria_max=4.2,
        ),
        MeasurementResult(
            name="RMS",
            value=1.42,
            unit="V",
            channel="CH1",
            passed=True,
            criteria_min=1.35,
            criteria_max=1.50,
        ),
        MeasurementResult(
            name="Rise Time",
            value=125e-9,
            unit="s",
            channel="CH1",
            passed=False,  # This one failed!
            criteria_max=100e-9,
        ),
    ]

    return measurements


def create_criteria_set() -> CriteriaSet:
    """Create a set of pass/fail criteria."""
    criteria_set = CriteriaSet(
        name="Power Supply Output Test",
        description="Criteria for 1kHz, 4Vpp sine wave output",
    )

    # Frequency must be within ±1%
    criteria_set.add_criteria(
        MeasurementCriteria(
            measurement_name="Frequency",
            comparison_type=ComparisonType.RANGE,
            min_value=990,
            max_value=1010,
            channel="CH1",
            description="Output frequency within ±1%",
            severity="critical",
        )
    )

    # Vpp must be 4V ± 0.2V
    criteria_set.add_criteria(
        MeasurementCriteria(
            measurement_name="Peak-to-Peak",
            comparison_type=ComparisonType.RANGE,
            min_value=3.8,
            max_value=4.2,
            channel="CH1",
            description="Peak-to-peak voltage within spec",
            severity="critical",
        )
    )

    # Rise time must be < 100ns
    criteria_set.add_criteria(
        MeasurementCriteria(
            measurement_name="Rise Time",
            comparison_type=ComparisonType.MAX_ONLY,
            max_value=100e-9,
            channel="CH1",
            description="Rise time must be fast",
            severity="warning",
        )
    )

    return criteria_set


def create_report_with_ai(report: TestReport) -> TestReport:
    """
    Add AI-generated content to the report.

    This requires Ollama or LM Studio to be running locally.
    """
    try:
        # Configure Ollama (default settings)
        llm_config = LLMConfig.create_ollama_config(model="llama3.2")

        # Create client and analyzer
        llm_client = LLMClient(llm_config)
        analyzer = ReportAnalyzer(llm_client)

        print("Testing LLM connection...")
        if not llm_client.test_connection():
            print("Warning: Could not connect to LLM. Skipping AI features.")
            print("To enable AI features, install and run Ollama: https://ollama.com")
            return report

        print("Generating AI-powered executive summary...")
        report.executive_summary = analyzer.generate_executive_summary(report)
        report.ai_generated_summary = True

        print("Generating AI key findings...")
        report.key_findings = analyzer.generate_key_findings(report, max_findings=3) or []

        print("Generating AI recommendations...")
        suggestions = analyzer.suggest_next_steps(report)
        if suggestions:
            # Parse suggestions into list
            report.recommendations = [line.strip() for line in suggestions.split("\n") if line.strip() and (line.strip()[0].isdigit() or line.strip().startswith("-"))]

        # Add AI insights to sections
        for section in report.sections:
            if section.measurements:
                print(f"Analyzing section: {section.title}...")
                section.ai_insights = analyzer.interpret_measurements(report)

        print("AI analysis complete!")

    except Exception as e:
        print(f"Warning: AI features failed: {e}")
        print("Continuing without AI features...")

    return report


def main():
    """Main example function."""
    print("=" * 60)
    print("Siglent Report Generator - Example Script")
    print("=" * 60)
    print()

    # Step 1: Create report metadata
    print("Step 1: Creating report metadata...")
    metadata = ReportMetadata(
        title="Power Supply Ripple and Noise Test",
        technician="John Engineer",
        test_date=datetime.now(),
        equipment_model="SDS2104X Plus",
        equipment_id="SN12345678",
        test_procedure="TEST-PS-001 Rev 2.1",
        project_name="DC Power Supply Validation",
        customer="Acme Electronics",
        temperature="23°C",
        humidity="45% RH",
        location="Test Lab 3",
        notes="Testing 5V output under 1A load. Some rise time issues observed.",
        company_name="Example Test Laboratory",
    )

    # Step 2: Create sample data
    print("Step 2: Generating sample waveform data...")
    waveform = create_sample_waveform()
    measurements = create_sample_measurements()

    # Step 3: Build the report
    print("Step 3: Building test report...")
    report = TestReport(metadata=metadata)

    # Add test setup section
    setup_section = TestSection(
        title="Test Setup",
        content=(
            "The device under test (DUT) was configured for 5V output with a 1A resistive load. "
            "Channel 1 of the oscilloscope was connected to the output using a 1:1 probe. "
            "The oscilloscope was set to 100 µs/div timebase with 1 V/div vertical scale."
        ),
        order=1,
    )
    report.add_section(setup_section)

    # Add waveform section
    waveform_section = TestSection(
        title="Waveform Captures",
        content="Captured waveform showing the 1 kHz test signal output.",
        waveforms=[waveform],
        measurements=measurements,
        order=2,
    )
    report.add_section(waveform_section)

    # Add measurement results section
    measurement_section = TestSection(
        title="Measurement Results",
        content="Automated measurements with pass/fail criteria.",
        measurements=measurements,
        order=3,
    )
    report.add_section(measurement_section)

    # Calculate overall result
    report.overall_result = report.calculate_overall_result()

    # Step 4: Add AI analysis (optional)
    print()
    print("Step 4: AI Analysis (optional)...")
    print("Note: This requires Ollama or LM Studio running locally.")

    # Check if running interactively
    enable_ai = False
    try:
        import sys

        # Try to get input with a timeout by checking stdin
        if sys.stdin.isatty() and hasattr(sys.stdin, "read"):
            user_input = input("Enable AI features? (y/n): ").strip().lower()
            enable_ai = user_input == "y"
    except (EOFError, OSError):
        # Not interactive or stdin not available
        print("Running in non-interactive mode - skipping AI features.")
        print("To enable AI, run the script interactively in a terminal.")
        enable_ai = False

    if enable_ai:
        report = create_report_with_ai(report)
    else:
        print("Skipping AI features.")

    # Step 5: Generate reports
    print()
    print("Step 5: Generating reports...")

    # Create output directory
    output_dir = Path("example_reports")
    output_dir.mkdir(exist_ok=True)

    # Generate Markdown report
    print("  - Generating Markdown report...")
    md_path = output_dir / "example_report.md"
    md_generator = MarkdownReportGenerator(include_plots=True)

    if md_generator.generate(report, md_path):
        print(f"    [OK] Markdown report saved: {md_path}")
    else:
        print(f"    [FAILED] Failed to generate Markdown report")

    # Generate PDF report (if available)
    if PDF_AVAILABLE:
        print("  - Generating PDF report...")
        pdf_path = output_dir / "example_report.pdf"
        pdf_generator = PDFReportGenerator()

        if pdf_generator.generate(report, pdf_path):
            print(f"    [OK] PDF report saved: {pdf_path}")
        else:
            print(f"    [FAILED] Failed to generate PDF report")
    else:
        print("  - PDF generation skipped (reportlab not installed)")

    # Done!
    print()
    print("=" * 60)
    print("Example complete!")
    print(f"Reports saved to: {output_dir.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
