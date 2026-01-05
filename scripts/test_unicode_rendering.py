#!/usr/bin/env python3
"""
Test script for Unicode character rendering in PDF reports.

Tests that AI-generated text with special Unicode characters renders properly.
"""

import numpy as np
from pathlib import Path
from datetime import datetime

from siglent.report_generator.models.report_data import (
    TestReport, ReportMetadata, TestSection, WaveformData
)
from siglent.report_generator.generators.pdf_generator import PDFReportGenerator


def generate_test_waveform():
    """Generate a simple test waveform."""
    t = np.linspace(0, 0.01, 1000)
    v = np.sin(2 * np.pi * 1000 * t)
    return t, v


def main():
    """Test Unicode character rendering."""
    print("Unicode Character Rendering Test")
    print("=" * 60)

    # Create metadata
    metadata = ReportMetadata(
        title="Unicode Rendering Test Report",
        technician="Test User",
        test_date=datetime.now(),
        equipment_model="Test Equipment"
    )

    # Create report with AI-generated text containing special characters
    report = TestReport(metadata=metadata)

    # Executive summary with various Unicode characters
    report.executive_summary = """
This test verifies Unicode character rendering in PDF reports:
- Smart quotes: \u201cHello\u201d and \u2018world\u2019
- Em-dash and en-dash: \u2014test\u2014 and \u2013test\u2013
- Bullets: \u2022 Item 1 \u2022 Item 2
- Ellipsis: Testing\u2026
- Mathematical symbols: \u2264 \u2265 \u2260 \u00d7 \u00f7
- Degrees: 25\u00b0C or 77\u00b0F
- Non-breaking spaces and special formatting
"""
    report.ai_generated_summary = True

    # Key findings with Unicode
    report.key_findings = [
        "Signal quality is \u201cexcellent\u201d with minimal noise",
        "Frequency stability: \u00b10.1% \u2013 well within spec",
        "Temperature range: 20\u00b0C to 25\u00b0C",
        "Rise time \u2264 100ns; fall time \u2265 50ns"
    ]

    # Recommendations with Unicode
    report.recommendations = [
        "Continue monitoring\u2026 signal may degrade over time",
        "Use \u00d7 10 probe for better accuracy",
        "Maintain temperature \u2264 30\u00b0C for optimal performance"
    ]

    # Create section with AI insights
    section = TestSection(
        title="Test Results",
        content="This section tests AI-generated text with special characters."
    )

    # AI summary with lots of Unicode
    section.ai_summary = """
The waveform analysis reveals several key characteristics:
\u2022 Frequency: 1.000 kHz (\u00b10.01%)
\u2022 Amplitude: Very stable \u2014 no significant drift
\u2022 Temperature coefficient: \u2264 10 ppm/\u00b0C
\u2022 Signal-to-noise ratio: \u2265 60 dB

The signal quality is \u201cexceptional\u201d\u2026 surpassing expectations.
"""

    # AI insights with Unicode
    section.ai_insights = """
Key observations:
1. The signal shows \u201ctextbook\u201d sine wave characteristics
2. Harmonic distortion is \u2264 0.1% \u2014 excellent performance
3. Phase noise: \u2013140 dBc/Hz @ 10 kHz offset
4. Recommended operating range: \u201320\u00b0C to +85\u00b0C

Note: These results are within \u00b15% of theoretical predictions.
"""

    # Add a test waveform
    t, v = generate_test_waveform()
    waveform = WaveformData(
        channel_name="CH1",
        time_data=t,
        voltage_data=v,
        sample_rate=100000,
        record_length=len(t),
        label="Test Sine Wave"
    )
    waveform.analyze()
    section.waveforms.append(waveform)

    report.add_section(section)

    # Generate PDF
    output_path = Path("test_unicode_rendering.pdf")

    print(f"\nGenerating PDF: {output_path}")
    print("\nTesting Unicode character normalization:")
    print("  - Smart quotes (U+201C, U+201D, U+2018, U+2019)")
    print("  - Dashes (U+2013, U+2014)")
    print("  - Bullets (U+2022)")
    print("  - Ellipsis (U+2026)")
    print("  - Math symbols (U+2264, U+2265, U+2260, U+00D7, U+00F7)")
    print("  - Degrees (U+00B0, U+2103, U+2109)")

    generator = PDFReportGenerator()
    success = generator.generate(report, output_path)

    if success:
        print(f"\n[PASS] PDF generated successfully!")
        print(f"  Output: {output_path}")
        print(f"  Size: {output_path.stat().st_size:,} bytes")

        print("\nVerify in the PDF that:")
        print("  1. Smart quotes appear as regular quotes")
        print("  2. Em-dashes appear as regular hyphens")
        print("  3. Bullets appear as asterisks (*)")
        print("  4. Ellipsis appears as three dots (...)")
        print("  5. Math symbols are converted (U+2264 -> <=, etc.)")
        print("  6. Degree symbols appear as 'deg', 'C', 'F'")
        print("  7. NO empty boxes, question marks, or missing characters")
    else:
        print("\n[FAIL] PDF generation failed")
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
