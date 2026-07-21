# Advanced Examples

Advanced examples demonstrating signal analysis, FFT processing, and specialized features like vector graphics for XY mode display.

## Quick Reference

| Example | Description |
|---------|-------------|
| [Advanced waveform analysis and visualization](#advanced-waveform-analysis-and-visualization) | Advanced waveform analysis and visualization. |
| [Probe Calibration Analysis Example](#probe-calibration-analysis-example) | Probe Calibration Analysis Example |
| [Test the power supply GUI with a mock connection](#test-the-power-supply-gui-with-a-mock-connection) | Test the power supply GUI with a mock connection. |
| [Ask a local LLM questions about a report, using tool-calling](#ask-a-local-llm-questions-about-a-report-using-tool-calling) | Ask a local LLM questions about a report, using tool-calling. |
| [Apply company branding to a generated report](#apply-company-branding-to-a-generated-report) | Apply company branding to a generated report. |
| [Deterministic (LLM-free) report analysis](#deterministic-llm-free-report-analysis) | Deterministic (LLM-free) report analysis. |
| [Example: Generating Professional Test Reports](#example-generating-professional-test-reports) | Example: Generating Professional Test Reports |
| [Vector Graphics on Oscilloscope using XY Mode](#vector-graphics-on-oscilloscope-using-xy-mode) | Vector Graphics on Oscilloscope using XY Mode |

---

## Advanced waveform analysis and visualization

Advanced waveform analysis and visualization.

### Requirements

- matplotlib - For plotting
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/advanced_analysis.py
```

### Source Code

```python
"""Advanced waveform analysis and visualization.

This example demonstrates how to perform advanced analysis on captured
waveforms, including FFT analysis, statistical analysis, and visualization
using matplotlib.

Requirements: an oscilloscope reachable on the network -- edit SCOPE_IP below
to match its LAN address. matplotlib is a core dependency, no extra install
needed.

Expected output: basic and signal-quality stats printed to the console,
three plot windows (time domain, FFT, histogram), and 'analyzed_waveform.npz'
plus 'analysis_report.txt' saved to the current directory.
"""

import matplotlib.pyplot as plt
import numpy as np

from scpi_control.automation import DataCollector

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def plot_waveform(waveform, channel_num, title="Waveform"):
    """Plot time-domain waveform."""
    time = np.arange(len(waveform.voltage)) * (1.0 / waveform.sample_rate)
    time_ms = time * 1000  # Convert to milliseconds

    plt.figure(figsize=(12, 4))
    plt.plot(time_ms, waveform.voltage, linewidth=1)
    plt.xlabel("Time (ms)")
    plt.ylabel("Voltage (V)")
    plt.title(f"{title} - Channel {channel_num}")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()


def plot_fft(waveform, channel_num):
    """Plot frequency spectrum using FFT."""
    # Perform FFT
    fft_result = np.fft.fft(waveform.voltage)
    fft_freq = np.fft.fftfreq(len(waveform.voltage), 1.0 / waveform.sample_rate)

    # Take only positive frequencies
    positive_freq_idx = fft_freq > 0
    freqs = fft_freq[positive_freq_idx]
    magnitude = np.abs(fft_result[positive_freq_idx])

    # Convert to dB
    magnitude_db = 20 * np.log10(magnitude + 1e-12)

    plt.figure(figsize=(12, 4))
    plt.plot(freqs / 1e3, magnitude_db, linewidth=1)
    plt.xlabel("Frequency (kHz)")
    plt.ylabel("Magnitude (dB)")
    plt.title(f"FFT Spectrum - Channel {channel_num}")
    plt.grid(True, alpha=0.3)
    plt.xlim(0, freqs.max() / 1e3)
    plt.tight_layout()


def analyze_signal_quality(waveform):
    """Analyze signal quality metrics."""
    voltage = waveform.voltage

    # Basic statistics
    mean_val = np.mean(voltage)
    std_val = np.std(voltage)
    rms_val = np.sqrt(np.mean(voltage**2))

    # Signal-to-noise ratio (simplified)
    # Assume signal is the AC component and noise is variation around it
    ac_component = voltage - mean_val
    signal_power = np.mean(ac_component**2)

    # Estimate noise as high-frequency component
    # (This is a simple approximation)
    filtered = np.convolve(voltage, np.ones(10) / 10, mode="same")
    noise = voltage - filtered
    noise_power = np.mean(noise**2)

    snr_db = 10 * np.log10(signal_power / (noise_power + 1e-12))

    # Total Harmonic Distortion (THD) estimation
    fft_result = np.fft.fft(voltage)
    fft_magnitude = np.abs(fft_result)

    # Find fundamental frequency (largest peak)
    fundamental_idx = np.argmax(fft_magnitude[1 : len(fft_magnitude) // 2]) + 1
    fundamental_power = fft_magnitude[fundamental_idx] ** 2

    # Sum harmonics (2f, 3f, 4f, 5f)
    harmonic_power = 0
    for n in range(2, 6):
        harmonic_idx = fundamental_idx * n
        if harmonic_idx < len(fft_magnitude):
            harmonic_power += fft_magnitude[harmonic_idx] ** 2

    thd = np.sqrt(harmonic_power / (fundamental_power + 1e-12)) * 100

    return {
        "mean": mean_val,
        "std_dev": std_val,
        "rms": rms_val,
        "snr_db": snr_db,
        "thd_percent": thd,
    }


def main():
    with DataCollector(SCOPE_IP) as collector:
        print(f"Connected to {collector.scope.identify()}\n")

        # Capture waveform
        print("Capturing waveform from channel 1...")
        waveforms = collector.capture_single([1])

        if 1 not in waveforms:
            print("Error: Channel 1 not available")
            return

        waveform = waveforms[1]
        print(f"Captured {len(waveform.voltage)} samples")

        # Basic analysis
        print("\n" + "=" * 60)
        print("BASIC ANALYSIS")
        print("=" * 60)
        basic_stats = collector.analyze_waveform(waveform)
        print(f"Vpp:        {basic_stats['vpp']:.4f} V")
        print(f"Amplitude:  {basic_stats['amplitude']:.4f} V")
        print(f"Mean:       {basic_stats['mean']:.4f} V")
        print(f"RMS:        {basic_stats['rms']:.4f} V")
        print(f"Std Dev:    {basic_stats['std_dev']:.4f} V")
        print(f"Max:        {basic_stats['max']:.4f} V")
        print(f"Min:        {basic_stats['min']:.4f} V")
        if basic_stats["frequency"] > 0:
            print(f"Frequency:  {basic_stats['frequency'] / 1e3:.2f} kHz")
            print(f"Period:     {basic_stats['period'] * 1e6:.2f} us")

        # Advanced signal quality analysis
        print("\n" + "=" * 60)
        print("SIGNAL QUALITY ANALYSIS")
        print("=" * 60)
        quality = analyze_signal_quality(waveform)
        print(f"SNR:        {quality['snr_db']:.2f} dB")
        print(f"THD:        {quality['thd_percent']:.2f} %")

        # Statistical distribution
        print("\n" + "=" * 60)
        print("STATISTICAL DISTRIBUTION")
        print("=" * 60)
        percentiles = np.percentile(waveform.voltage, [1, 5, 25, 50, 75, 95, 99])
        print(f"1st percentile:   {percentiles[0]:.4f} V")
        print(f"5th percentile:   {percentiles[1]:.4f} V")
        print(f"25th percentile:  {percentiles[2]:.4f} V")
        print(f"Median (50th):    {percentiles[3]:.4f} V")
        print(f"75th percentile:  {percentiles[4]:.4f} V")
        print(f"95th percentile:  {percentiles[5]:.4f} V")
        print(f"99th percentile:  {percentiles[6]:.4f} V")

        # Visualizations
        print("\n" + "=" * 60)
        print("GENERATING VISUALIZATIONS")
        print("=" * 60)

        # Time domain plot
        print("Plotting time-domain waveform...")
        plot_waveform(waveform, 1, "Time Domain Analysis")

        # Frequency domain plot
        print("Plotting frequency spectrum...")
        plot_fft(waveform, 1)

        # Histogram
        print("Plotting voltage distribution...")
        plt.figure(figsize=(12, 4))
        plt.hist(waveform.voltage, bins=100, edgecolor="black", alpha=0.7)
        plt.xlabel("Voltage (V)")
        plt.ylabel("Count")
        plt.title("Voltage Distribution Histogram - Channel 1")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        print("\nDisplaying plots (close windows to continue)...")
        plt.show()

        # Save waveform data
        print("\nSaving waveform data and analysis...")
        collector.save_data(waveforms, "analyzed_waveform.npz")

        # Save analysis results
        with open("analysis_report.txt", "w") as f:
            f.write("WAVEFORM ANALYSIS REPORT\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Oscilloscope: {collector.scope.identify()}\n")
            f.write(f"Samples: {len(waveform.voltage)}\n")
            f.write(f"Sample Rate: {waveform.sample_rate / 1e6:.2f} MSa/s\n\n")

            f.write("BASIC MEASUREMENTS\n")
            f.write("-" * 60 + "\n")
            for key, value in basic_stats.items():
                f.write(f"{key:15s}: {value:.6f}\n")

            f.write("\nSIGNAL QUALITY\n")
            f.write("-" * 60 + "\n")
            for key, value in quality.items():
                f.write(f"{key:15s}: {value:.6f}\n")

        print("Analysis report saved to 'analysis_report.txt'")
        print("Done!")


if __name__ == "__main__":
    main()
```

---

## Probe Calibration Analysis Example

Probe Calibration Analysis Example

### Requirements

- scpi_control - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/probe_calibration_analysis.py
```

### Source Code

```python
#!/usr/bin/env python3
"""
Probe Calibration Analysis Example

Demonstrates waveform region extraction for probe compensation analysis:
plateau detection, slope analysis, calibration guidance, and zoomed region
plots in reports.

By default this example is fully synthetic/no-hardware: it generates its
own 1kHz square waves with numpy for properly-, under-, and over-compensated
plateaus. Optionally, for a real-world check, capture a 1kHz square wave
from your oscilloscope's probe compensation output instead.

Requirements: `SCPI-Instrument-Control[report-generator]` -- no hardware
needed.

Expected output: 'probe_calibration_analysis.pdf', 'probe_calibration_analysis.md',
and a 'plots/' directory, all saved to the current directory.
"""

from datetime import datetime
from pathlib import Path

import numpy as np

from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator
from scpi_control.report_generator.models.report_data import ReportMetadata, TestReport, TestSection, WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer


def generate_test_square_wave(slope: float = 0, noise: float = 0.01):
    """
    Generate a test square wave with configurable plateau slope.

    Args:
        slope: Plateau slope in V/s (positive=rising, negative=falling, 0=flat)
        noise: Noise level to add (RMS voltage)

    Returns:
        Tuple of (time, voltage)
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

    waveform1 = WaveformData(channel="CH1", time=t1, voltage=v1, sample_rate=100000, record_length=len(t1), label="Properly Compensated Probe", probe_ratio=10)

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

    waveform2 = WaveformData(channel="CH2", time=t2, voltage=v2, sample_rate=100000, record_length=len(t2), label="Undercompensated Probe", probe_ratio=10)

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

    waveform3 = WaveformData(channel="CH3", time=t3, voltage=v3, sample_rate=100000, record_length=len(t3), label="Overcompensated Probe", probe_ratio=10)

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

    waveform4 = WaveformData(channel="CH4", time=t4, voltage=v4, sample_rate=100000, record_length=len(t4), label="Manual Region Example")

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
        print(f"  [OK] PDF generated successfully ({pdf_path.stat().st_size:,} bytes)")
    else:
        print(f"  [FAILED] PDF generation failed")

    # Generate Markdown
    md_path = Path("probe_calibration_analysis.md")
    print(f"\nGenerating Markdown: {md_path}")
    md_generator = MarkdownReportGenerator(include_plots=True, plots_dir="plots")
    md_success = md_generator.generate(report, md_path)

    if md_success:
        print(f"  [OK] Markdown generated successfully ({md_path.stat().st_size:,} bytes)")
    else:
        print(f"  [FAILED] Markdown generation failed")

    # ========================================================================
    # Summary
    # ========================================================================
    print("\n" + "=" * 70)
    print("Feature Demonstration Summary")
    print("=" * 70)
    print("\n[OK] Features Demonstrated:")
    print("  1. Automatic plateau detection in square waves")
    print("  2. Plateau slope analysis for probe compensation")
    print("  3. Automatic calibration guidance generation")
    print("  4. Zoomed region plots in reports")
    print("  5. Manual region definition and analysis")
    print("  6. Region-specific statistics and measurements")
    print("  7. Color-coded calibration recommendations")
    print("  8. Both PDF and Markdown report generation")

    print("\n[OK] Report Contents:")
    print(f"  - {len(report.sections)} test sections")
    total_waveforms = sum(len(s.waveforms) for s in report.sections)
    total_regions = sum(len(w.regions) for w in [wf for s in report.sections for wf in s.waveforms])
    print(f"  - {total_waveforms} waveforms analyzed")
    print(f"  - {total_regions} regions detected and analyzed")
    print(f"  - {len(report.key_findings)} key findings")
    print(f"  - {len(report.recommendations)} recommendations")

    print("\n[OK] Files Generated:")
    if pdf_success:
        print(f"  - {pdf_path}")
    if md_success:
        print(f"  - {md_path}")
        print(f"  - plots/ (region zoomed plots)")

    print("\n" + "=" * 70)
    print("Review the generated PDF to see:")
    print("  - Full waveform plots")
    print("  - Automatic plateau detection")
    print("  - Zoomed region subsections")
    print("  - Slope analysis tables")
    print("  - Color-coded calibration guidance")
    print("  - Detailed region-specific measurements")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
```

---

## Test the power supply GUI with a mock connection

Test the power supply GUI with a mock connection.

### Requirements

- PyQt6 - For GUI
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/psu_gui_test.py
```

### Source Code

```python
"""Test the power supply GUI with a mock connection.

This script demonstrates the PSU control GUI using a mock connection,
allowing you to test the interface without physical hardware.

Requirements: `SCPI-Instrument-Control[gui]` -- no instrument needed, but it
opens an interactive PyQt6 window against a mock PSU and requires a display
and user interaction (choosing a PSU, clicking through the GUI). That is why
this example is compile-checked only, not auto-executed in the smoke suite.
"""

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from scpi_control import PowerSupply
from scpi_control.connection.mock import MockConnection
from scpi_control.gui.main_window import MainWindow


def test_psu_gui_with_mock():
    """Launch GUI and connect to mock PSU."""
    app = QApplication(sys.argv)

    # Create main window
    window = MainWindow()
    window.show()

    # Create mock PSU connection
    print("Creating mock PSU connection (Siglent SPD3303X)...")
    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")

    # Create PSU instance with mock connection
    psu = PowerSupply("mock", connection=mock_conn)

    try:
        # Connect to mock PSU
        psu.connect()
        print(f"Connected to: {psu.model_capability.model_name}")
        print(f"Outputs: {psu.model_capability.num_outputs}")

        # Pass PSU to GUI
        window.psu = psu
        window.psu_control.set_psu(psu)

        # Switch to Power Supply tab
        for i in range(window.tabs.count()):
            if window.tabs.tabText(i) == "Power Supply":
                window.tabs.setCurrentIndex(i)
                break

        # Show connection info
        info_msg = (
            f"Mock PSU Connected!\n\n"
            f"Model: {psu.model_capability.model_name}\n"
            f"Outputs: {psu.model_capability.num_outputs}\n"
            f"SCPI Variant: {psu.model_capability.scpi_variant}\n\n"
            f"You can now test the PSU controls:\n"
            f"- Set voltage and current\n"
            f"- Enable/disable outputs\n"
            f"- View real-time measurements\n"
            f"- Test the safety 'All Off' button"
        )
        QMessageBox.information(window, "Mock PSU Connected", info_msg)

        print("\nGUI launched successfully!")
        print("Try the PSU controls in the 'Power Supply' tab")
        print("\nInstructions:")
        print("1. Adjust voltage and current sliders")
        print("2. Enable outputs with checkboxes")
        print("3. Watch real-time measurements update")
        print("4. Test the 'All Outputs OFF' safety button")

        # Run the application
        sys.exit(app.exec())

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


def test_generic_psu():
    """Test with a generic SCPI PSU."""
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    # Create mock generic PSU connection
    print("Creating mock generic PSU connection...")
    mock_conn = MockConnection(psu_mode=True, psu_idn="RIGOL TECHNOLOGIES,DP832,DP8XXXX,V1.0")

    psu = PowerSupply("mock", connection=mock_conn)

    try:
        psu.connect()
        print(f"Connected to: {psu.model_capability.model_name}")
        print(f"SCPI Variant: {psu.model_capability.scpi_variant}")

        window.psu = psu
        window.psu_control.set_psu(psu)

        # Switch to Power Supply tab
        for i in range(window.tabs.count()):
            if window.tabs.tabText(i) == "Power Supply":
                window.tabs.setCurrentIndex(i)
                break

        info_msg = (
            f"Mock Generic PSU Connected!\n\n"
            f"Model: {psu.model_capability.model_name}\n"
            f"Manufacturer: {psu.model_capability.manufacturer}\n"
            f"SCPI Variant: generic (standard commands)\n\n"
            f"This demonstrates generic SCPI-99 compatibility"
        )
        QMessageBox.information(window, "Generic PSU Connected", info_msg)

        print("\nGeneric PSU GUI test launched!")
        sys.exit(app.exec())

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("Power Supply GUI Test with Mock Connection")
    print("=" * 60)
    print()
    print("Choose test:")
    print("1. Siglent SPD3303X (default)")
    print("2. Generic SCPI PSU")
    print()

    choice = input("Enter choice (1 or 2, default=1): ").strip()

    if choice == "2":
        test_generic_psu()
    else:
        test_psu_gui_with_mock()
```

---

## Ask a local LLM questions about a report, using tool-calling

Ask a local LLM questions about a report, using tool-calling.

### Requirements

- scpi_control - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/report_ai_qa.py
```

### Source Code

```python
"""Ask a local LLM questions about a report, using tool-calling.

Builds a synthetic report and asks a local Ollama model questions about it. When
the model supports tools, it answers by CALLING the report's analysis tools
(list_waveforms, analyze_waveform, ...) rather than guessing from a summary.

This needs a local Ollama running with a tool-capable model (e.g. `ollama run
llama3.2`). With none available it prints that and exits cleanly -- so the
example is safe to run anywhere.

Requirements: SCPI-Instrument-Control[report-generator]; optional local Ollama
for the live Q&A. No hardware.
"""

from datetime import datetime

import numpy as np

from scpi_control.report_generator.llm.analyzer import ReportAnalyzer
from scpi_control.report_generator.llm.client import LLMClient, LLMConfig
from scpi_control.report_generator.models.report_data import ReportMetadata, TestReport, TestSection, WaveformData


def build_report() -> TestReport:
    sample_rate = 1e6
    t = np.arange(2000) / sample_rate
    np.random.seed(0)
    v = 3.3 * np.sin(2 * np.pi * 1000 * t) + 0.02 * np.random.randn(t.size)
    waveform = WaveformData(channel="C1", time=t, voltage=v, sample_rate=sample_rate, record_length=t.size, label="1 kHz reference")
    return TestReport(
        metadata=ReportMetadata(title="AI Q&A Demo", technician="Lab Tech", test_date=datetime.now()),
        sections=[TestSection(title="Captures", waveforms=[waveform], order=1)],
    )


def main():
    print("=" * 60)
    print("Local-LLM tool-calling Q&A over a report")
    print("=" * 60)

    report = build_report()

    client = LLMClient(LLMConfig.create_ollama_config(model="llama3.2"))

    if not client.supports_tools():
        print("No tool-capable local model available.")
        print("Start Ollama with a tool-capable model (e.g. `ollama run llama3.2`) to try the live Q&A.")
        print("=" * 60)
        print("Done (skipped live Q&A).")
        print("=" * 60)
        return

    analyzer = ReportAnalyzer(client)
    questions = [
        "What channels are in this report?",
        "What kind of signal is on C1, and what is its frequency?",
    ]
    for question in questions:
        print(f"\nQ: {question}")
        try:
            answer = analyzer.answer_question(report, question)
        except Exception as exc:  # never let a model hiccup crash the example
            print(f"A: (the model call failed: {exc})")
            continue
        print(f"A: {answer if answer is not None else '(no answer)'}")

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

---

## Apply company branding to a generated report

Apply company branding to a generated report.

### Requirements

- scpi_control - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/report_branding.py
```

### Source Code

```python
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
```

---

## Deterministic (LLM-free) report analysis

Deterministic (LLM-free) report analysis.

### Requirements

- scpi_control - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/report_computed_analysis.py
```

### Source Code

```python
"""Deterministic (LLM-free) report analysis.

Builds a synthetic test report and runs ComputedAnalyzer over it. Unlike the AI
path, this needs no local model and no network: it fills the executive summary,
key findings, and recommendations straight from the waveform analysis and sets
summary_source to "computed".

Requirements: SCPI-Instrument-Control[report-generator] (no hardware, no network)
"""

from datetime import datetime

import numpy as np

from scpi_control.report_generator.analysis.computed_analyzer import ComputedAnalyzer
from scpi_control.report_generator.models.report_data import (
    SUMMARY_SOURCE_COMPUTED,
    MeasurementResult,
    ReportMetadata,
    TestReport,
    TestSection,
    WaveformData,
)


def build_report() -> TestReport:
    """A one-channel synthetic report: a 1 kHz sine with light noise."""
    sample_rate = 1e6
    t = np.arange(2000) / sample_rate
    np.random.seed(0)
    v = 3.3 * np.sin(2 * np.pi * 1000 * t) + 0.02 * np.random.randn(t.size)
    waveform = WaveformData(
        channel="C1",
        time=t,
        voltage=v,
        sample_rate=sample_rate,
        record_length=t.size,
        label="1 kHz reference",
    )
    measurements = [
        MeasurementResult(name="Frequency", value=1000.0, unit="Hz", channel="C1", passed=True, criteria_min=990, criteria_max=1010),
        MeasurementResult(name="Peak-to-Peak", value=6.6, unit="V", channel="C1", passed=True, criteria_min=6.0, criteria_max=7.0),
    ]
    report = TestReport(
        metadata=ReportMetadata(title="Computed Analysis Demo", technician="Lab Tech", test_date=datetime.now()),
        sections=[TestSection(title="Captures", waveforms=[waveform], measurements=measurements, order=1)],
    )
    report.overall_result = report.calculate_overall_result()
    return report


def main():
    print("=" * 60)
    print("Deterministic (LLM-free) report analysis")
    print("=" * 60)

    report = build_report()

    print("Running ComputedAnalyzer (no model, no network)...")
    ComputedAnalyzer().analyze_report(report)

    print(f"\nsummary_source: {report.summary_source!r}  (expected {SUMMARY_SOURCE_COMPUTED!r})")
    print("\nExecutive summary:")
    print(f"  {report.executive_summary}")
    print("\nKey findings:")
    for finding in report.key_findings:
        print(f"  - {finding}")
    print("\nRecommendations:")
    for recommendation in report.recommendations:
        print(f"  - {recommendation}")

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

---

## Example: Generating Professional Test Reports

Example: Generating Professional Test Reports

### Requirements

- scpi_control - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/report_generation_example.py
```

### Source Code

```python
"""
Example: Generating Professional Test Reports

Demonstrates the Report Generator: synthesizing waveform data with numpy
(no oscilloscope or input file needed), creating report metadata, adding
measurements with pass/fail criteria, optional AI analysis, and generating
PDF and Markdown reports.

Requirements: `SCPI-Instrument-Control[report-generator]` -- no hardware
needed.

Expected output: 'example_reports/example_report.md' and, if reportlab is
installed, 'example_reports/example_report.pdf'.
"""

from datetime import datetime
from pathlib import Path

import numpy as np

from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.models.criteria import ComparisonType, CriteriaSet, MeasurementCriteria
from scpi_control.report_generator.models.report_data import SUMMARY_SOURCE_AI, MeasurementResult, ReportMetadata, TestReport, TestSection, WaveformData

# Import PDF generator if available
try:
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator

    PDF_AVAILABLE = True
except ImportError:
    print("Warning: reportlab not installed - PDF generation will be skipped")
    PDF_AVAILABLE = False

from scpi_control.report_generator.llm.analyzer import ReportAnalyzer

# Import LLM components if you want AI features
from scpi_control.report_generator.llm.client import LLMClient, LLMConfig


def create_sample_waveform() -> WaveformData:
    """Create a sample waveform for demonstration."""
    # Generate a simple sine wave with some noise
    sample_rate = 1e6  # 1 MS/s
    duration = 1e-3  # 1 ms
    frequency = 1e3  # 1 kHz

    num_samples = int(sample_rate * duration)
    time_data = np.linspace(0, duration, num_samples)

    # Generate sine wave with noise
    voltage_data = 2.0 * np.sin(2 * np.pi * frequency * time_data)
    voltage_data += 0.1 * np.random.randn(num_samples)  # Add noise

    return WaveformData(
        channel="CH1",
        time=time_data,
        voltage=voltage_data,
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
        report.summary_source = SUMMARY_SOURCE_AI

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
    print("  - Generating PDF report...")
    try:
        pdf_path = output_dir / "example_report.pdf"
        pdf_generator = PDFReportGenerator()

        if pdf_generator.generate(report, pdf_path):
            print(f"    [OK] PDF report saved: {pdf_path}")
        else:
            print(f"    [FAILED] Failed to generate PDF report")
    except ImportError:
        print("  - PDF generation skipped (reportlab not installed)")

    # Done!
    print()
    print("=" * 60)
    print("Example complete!")
    print(f"Reports saved to: {output_dir.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

---

## Vector Graphics on Oscilloscope using XY Mode

Vector Graphics on Oscilloscope using XY Mode

### Requirements

- scpi_control[fun] - Vector graphics extras
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/vector_graphics_xy_mode.py
```

### Source Code

```python
"""Vector Graphics on Oscilloscope using XY Mode

This example demonstrates how to use the oscilloscope as a vector display
by generating waveforms for XY mode.

REQUIREMENTS:
    - Install fun extras: pip install "SCPI-Instrument-Control[fun]"
    - External AWG/DAC to feed signals into scope channels
      OR use scope's built-in AWG if available
    - Oscilloscope channels connected to AWG outputs

SETUP:
    1. Connect AWG CH1 output → Scope CH1 (X axis)
    2. Connect AWG CH2 output → Scope CH2 (Y axis)
    3. Enable XY mode on oscilloscope (Display → XY Mode → ON)
    4. Adjust voltage scales to see full pattern

WHAT THIS DOES:
    - Generates X/Y waveform data for various shapes
    - Saves waveform files that can be loaded into an AWG
    - Creates animations by rotating and transforming shapes
"""

import time

import numpy as np

from scpi_control import Oscilloscope
from scpi_control.vector_graphics import Shape, VectorDisplay

# Configuration
SCOPE_IP = "192.168.1.100"
SAMPLE_RATE = 1e6  # 1 MSa/s for AWG
DURATION = 0.1  # 100ms per frame
OUTPUT_DIR = "vector_waveforms"


def main():
    """Main demonstration of vector graphics features."""

    print("=" * 60)
    print("  Oscilloscope Vector Graphics Demo")
    print("=" * 60)
    print()
    print("This demo generates waveform data for XY mode display.")
    print("Load the generated files into your AWG to see the shapes!")
    print()

    # Connect to oscilloscope
    print(f"Connecting to {SCOPE_IP}...")
    scope = Oscilloscope(SCOPE_IP)
    scope.connect()
    print(f"Connected: {scope.identify()}")
    print()

    # Initialize vector display
    print("Initializing vector display (CH1=X, CH2=Y)...")
    display = scope.vector_display
    display.enable_xy_mode(voltage_scale=1.0)
    print("[OK] XY mode configured")
    print()

    # Create output directory
    import os

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ==========================================
    # Demo 1: Basic Shapes
    # ==========================================
    print("Demo 1: Basic Shapes")
    print("-" * 40)

    # Circle
    print("  Generating circle...")
    circle = Shape.circle(radius=0.8, points=1000)
    display.save_waveforms(circle, f"{OUTPUT_DIR}/01_circle", sample_rate=SAMPLE_RATE, duration=DURATION)

    # Square
    print("  Generating square...")
    square = Shape.rectangle(width=1.6, height=1.6, points_per_side=250)
    display.save_waveforms(square, f"{OUTPUT_DIR}/02_square", sample_rate=SAMPLE_RATE, duration=DURATION)

    # Star
    print("  Generating star...")
    star = Shape.star(num_points=5, outer_radius=0.9, inner_radius=0.4)
    display.save_waveforms(star, f"{OUTPUT_DIR}/03_star", sample_rate=SAMPLE_RATE, duration=DURATION)

    # Triangle
    print("  Generating triangle...")
    triangle = Shape.polygon(
        [
            (0, 0.8),  # Top
            (-0.7, -0.4),  # Bottom left
            (0.7, -0.4),  # Bottom right
        ],
        points_per_side=300,
    )
    display.save_waveforms(triangle, f"{OUTPUT_DIR}/04_triangle", sample_rate=SAMPLE_RATE, duration=DURATION)

    print("[OK] Basic shapes generated\n")

    # ==========================================
    # Demo 2: Lissajous Figures
    # ==========================================
    print("Demo 2: Lissajous Figures")
    print("-" * 40)

    lissajous_patterns = [
        (3, 2, np.pi / 2, "3_2"),
        (5, 4, 0, "5_4"),
        (7, 5, np.pi / 4, "7_5"),
    ]

    for a, b, delta, name in lissajous_patterns:
        print(f"  Generating Lissajous {a}:{b}...")
        lissajous = Shape.lissajous(a=a, b=b, delta=delta, points=2000)
        display.save_waveforms(lissajous, f"{OUTPUT_DIR}/lissajous_{name}", sample_rate=SAMPLE_RATE, duration=DURATION)

    print("[OK] Lissajous figures generated\n")

    # ==========================================
    # Demo 3: Text
    # ==========================================
    print("Demo 3: Text Rendering")
    print("-" * 40)
    print("  Generating text 'HELLO'...")

    try:
        text = Shape.text("HELLO", font_size=0.6)
        display.save_waveforms(text, f"{OUTPUT_DIR}/text_hello", sample_rate=SAMPLE_RATE, duration=DURATION)
        print("[OK] Text generated")
    except Exception as e:
        print(f"  WARNING: Text generation skipped: {e}")

    print()

    # ==========================================
    # Demo 4: Animations (Rotating Star)
    # ==========================================
    print("Demo 4: Animation Frames (Rotating Star)")
    print("-" * 40)

    star_base = Shape.star(num_points=5, outer_radius=0.8, inner_radius=0.3)

    for i, angle in enumerate(range(0, 360, 15)):
        rotated_star = star_base.rotate(angle)
        display.save_waveforms(
            rotated_star,
            f"{OUTPUT_DIR}/anim_star_frame_{i:02d}",
            sample_rate=SAMPLE_RATE,
            duration=DURATION / 10,
        )  # Faster frames
        print(f"  Frame {i+1}/24 (angle={angle}deg)")

    print("[OK] Animation frames generated\n")

    # ==========================================
    # Demo 5: Composite Shapes
    # ==========================================
    print("Demo 5: Composite Shapes")
    print("-" * 40)

    # Smiley face (circle + eyes + mouth)
    print("  Generating smiley face...")
    face_outer = Shape.circle(radius=0.9, points=500)
    eye_left = Shape.circle(radius=0.1, center=(-0.3, 0.3), points=100)
    eye_right = Shape.circle(radius=0.1, center=(0.3, 0.3), points=100)

    # Mouth as an arc (half circle)
    t = np.linspace(0, np.pi, 200)
    mouth_x = 0.5 * np.cos(t)
    mouth_y = -0.2 + 0.3 * np.sin(t)
    from scpi_control.vector_graphics import VectorPath

    mouth = VectorPath(x=mouth_x, y=mouth_y, connected=False)

    # Combine all parts
    smiley = face_outer.combine(eye_left).combine(eye_right).combine(mouth)
    display.save_waveforms(smiley, f"{OUTPUT_DIR}/composite_smiley", sample_rate=SAMPLE_RATE, duration=DURATION)
    print("[OK] Smiley face generated\n")

    # ==========================================
    # Summary
    # ==========================================
    print("=" * 60)
    print("  Demo Complete!")
    print("=" * 60)
    print()
    print(f"Waveform files saved to: {OUTPUT_DIR}/")
    print()
    print("Next Steps:")
    print("  1. Load the .csv files into your AWG")
    print("     - Load *_x.csv -> AWG Channel 1")
    print("     - Load *_y.csv -> AWG Channel 2")
    print("  2. Enable XY mode on the oscilloscope")
    print("  3. Start the AWG output")
    print("  4. Adjust timebase and voltage scales to see the pattern")
    print()
    print("Tips:")
    print("  - Use CSV format for most AWGs")
    print("  - Adjust sample rate to match your AWG capabilities")
    print("  - Connect AWG outputs directly to scope inputs")
    print("  - Set scope to DC coupling for best results")
    print()

    # Cleanup
    scope.disconnect()


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        if "fun" in str(e):
            print()
            print("=" * 60)
            print("  ERROR: Missing 'fun' extras")
            print("=" * 60)
            print()
            print("Vector graphics features require additional packages.")
            print()
            print("Install with:")
            print('  pip install "SCPI-Instrument-Control[fun]"')
            print()
            print("This will install:")
            print("  - shapely (geometric operations)")
            print("  - Pillow (text rendering)")
            print("  - svgpathtools (SVG path support)")
            print()
        else:
            raise
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        raise
```

---

## Next Steps

Review the [API Reference](../api/oscilloscope.md) for detailed documentation of all available methods and properties.

See also:

- [User Guide](../user-guide/basic-usage.md) - Conceptual documentation
- [API Reference](../api/oscilloscope.md) - Detailed API documentation
- [Getting Started](../getting-started/quickstart.md) - Quick start guide
