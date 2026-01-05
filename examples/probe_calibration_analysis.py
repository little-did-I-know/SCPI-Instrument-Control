#!/usr/bin/env python3
"""
Probe Calibration Analysis Example

Demonstrates the new waveform region extraction features for analyzing
probe compensation using oscilloscope calibration signals.

This example shows:
1. Automatic plateau detection in square waves
2. Plateau slope analysis for probe compensation assessment
3. Calibration guidance generation
4. Zoomed region plots in PDF reports
5. Manual region addition and analysis

For best results, capture a 1kHz square wave from your oscilloscope's
probe compensation output with different probe compensation settings:
- Properly compensated (flat plateaus)
- Undercompensated (rising plateaus)
- Overcompensated (falling plateaus)
"""

from datetime import datetime
from pathlib import Path

import numpy as np

from siglent.report_generator.generators.markdown_generator import MarkdownReportGenerator
from siglent.report_generator.generators.pdf_generator import PDFReportGenerator
from siglent.report_generator.models.report_data import ReportMetadata, TestReport, TestSection, WaveformData
from siglent.report_generator.utils.waveform_analyzer import WaveformAnalyzer


def generate_test_square_wave(slope: float = 0, noise: float = 0.01):
    """
    Generate a test square wave with configurable plateau slope.

    Args:
        slope: Plateau slope in V/s (positive=rising, negative=falling, 0=flat)
        noise: Noise level to add (RMS voltage)

    Returns:
        Tuple of (time_data, voltage_data)
    """
    # 1kHz square wave, 10ms duration, 100kS/s
    sample_rate = 100000
    duration = 0.01
    freq = 1000

    t = np.linspace(0, duration, int(sample_rate * duration))

    # Generate base square wave
    v = np.sign(np.sin(2 * np.pi * freq * t))

    # Add slope to plateaus
    if slope != 0:
        # Find high and low plateau regions
        high_regions = v > 0.5
        low_regions = v < -0.5

        # Add linear trend to each plateau
        for i in range(len(v) - 1):
            if high_regions[i]:
                # Rising edge at start of plateau
                if i == 0 or not high_regions[i - 1]:
                    plateau_start_time = t[i]
                # Add slope
                v[i] += slope * (t[i] - plateau_start_time)
            elif low_regions[i]:
                # Falling edge at start of plateau
                if i == 0 or not low_regions[i - 1]:
                    plateau_start_time = t[i]
                # Add slope
                v[i] += slope * (t[i] - plateau_start_time)

    # Add noise
    if noise > 0:
        v += np.random.normal(0, noise, len(v))

    return t, v


