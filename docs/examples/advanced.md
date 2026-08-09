# Advanced Examples

Advanced examples demonstrating signal analysis, FFT processing, and specialized features like vector graphics for XY mode display.

## Quick Reference

| Example | Description |
|---------|-------------|
| [Advanced waveform analysis and visualization](#advanced-waveform-analysis-and-visualization) | Advanced waveform analysis and visualization. |
| [AWG-to-scope loopback: a mock function generator's live state drives what a](#awg-to-scope-loopback-a-mock-function-generators-live-state-drives-what-a) | AWG-to-scope loopback: a mock function generator's live state drives what a
mock oscilloscope captures, optionally through an RC device-under-test model. |
| [Measure a frequency response: mock AWG -> RC low-pass -> mock scope](#measure-a-frequency-response-mock-awg-rc-low-pass-mock-scope) | Measure a frequency response: mock AWG -> RC low-pass -> mock scope. |
| [Tektronix measurement badges: how repeat measurements reuse a slot](#tektronix-measurement-badges-how-repeat-measurements-reuse-a-slot) | Tektronix measurement badges: how repeat measurements reuse a slot. |
| [Probe Calibration Analysis Example](#probe-calibration-analysis-example) | Probe Calibration Analysis Example |
| [Serial protocol decoding: I2C, SPI and UART](#serial-protocol-decoding-i2c-spi-and-uart) | Serial protocol decoding: I2C, SPI and UART. |
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
- None -- runs on the built-in mock; `--host <ip>` for real hardware

### Configuration

None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.

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

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network. matplotlib is a
core dependency, no extra install needed.

Expected output: basic and signal-quality stats printed to the console;
'advanced_analysis_time.png', 'advanced_analysis_fft.png', and
'advanced_analysis_histogram.png' plots, plus 'analyzed_waveform_ch1.npz' and
'analysis_report.txt', all saved to the current directory. No plot window
is opened -- matplotlib's Agg backend (set by the test harness) cannot
display one, so this example saves figures instead of calling plt.show().

Note: against --host mock, the instrument-side :MEASure values are fixed
constants and do not track the synthesized waveform. Numbers computed from
captured samples (via scpi_control.analysis) do track it. This is a mock
fidelity limit, not a measurement error.
"""

import argparse

import matplotlib.pyplot as plt
import numpy as np

from scpi_control.automation import DataCollector
from scpi_control.connection import MockConnection
from scpi_control.signal_synth import SignalSpec


def _connect(host):
    """Return a mock connection for --host mock, or None to use a real socket."""
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True},
        signals={1: SignalSpec(kind="square", frequency=1000.0, amplitude=1.65, offset=1.65)},
        sample_rate=20e6,
        timebase=500e-6,
    )


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
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' for the built-in mock scope (default: mock)")
    args = parser.parse_args()

    with DataCollector(args.host, connection=_connect(args.host)) as collector:
        print(f"Connected to {collector.scope.identify()}\n")

        # Capture waveform
        print("Capturing waveform from channel 1...")
        waveforms = collector.capture_single([1])

        if 1 not in waveforms:
            print("Error: Channel 1 not available")
            raise SystemExit(1)

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

        # Visualizations. plt.show() would block waiting for a display (and is
        # a no-op under the Agg backend anyway), so each figure is saved to a
        # file instead.
        print("\n" + "=" * 60)
        print("GENERATING VISUALIZATIONS")
        print("=" * 60)

        # Time domain plot
        print("Plotting time-domain waveform...")
        plot_waveform(waveform, 1, "Time Domain Analysis")
        plt.savefig("advanced_analysis_time.png", dpi=150)
        plt.close()

        # Frequency domain plot
        print("Plotting frequency spectrum...")
        plot_fft(waveform, 1)
        plt.savefig("advanced_analysis_fft.png", dpi=150)
        plt.close()

        # Histogram
        print("Plotting voltage distribution...")
        plt.figure(figsize=(12, 4))
        plt.hist(waveform.voltage, bins=100, edgecolor="black", alpha=0.7)
        plt.xlabel("Voltage (V)")
        plt.ylabel("Count")
        plt.title("Voltage Distribution Histogram - Channel 1")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig("advanced_analysis_histogram.png", dpi=150)
        plt.close()

        print("Plots saved to 'advanced_analysis_time.png', 'advanced_analysis_fft.png', and 'advanced_analysis_histogram.png'")

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

## AWG-to-scope loopback: a mock function generator's live state drives what a

AWG-to-scope loopback: a mock function generator's live state drives what a
mock oscilloscope captures, optionally through an RC device-under-test model.

### Requirements

- scpi_control - Core library
- No hardware required

### Configuration

No hardware required.

### Usage

```bash
python examples/awg_scope_loopback.py
```

### Source Code

```python
"""AWG-to-scope loopback: a mock function generator's live state drives what a
mock oscilloscope captures, optionally through an RC device-under-test model.

scpi_control.connection.mock.loopback.AwgLoopback is a callable suitable for
MockConnection(signals={...}): it reads a separate mock AWG connection's
current channel state every time the scope acquires, so a SCPI write on the
AWG changes the very next scope capture -- two mock instruments joined by one
virtual cable. An optional scpi_control.dut.RCLowPass sits on that cable,
standing in for a device under test between the two instruments and rounding
the edges of whatever the AWG outputs.

This example (1) opens a mock AWG and a mock scope wired together with
AwgLoopback and prints the captured peak-to-peak of a sine, (2) switches the
AWG to a square wave with a plain SCPI write and prints the new peak-to-peak,
then (3) adds an RCLowPass DUT and prints the 10%-90% rise time of the
square wave's rising edge with and without the DUT, to show how much it
rounds the edge. Rise time is used rather than a raw sample-to-sample step
because the mock's int8 code quantization (25 codes/division, see
docs/user-guide/synthetic-signals.md) would dominate a step-height
comparison at a gentle cutoff; a 10%-90% time span is many samples wide and
is not limited by the code grid.

Requirements: SCPI-Instrument-Control (core install) -- runs entirely against
mock connections, no instrument needed.
"""

import numpy as np

from scpi_control.connection import MockConnection
from scpi_control.connection.mock.loopback import AwgLoopback
from scpi_control.dut import RCLowPass
from scpi_control.oscilloscope import Oscilloscope

SAMPLE_RATE = 1_000_000.0
TIMEBASE = 1e-3


def _make_awg() -> MockConnection:
    """A mock AWG, output enabled at 2.0 Vpp / 1 kHz sine."""
    awg = MockConnection("mock", awg_mode=True)
    awg.connect()
    awg.write("C1:BSWV FRQ,1000")
    awg.write("C1:BSWV AMP,2.0")
    awg.write("C1:OUTP ON")
    return awg


def _make_scope(source) -> Oscilloscope:
    """A mock scope whose channel 1 synthesizes from `source` (an AwgLoopback)."""
    conn = MockConnection(
        "mock",
        channel_states={1: True, 2: False, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=SAMPLE_RATE,
        timebase=TIMEBASE,
        signals={1: source},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope


def _vpp(voltage) -> float:
    return float(voltage.max() - voltage.min())


def _rising_crossing(time_s: np.ndarray, voltage: np.ndarray, level: float, start_index: int = 0):
    """Sub-sample time of the first rising crossing of `level` at/after `start_index`.

    Linear interpolation between the two bracketing samples locates the
    crossing between samples, not just to the nearest one. Returns
    (crossing_time, index_of_the_sample_just_before_the_crossing).
    """
    candidates = np.flatnonzero((voltage[start_index:-1] < level) & (voltage[start_index + 1 :] >= level))
    if candidates.size == 0:
        raise ValueError(f"no rising crossing of {level} found at or after index {start_index}")
    i = start_index + int(candidates[0])
    t0, t1 = time_s[i], time_s[i + 1]
    v0, v1 = voltage[i], voltage[i + 1]
    crossing_time = float(t0 + (level - v0) * (t1 - t0) / (v1 - v0))
    return crossing_time, i


def _rise_time_10_90_us(waveform) -> float:
    """10%-90% rise time (microseconds) of the first rising transition.

    The 10% and 90% levels are relative to the trace's own min/max, so this
    works the same way whether or not a DUT has rounded the edge. Unlike a
    raw sample-to-sample step, a rise time spans many samples and is not
    limited by the mock's int8 code quantization.
    """
    voltage = waveform.voltage
    time_s = waveform.time
    lo, hi = float(voltage.min()), float(voltage.max())
    v10 = lo + 0.10 * (hi - lo)
    v90 = lo + 0.90 * (hi - lo)
    t10, i10 = _rising_crossing(time_s, voltage, v10)
    t90, _ = _rising_crossing(time_s, voltage, v90, start_index=i10)
    return (t90 - t10) * 1e6


def demo_live_loopback() -> MockConnection:
    """Capture a sine, switch the AWG to a square over SCPI, capture again."""
    print("=== Part 1: the scope captures whatever the AWG is currently outputting ===")
    awg = _make_awg()
    scope = _make_scope(AwgLoopback(awg, awg_channel=1))
    try:
        sine = scope.get_waveform(1, provenance=False)
        print(f"AWG set to SINE, 2.0 Vpp: scope captures Vpp={_vpp(sine.voltage):.3f} V")

        awg.write("C1:BSWV WVTP,SQUARE")
        square = scope.get_waveform(1, provenance=False)
        print(f"AWG switched to SQUARE via 'C1:BSWV WVTP,SQUARE': scope captures Vpp={_vpp(square.voltage):.3f} V")
    finally:
        scope.disconnect()
    return awg


def demo_dut(awg: MockConnection) -> None:
    """Add an RCLowPass DUT between the (now square-wave) AWG and the scope."""
    print()
    print("=== Part 2: an RCLowPass DUT rounds the square wave's edges ===")
    sharp_scope = _make_scope(AwgLoopback(awg))
    soft_scope = _make_scope(AwgLoopback(awg, dut=RCLowPass(cutoff_hz=2_000.0)))
    try:
        sharp = sharp_scope.get_waveform(1, provenance=False)
        soft = soft_scope.get_waveform(1, provenance=False)
    finally:
        sharp_scope.disconnect()
        soft_scope.disconnect()

    sharp_rise_us = _rise_time_10_90_us(sharp)
    soft_rise_us = _rise_time_10_90_us(soft)
    print(f"10-90 percent rise time with no DUT: {sharp_rise_us:.3f} us (an ideal edge, a fraction of one sample)")
    print(f"10-90 percent rise time with RCLowPass(cutoff_hz=2000): {soft_rise_us:.1f} us")
    print("The DUT stretched the rising edge from a fraction of a microsecond to roughly " f"{soft_rise_us:.0f} us -- the edge is visibly rounded")


def main() -> None:
    awg = demo_live_loopback()
    try:
        demo_dut(awg)
    finally:
        awg.disconnect()


if __name__ == "__main__":
    main()
```

---

## Measure a frequency response: mock AWG -> RC low-pass -> mock scope

Measure a frequency response: mock AWG -> RC low-pass -> mock scope.

### Requirements

- scpi_control - Core library
- No hardware required

### Configuration

No hardware required.

### Usage

```bash
python examples/frequency_response_sweep.py
```

### Source Code

```python
"""Measure a frequency response: mock AWG -> RC low-pass -> mock scope.

Channel 1 is patched straight to the generator (the reference); channel 2 sees
the same signal through an RCLowPass device model with a 1 kHz corner. The sweep
steps the generator across two decades, autoranges the response channel at every
point, and compares the measured corner against the analytic one.

Everything here runs against mock connections -- no instrument required, and no
claim in the output has been validated against real hardware, because there is
no function generator on the development bench.

Requirements: SCPI-Instrument-Control (core install).
"""

import math

from scpi_control.connection import MockConnection
from scpi_control.connection.mock.loopback import AwgLoopback
from scpi_control.dut import RCLowPass
from scpi_control.frequency_response import sweep
from scpi_control.function_generator import FunctionGenerator
from scpi_control.oscilloscope import Oscilloscope

CUTOFF_HZ = 1000.0


def main() -> None:
    awg_connection = MockConnection("mock", awg_mode=True)
    awg = FunctionGenerator("mock", connection=awg_connection)
    awg.connect()

    scope = Oscilloscope(
        "mock",
        connection=MockConnection(
            "mock",
            channel_states={1: True, 2: True, 3: False, 4: False},
            trigger_status=["Stop"],
            sample_rate=1e6,
            timebase=1e-3,
            signals={
                1: AwgLoopback(awg_connection, awg_channel=1),
                2: AwgLoopback(awg_connection, awg_channel=1, dut=RCLowPass(CUTOFF_HZ)),
            },
        ),
    )
    scope.connect()

    try:
        print(f"Sweeping 100 Hz to 10 kHz through an RC low-pass with a {CUTOFF_HZ:.0f} Hz corner\n")
        print(f"{'frequency':>12} {'gain':>10} {'phase':>10} {'V/div':>8}")

        def show(point):
            if point.gain_db is None:
                print(f"{point.frequency_hz:>10.1f} Hz {'--':>10} {'--':>10}   ({point.excluded_reason})")
            else:
                print(f"{point.frequency_hz:>10.1f} Hz {point.gain_db:>9.2f} dB {point.phase_deg:>8.1f} deg {point.volts_per_div:>7.3f}")

        result = sweep(scope, awg, reference_channel=1, response_channel=2, start_hz=100.0, stop_hz=10000.0, points_per_decade=5, amplitude_vpp=2.0, settle_s=0.0, on_point=show)
    finally:
        scope.disconnect()
        awg.disconnect()

    measured = result.cutoff_hz()
    print(f"\nMeasured -3 dB corner: {measured:.1f} Hz (model: {CUTOFF_HZ:.1f} Hz)")
    print(f"Error: {100 * (measured - CUTOFF_HZ) / CUTOFF_HZ:+.1f}% -- interpolated between points, so it cannot beat the point spacing")

    at_cutoff = min(result.usable(), key=lambda point: abs(point.frequency_hz - CUTOFF_HZ))
    ratio = at_cutoff.frequency_hz / CUTOFF_HZ
    print(f"\nAt {at_cutoff.frequency_hz:.1f} Hz: measured {at_cutoff.gain_db:.3f} dB / {at_cutoff.phase_deg:.2f} deg")
    print(f"{'':>{len(f'At {at_cutoff.frequency_hz:.1f} Hz:')}} analytic {-10 * math.log10(1 + ratio**2):.3f} dB / {-math.degrees(math.atan(ratio)):.2f} deg")

    result.to_csv("frequency_response.csv")
    print("\nWrote frequency_response.csv (metadata header + one row per point)")

    figure = result.plot(title=f"RC low-pass, {CUTOFF_HZ:.0f} Hz corner")
    figure.savefig("frequency_response.png")
    print("Wrote frequency_response.png (Bode plot; excluded points would show as gaps, none here)")


if __name__ == "__main__":
    main()
```

---

## Tektronix measurement badges: how repeat measurements reuse a slot

Tektronix measurement badges: how repeat measurements reuse a slot.

### Requirements

- scpi_control - Core library
- None -- runs on the built-in mock; `--host <ip>` for real hardware

### Configuration

None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.

### Usage

```bash
python examples/measurement_badges_example.py
```

### Source Code

```python
"""Tektronix measurement badges: how repeat measurements reuse a slot.

A Tektronix MSO exposes measurements as numbered "badges" that must be
allocated before they can be read. scpi_control pools them: the first
measurement of a given type allocates a badge, repeats reuse it with a single
query, and disconnecting removes the badges it created without touching any
of the user configured on the front panel.

Requirements: none by default -- runs against a built-in mock MSO58. Pass
--host <ip> to drive a real Tektronix MSO on the network.

Expected output: measured values plus, for the mock run only, the SCPI
traffic that allocated and removed the badge (a real-hardware run has no
`connection` object to inspect, so those two trace lines are skipped). No
files are written.
"""

import argparse

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection

MSO58_IDN = "TEKTRONIX,MSO58,MOCK0300,CF:91.1CT FV:2.0"


def _connect(host):
    if host != "mock":
        return None
    return MockConnection("mock", idn=MSO58_IDN, channel_states={i: True for i in range(1, 9)})


def main():
    parser = argparse.ArgumentParser(description="Tektronix measurement badge pooling")
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' (default: mock)")
    args = parser.parse_args()

    connection = _connect(args.host)
    scope = Oscilloscope(args.host, connection=connection)
    scope.connect()
    try:
        print(f"Connected to: {scope.identify()}")

        print(f"CH1 Vpp (first call, allocates a badge): {scope.measurement.measure_vpp(1):.3f} V")
        print(f"CH1 Vpp (second call, reuses the badge): {scope.measurement.measure_vpp(1):.3f} V")
        print(f"CH2 Vpp (different channel, its own slot): {scope.measurement.measure_vpp(2):.3f} V")
    finally:
        scope.disconnect()

    if connection is not None:
        allocated = [w for w in connection.writes if "ADDNew" in w]
        removed = [w for w in connection.writes if "DELete" in w]
        print(f"Badges allocated: {allocated}")
        print(f"Badges removed on disconnect: {removed}")


if __name__ == "__main__":
    main()
```

---

## Probe Calibration Analysis Example

Probe Calibration Analysis Example

### Requirements

- scpi_control - Core library
- No hardware required

### Configuration

No hardware required.

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

## Serial protocol decoding: I2C, SPI and UART

Serial protocol decoding: I2C, SPI and UART.

### Requirements

- scpi_control - Core library
- None -- runs on the built-in mock; `--host <ip>` for real hardware

### Configuration

None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.

### Usage

```bash
python examples/protocol_decoding.py
```

### Source Code

```python
"""Serial protocol decoding: I2C, SPI and UART.

Shows what each decoder needs before it can run -- which channels it must be
given and which parameters it exposes -- then decodes a captured waveform and
summarises the events found.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Note: the mock synthesizes analogue test signals (sine, square, ramp, ...),
not framed bus traffic, so a mock run demonstrates decoder setup and the
decode call rather than a realistic bus transcript. Running the UART decoder
against the mock's 10 kHz square wave does not find real UART frames -- but
it is not guaranteed to find *zero* events either: the captured buffer holds
14 falling edges, and the decoder tries each as a candidate start bit. The
first 13 are correctly rejected (the wave's ~50 us low phase has already
flipped back high by the time the decoder samples 52 us later). The 14th
is the last edge in the buffer, so its start-bit and eight data-bit sample
times all fall past the end of the capture; the decoder's nearest-sample
lookup has no bounds check, so those nine out-of-range queries silently
clamp to the buffer's final (still-low) sample instead of being rejected.
The result is a single spurious byte (0x00) that has nothing to do with
real bus data -- a buffer-boundary clamping artifact, not periodic or
baud-rate phase alignment. Point --host at hardware probing a real UART
line to see genuine decoded bytes.

Expected output: each decoder's required channels and parameters, then the
UART event summary for the mock's square wave -- deterministically
`UART event summary: {'DATA': 1}`, the single spurious byte described above.
No files are written.
"""

import argparse

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection
from scpi_control.protocol_decoders import I2CDecoder, SPIDecoder, UARTDecoder
from scpi_control.signal_synth import SignalSpec


def _connect(host):
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True, 2: True},
        signals={
            1: SignalSpec(kind="square", frequency=10000.0, amplitude=1.65, offset=1.65),
            2: SignalSpec(kind="square", frequency=5000.0, amplitude=1.65, offset=1.65),
        },
        sample_rate=10e6,
        timebase=1e-3,
    )


def main():
    parser = argparse.ArgumentParser(description="Serial protocol decoding")
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' (default: mock)")
    args = parser.parse_args()

    for decoder in (I2CDecoder(), SPIDecoder(), UARTDecoder()):
        name = type(decoder).__name__
        print(f"{name}: channels={decoder.get_required_channels()} parameters={sorted(decoder.get_parameters())}")

    scope = Oscilloscope(args.host, connection=_connect(args.host))
    scope.connect()
    try:
        waveform = scope.get_waveform(channel=1)
        decoder = UARTDecoder()
        decoder.decode({"TX": waveform})
        print(f"UART event summary: {decoder.get_event_summary()}")
    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()
```

---

## Test the power supply GUI with a mock connection

Test the power supply GUI with a mock connection.

### Requirements

- PyQt6 - For GUI
- No hardware required

### Configuration

No hardware required.

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

Not executed in CI: launches a Qt GUI and needs PyQt6 plus a display. It is
compile-checked only -- verify it manually after changes.
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
- No hardware required

### Configuration

No hardware required.

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
- No hardware required

### Configuration

No hardware required.

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
- No hardware required

### Configuration

No hardware required.

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
- No hardware required

### Configuration

No hardware required.

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

import sys
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

    This requires Ollama or LM Studio to be running locally. An unreachable
    service is handled explicitly below -- test_connection() returns False
    rather than raising, so AI features are skipped gracefully. Anything
    else that goes wrong here is a real bug and is left to propagate rather
    than being reported as just another "AI unavailable" case.
    """
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
        # generate() returns False on any internal failure (it logs and
        # swallows the real exception -- see scpi_control's markdown_generator.py).
        # Markdown is this example's primary, always-attempted deliverable, so
        # a False here is a real failure, not an optional-dependency skip.
        print("    [FAILED] Failed to generate Markdown report", file=sys.stderr)
        raise SystemExit(1)

    # Generate PDF report (if available)
    print("  - Generating PDF report...")
    try:
        pdf_path = output_dir / "example_report.pdf"
        pdf_generator = PDFReportGenerator()

        if pdf_generator.generate(report, pdf_path):
            print(f"    [OK] PDF report saved: {pdf_path}")
        else:
            # Same reasoning as the Markdown case above: reportlab being
            # missing is the legitimate "optional" outcome and is handled
            # below by the ImportError branch, not here. Once reportlab is
            # importable, PDFReportGenerator existing and generate() still
            # returning False means real report generation failed.
            print("    [FAILED] Failed to generate PDF report", file=sys.stderr)
            raise SystemExit(1)
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

- scpi_control - Core library
- None -- runs on the built-in mock; `--host <ip>` for real hardware

### Configuration

None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.

### Usage

```bash
python examples/vector_graphics_xy_mode.py
```

### Source Code

```python
"""Vector Graphics on Oscilloscope using XY Mode

This example demonstrates how to use the oscilloscope as a vector display by
generating waveforms for XY mode: circles, polygons, a star, Lissajous
figures, text, and rotation-animation frames, all saved as CSV waveform
files ready for an external AWG/DAC.

To actually see these shapes on a scope, feed the generated *_x.csv /
*_y.csv pairs into an external AWG (or the scope's own built-in AWG) wired
into the scope's X and Y channels, then enable XY mode on the display. This
script itself only talks to the oscilloscope (to configure its channels for
XY display) and generates/saves waveform data -- it never drives an AWG, so
it runs to completion with no AWG attached.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network. Text-shape
generation additionally needs the 'fun' extras
(pip install "SCPI-Instrument-Control[fun]") -- shapely, Pillow,
svgpathtools; if they are not installed, that one demo is skipped with a
warning and everything else still runs.

Expected output: connection/device info, XY-mode configuration echoed to the
console, progress messages for each shape/demo, and CSV waveform file pairs
(<name>_x.csv, <name>_y.csv) written under vector_waveforms/ in the current
directory for the circle, square, star, triangle, 3 Lissajous figures, 24
rotating-star animation frames, and a composite smiley face -- plus text
"HELLO" if the 'fun' extras are installed.
"""

import argparse
import os

import numpy as np

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection
from scpi_control.vector_graphics import Shape, VectorPath

SAMPLE_RATE = 1e6  # 1 MSa/s for AWG
DURATION = 0.1  # 100ms per frame
OUTPUT_DIR = "vector_waveforms"


def _connect(host):
    """Return a mock connection for --host mock, or None to use a real socket."""
    if host != "mock":
        return None
    return MockConnection("mock", channel_states={1: True, 2: True})


def main():
    """Main demonstration of vector graphics features."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' for the built-in mock scope (default: mock)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Oscilloscope Vector Graphics Demo")
    print("=" * 60)
    print()
    print("This demo generates waveform data for XY mode display.")
    print("Load the generated files into your AWG to see the shapes!")
    print()

    # Connect to oscilloscope
    print(f"Connecting to {args.host}...")
    scope = Oscilloscope(args.host, connection=_connect(args.host))
    scope.connect()
    print(f"Connected: {scope.identify()}")
    print()

    try:
        # Initialize vector display
        print("Initializing vector display (CH1=X, CH2=Y)...")
        display = scope.vector_display
        display.enable_xy_mode(voltage_scale=1.0)
        print("[OK] XY mode configured")
        print()

        # Create output directory
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
        except ImportError as e:
            # Text rendering needs the optional 'fun' extras (shapely, Pillow,
            # svgpathtools); everything else in this demo works without them.
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

    finally:
        # Cleanup
        scope.disconnect()


if __name__ == "__main__":
    main()
```

---

## Next Steps

Review the [API Reference](../api/oscilloscope.md) for detailed documentation of all available methods and properties.

See also:

- [User Guide](../user-guide/basic-usage.md) - Conceptual documentation
- [API Reference](../api/oscilloscope.md) - Detailed API documentation
- [Getting Started](../getting-started/quickstart.md) - Quick start guide
