# Advanced Examples

Advanced examples demonstrating signal analysis, FFT processing, and specialized features like vector graphics for XY mode display.

## Quick Reference

| Example                                                                                         | Description                                   |
| ----------------------------------------------------------------------------------------------- | --------------------------------------------- |
| [Advanced waveform analysis and visualization](#advanced-waveform-analysis-and-visualization)   | Advanced waveform analysis and visualization. |
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
"""

import matplotlib.pyplot as plt
import numpy as np

from siglent.automation import DataCollector

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def plot_waveform(waveform, channel_num, title="Waveform"):
    """Plot time-domain waveform."""
    time = np.arange(len(waveform.voltage)) * waveform.time_interval
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
    fft_freq = np.fft.fftfreq(len(waveform.voltage), waveform.time_interval)

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
            print(f"Period:     {basic_stats['period'] * 1e6:.2f} µs")

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

## Vector Graphics on Oscilloscope using XY Mode

Vector Graphics on Oscilloscope using XY Mode

### Requirements

- siglent - Core library
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
    - Install fun extras: pip install "Siglent-Oscilloscope[fun]"
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

from siglent import Oscilloscope
from siglent.vector_graphics import Shape, VectorDisplay

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
    print("✓ XY mode configured")
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

    print("✓ Basic shapes generated\n")

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

    print("✓ Lissajous figures generated\n")

    # ==========================================
    # Demo 3: Text
    # ==========================================
    print("Demo 3: Text Rendering")
    print("-" * 40)
    print("  Generating text 'HELLO'...")

    try:
        text = Shape.text("HELLO", font_size=0.6)
        display.save_waveforms(text, f"{OUTPUT_DIR}/text_hello", sample_rate=SAMPLE_RATE, duration=DURATION)
        print("✓ Text generated")
    except Exception as e:
        print(f"  ⚠ Text generation skipped: {e}")

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
        print(f"  Frame {i+1}/24 (angle={angle}°)")

    print("✓ Animation frames generated\n")

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
    from siglent.vector_graphics import VectorPath

    mouth = VectorPath(x=mouth_x, y=mouth_y, connected=False)

    # Combine all parts
    smiley = face_outer.combine(eye_left).combine(eye_right).combine(mouth)
    display.save_waveforms(smiley, f"{OUTPUT_DIR}/composite_smiley", sample_rate=SAMPLE_RATE, duration=DURATION)
    print("✓ Smiley face generated\n")

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
    print("     - Load *_x.csv → AWG Channel 1")
    print("     - Load *_y.csv → AWG Channel 2")
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
            print('  pip install "Siglent-Oscilloscope[fun]"')
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