def main():
    """Run the probe calibration analysis example."""
    print("=" * 70)
    print("Probe Calibration Analysis - Region Extraction Demo")
    print("=" * 70)

    # Create metadata
    metadata = ReportMetadata(
        title="Oscilloscope Probe Calibration Test",
        technician="Test Engineer",
        test_date=datetime.now(),
        equipment_model="SDS2104X Plus",
        test_procedure="PROC-001: 10X Probe Compensation Verification",
        notes="Testing probe compensation using 1kHz calibration signal",
    )

    # Create report
    report = TestReport(metadata=metadata)

    # Executive summary
    report.executive_summary = """
This report analyzes oscilloscope probe compensation using the built-in 1kHz
calibration signal. Proper probe compensation is critical for accurate measurements.

The analysis examines plateau slope and flatness to determine if the probe's
trimmer capacitor requires adjustment.
"""

    # ========================================================================
    # Test Case 1: Properly Compensated Probe
    # ========================================================================
    print("\n1. Generating properly compensated probe test...")
    section1 = TestSection(title="Test 1: Properly Compensated Probe", content="This test shows a properly compensated 10X probe with flat plateaus.")

    # Generate test waveform (flat plateaus, minimal slope)
    t1, v1 = generate_test_square_wave(slope=0, noise=0.005)

    waveform1 = WaveformData(channel_name="CH1", time_data=t1, voltage_data=v1, sample_rate=100000, record_length=len(t1), label="Properly Compensated Probe", probe_ratio=10)

    # Analyze the waveform (detects signal type)
    print("   - Analyzing waveform...")
    waveform1.analyze()
    print(f"   - Detected signal type: {waveform1.signal_type}")

    # Automatically detect and analyze regions
    print("   - Detecting plateau regions...")
    WaveformAnalyzer.detect_regions(waveform1, auto_detect_plateaus=True, auto_detect_edges=False)
    print(f"   - Found {len(waveform1.regions)} regions")

    # Analyze all detected regions
    print("   - Analyzing regions...")
    WaveformAnalyzer.analyze_all_regions(waveform1)

    # Print region analysis results
    for i, region in enumerate(waveform1.regions, 1):
        print(f"     Region {i}: {region.label}")
        print(f"       - Slope: {region.slope:.0f} V/s")
        print(f"       - Flatness: {region.flatness*1e3:.2f} mV")
        if region.calibration_recommendation:
            print(f"       - {region.calibration_recommendation}")

    section1.waveforms.append(waveform1)
    report.add_section(section1)

    # ========================================================================
    # Test Case 2: Undercompensated Probe
    # ========================================================================
    print("\n2. Generating undercompensated probe test...")
    section2 = TestSection(title="Test 2: Undercompensated Probe", content="This test shows an undercompensated probe with rising plateaus.")

    # Generate test waveform (positive slope = undercompensated)
    t2, v2 = generate_test_square_wave(slope=15000, noise=0.008)

    waveform2 = WaveformData(channel_name="CH2", time_data=t2, voltage_data=v2, sample_rate=100000, record_length=len(t2), label="Undercompensated Probe", probe_ratio=10)

    waveform2.analyze()
    WaveformAnalyzer.detect_regions(waveform2, auto_detect_plateaus=True, auto_detect_edges=False)
    WaveformAnalyzer.analyze_all_regions(waveform2)

    for i, region in enumerate(waveform2.regions, 1):
        print(f"     Region {i}: {region.label}")
        print(f"       - Slope: {region.slope:.0f} V/s")
        if region.calibration_recommendation:
            print(f"       - {region.calibration_recommendation}")

    section2.waveforms.append(waveform2)
    report.add_section(section2)

    # ========================================================================
    # Test Case 3: Overcompensated Probe
    # ========================================================================
    print("\n3. Generating overcompensated probe test...")
    section3 = TestSection(title="Test 3: Overcompensated Probe", content="This test shows an overcompensated probe with falling plateaus.")

    # Generate test waveform (negative slope = overcompensated)
    t3, v3 = generate_test_square_wave(slope=-18000, noise=0.006)

    waveform3 = WaveformData(channel_name="CH3", time_data=t3, voltage_data=v3, sample_rate=100000, record_length=len(t3), label="Overcompensated Probe", probe_ratio=10)

    waveform3.analyze()
    WaveformAnalyzer.detect_regions(waveform3, auto_detect_plateaus=True, auto_detect_edges=False)
    WaveformAnalyzer.analyze_all_regions(waveform3)

    for i, region in enumerate(waveform3.regions, 1):
        print(f"     Region {i}: {region.label}")
        print(f"       - Slope: {region.slope:.0f} V/s")
        if region.calibration_recommendation:
            print(f"       - {region.calibration_recommendation}")

    section3.waveforms.append(waveform3)
    report.add_section(section3)

    # ========================================================================
    # Test Case 4: Manual Region Addition
    # ========================================================================
    print("\n4. Demonstrating manual region addition...")
    section4 = TestSection(title="Test 4: Manual Region Definition", content="This example shows how to manually add custom regions of interest.")

    # Generate another test waveform
    t4, v4 = generate_test_square_wave(slope=5000, noise=0.01)

    waveform4 = WaveformData(channel_name="CH4", time_data=t4, voltage_data=v4, sample_rate=100000, record_length=len(t4), label="Manual Region Example")

    waveform4.analyze()

    # Manually add a custom region (e.g., focusing on first high plateau)
    custom_region = waveform4.add_region(
        start_time=0.0005,  # 0.5ms
        end_time=0.0010,  # 1.0ms
        label="Custom Analysis Region",
        description="Manually defined region for detailed investigation",
        region_type="custom",
        ideal_value=1.0,
        tolerance_min=0.95,
        tolerance_max=1.05,
    )

    # Analyze the custom region
    WaveformAnalyzer.analyze_region(waveform4, custom_region)

    print(f"     Custom region: {custom_region.label}")
    print(f"       - Time range: {custom_region.start_time*1e3:.3f}ms to {custom_region.end_time*1e3:.3f}ms")
    print(f"       - Slope: {custom_region.slope:.0f} V/s")
    print(f"       - Passes spec: {custom_region.passes_spec}")

    section4.waveforms.append(waveform4)
    report.add_section(section4)

    # Add key findings
    report.key_findings = [
        "Test 1 (Properly Compensated): Flat plateaus with minimal slope - probe calibration is good",
        "Test 2 (Undercompensated): Rising plateaus indicate trimmer capacitor needs clockwise adjustment",
        "Test 3 (Overcompensated): Falling plateaus indicate trimmer capacitor needs counter-clockwise adjustment",
        "Region extraction enables detailed analysis of specific waveform sections",
        "Automatic calibration guidance provides actionable recommendations",
    ]

    # Add recommendations
    report.recommendations = [
        "Always verify probe compensation before critical measurements",
        "Use the 1kHz calibration signal output on your oscilloscope",
        "Adjust trimmer capacitor in small increments (10-15°) and retest",
        "Document probe compensation status in test reports",
        "Recheck compensation when changing measurement setup or environment",
    ]

    # ========================================================================
    # Generate Reports
    # ========================================================================
    print("\n" + "=" * 70)
    print("Generating Reports...")
    print("=" * 70)

    # Generate PDF
    pdf_path = Path("probe_calibration_analysis.pdf")
    print(f"\nGenerating PDF: {pdf_path}")
    pdf_generator = PDFReportGenerator()
    pdf_success = pdf_generator.generate(report, pdf_path)

    if pdf_success:
        print(f"  ✓ PDF generated successfully ({pdf_path.stat().st_size:,} bytes)")
    else:
        print(f"  ✗ PDF generation failed")

    # Generate Markdown
    md_path = Path("probe_calibration_analysis.md")
    print(f"\nGenerating Markdown: {md_path}")
    md_generator = MarkdownReportGenerator(include_plots=True, plots_dir="plots")
    md_success = md_generator.generate(report, md_path)

    if md_success:
        print(f"  ✓ Markdown generated successfully ({md_path.stat().st_size:,} bytes)")
    else:
        print(f"  ✗ Markdown generation failed")

    # ========================================================================
    # Summary
    # ========================================================================
    print("\n" + "=" * 70)
    print("Feature Demonstration Summary")
    print("=" * 70)
    print("\n✓ Features Demonstrated:")
    print("  1. Automatic plateau detection in square waves")
    print("  2. Plateau slope analysis for probe compensation")
    print("  3. Automatic calibration guidance generation")
    print("  4. Zoomed region plots in reports")
    print("  5. Manual region definition and analysis")
    print("  6. Region-specific statistics and measurements")
    print("  7. Color-coded calibration recommendations")
    print("  8. Both PDF and Markdown report generation")

    print("\n✓ Report Contents:")
    print(f"  - {len(report.sections)} test sections")
    total_waveforms = sum(len(s.waveforms) for s in report.sections)
    total_regions = sum(len(w.regions) for w in [wf for s in report.sections for wf in s.waveforms])
    print(f"  - {total_waveforms} waveforms analyzed")
    print(f"  - {total_regions} regions detected and analyzed")
    print(f"  - {len(report.key_findings)} key findings")
    print(f"  - {len(report.recommendations)} recommendations")

    print("\n✓ Files Generated:")
    if pdf_success:
        print(f"  - {pdf_path}")
    if md_success:
        print(f"  - {md_path}")
        print(f"  - plots/ (region zoomed plots)")

    print("\n" + "=" * 70)
    print("Review the generated PDF to see:")
    print("  • Full waveform plots")
    print("  • Automatic plateau detection")
    print("  • Zoomed region subsections")
    print("  • Slope analysis tables")
    print("  • Color-coded calibration guidance")
    print("  • Detailed region-specific measurements")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
