#!/usr/bin/env python3
"""
Test script for PDF generation with progress tracking.

This script tests the progress callback functionality and KeepTogether
page layout features.
"""

import numpy as np
from pathlib import Path
from datetime import datetime

from siglent.report_generator.models.report_data import (
    TestReport, ReportMetadata, TestSection, WaveformData
)
from siglent.report_generator.generators.pdf_generator import PDFReportGenerator
from siglent.report_generator.models.report_options import ReportOptions


def generate_test_waveform(freq=1000, sample_rate=100000, duration=0.01, amplitude=1.0):
    """Generate a test sine wave."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    v = amplitude * np.sin(2 * np.pi * freq * t)
    return t, v


def generate_square_wave(freq=1000, sample_rate=100000, duration=0.01, amplitude=1.0, noise_level=0.0):
    """Generate a square wave with optional noise."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    v = amplitude * np.sign(np.sin(2 * np.pi * freq * t))
    if noise_level > 0:
        v += np.random.normal(0, noise_level, len(v))
    return t, v


def create_test_report():
    """Create a test report with multiple waveforms."""
    # Create metadata
    metadata = ReportMetadata(
        title="PDF Progress Test Report",
        technician="Test User",
        test_date=datetime.now(),
        equipment_model="Test Equipment"
    )

    # Create report
    report = TestReport(metadata=metadata)

    # Add a section with sine waves
    section = TestSection(
        title="Sine Wave Signals",
        content="This section contains sine waves to test signal type detection."
    )

    # Add several sine waveforms
    for i in range(3):
        t, v = generate_test_waveform(freq=1000 * (i + 1))
        waveform = WaveformData(
            channel_name=f"CH{i+1}",
            time_data=t,
            voltage_data=v,
            sample_rate=100000,
            record_length=len(t),
            label=f"Sine Wave {i+1}"
        )
        # Analyze waveform to populate statistics and signal type
        # Note: include_plateau_stability will be set by report options
        waveform.analyze()
        section.waveforms.append(waveform)

    report.add_section(section)

    # Add section with square waves for plateau stability testing
    section2 = TestSection(
        title="Square Wave Signals (Plateau Stability Test)",
        content="This section contains square waves with varying noise levels to test plateau stability analysis."
    )

    # Clean square wave
    t, v = generate_square_wave(freq=1000, amplitude=2.0, noise_level=0.0)
    waveform = WaveformData(
        channel_name="CH4",
        time_data=t,
        voltage_data=v,
        sample_rate=100000,
        record_length=len(t),
        label="Clean Square Wave"
    )
    waveform.analyze()
    section2.waveforms.append(waveform)

    # Noisy square wave (low noise)
    t, v = generate_square_wave(freq=1000, amplitude=2.0, noise_level=0.05)
    waveform = WaveformData(
        channel_name="CH5",
        time_data=t,
        voltage_data=v,
        sample_rate=100000,
        record_length=len(t),
        label="Square Wave (Low Noise)"
    )
    waveform.analyze()
    section2.waveforms.append(waveform)

    # Noisy square wave (high noise)
    t, v = generate_square_wave(freq=1000, amplitude=2.0, noise_level=0.1)
    waveform = WaveformData(
        channel_name="CH6",
        time_data=t,
        voltage_data=v,
        sample_rate=100000,
        record_length=len(t),
        label="Square Wave (High Noise)"
    )
    waveform.analyze()
    section2.waveforms.append(waveform)

    report.add_section(section2)

    return report


def main():
    """Run the test."""
    print("PDF Progress & Plateau Stability Test")
    print("=" * 60)

    # Create test report
    print("\nCreating test report with 6 waveforms...")
    print("  - 3 sine waves")
    print("  - 3 square waves (clean, low noise, high noise)")
    report = create_test_report()

    # Create output path
    output_path = Path("test_report_progress.pdf")

    print(f"\nOutput path: {output_path}")
    print("\nGenerating PDF with plateau stability enabled...")
    print("-" * 60)

    # Create PDF generator with progress callback
    def progress_callback(percent: int, message: str):
        """Simple console progress callback."""
        bar_length = 40
        filled = int(bar_length * percent / 100)
        bar = '=' * filled + '-' * (bar_length - filled)
        print(f"\r[{bar}] {percent:3d}% - {message:<40}", end='', flush=True)

    # Enable plateau stability analysis
    options = ReportOptions()
    options.include_plateau_stability = True

    generator = PDFReportGenerator(
        progress_callback=progress_callback,
        report_options=options
    )

    success = generator.generate(report, output_path)

    print()  # New line after progress bar
    print("-" * 60)

    if success:
        print(f"\n[PASS] PDF generated successfully!")
        print(f"  Output: {output_path}")
        print(f"  Size: {output_path.stat().st_size:,} bytes")

        print("\nFeatures tested:")
        print("  - Progress callback with percentage updates")
        print("  - Console output for programmatic usage")
        print("  - KeepTogether for waveform titles and plots")
        print("  - Signal type detection in statistics tables")
        print("  - Plateau stability analysis for periodic signals")

        print(f"\nOpen the PDF to verify:")
        print(f"  1. Progress bar shows smooth updates (not freezing)")
        print(f"  2. Waveform titles stay with their plots (no separation)")
        print(f"  3. Signal types are correctly detected:")
        print(f"     - Sine waves detected as 'sine'")
        print(f"     - Square waves detected as 'square'")
        print(f"  4. Plateau stability metrics appear for square waves:")
        print(f"     - Plateau Stability (average noise)")
        print(f"     - High Plateau Noise")
        print(f"     - Low Plateau Noise")
        print(f"  5. Noise levels increase: Clean < Low Noise < High Noise")
    else:
        print("\n[FAIL] PDF generation failed")
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
