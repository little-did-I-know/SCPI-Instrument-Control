# Advanced Features

This guide covers advanced features including FFT analysis, math channels, automation, screen capture, and more.

## FFT Analysis

Fast Fourier Transform (FFT) analysis converts time-domain signals to frequency domain, revealing frequency components.

### Basic FFT

```python
from scpi_control import Oscilloscope

with Oscilloscope('192.168.1.100') as scope:
    # Capture waveform
    scope.channel1.enabled = True
    waveform = scope.get_waveform(1)

    # Compute FFT
    fft_result = scope.fft_analyzer.compute_fft(waveform)

    print(f"Frequency range: DC to {fft_result.frequency[-1]/1e6:.2f} MHz")
    print(f"Frequency bins: {len(fft_result.frequency)}")
    print(f"Window: {fft_result.window}")

    # Access FFT data
    frequencies = fft_result.frequency  # Hz
    magnitude = fft_result.magnitude    # dB or linear
    phase = fft_result.phase            # radians
```

### Window Functions

Different window functions affect spectral leakage and frequency resolution:

```python
# Available window functions:
# - rectangular (no window)
# - hanning (default, good general purpose)
# - hamming (similar to hanning)
# - blackman (low sidelobes)
# - bartlett (triangular)
# - flattop (accurate amplitude)

# Hanning window (default)
fft_hanning = scope.fft_analyzer.compute_fft(waveform, window="hanning")

# Blackman window (lower sidelobes, less spectral leakage)
fft_blackman = scope.fft_analyzer.compute_fft(waveform, window="blackman")

# Flat-top window (best for amplitude accuracy)
fft_flattop = scope.fft_analyzer.compute_fft(waveform, window="flattop")

# Rectangular (no windowing, maximum resolution)
fft_rect = scope.fft_analyzer.compute_fft(waveform, window="rectangular")
```

**Window Selection Guide:**

- **Hanning**: General purpose, good for most signals
- **Blackman**: Low spectral leakage, good for finding weak signals
- **Flat-top**: Accurate amplitude measurements
- **Rectangular**: Maximum frequency resolution, but more spectral leakage

### FFT Output Options

```python
# Magnitude in dB (default)
fft_db = scope.fft_analyzer.compute_fft(waveform, output_db=True)

# Magnitude linear
fft_linear = scope.fft_analyzer.compute_fft(waveform, output_db=False)

# Disable detrending (keep DC component)
fft_with_dc = scope.fft_analyzer.compute_fft(waveform, detrend=False)
```

### Finding Peak Frequencies

```python
# Get the dominant frequency
fft_result = scope.fft_analyzer.compute_fft(waveform)

# Find top peak
peaks = fft_result.get_peak_frequency(num_peaks=1)
if peaks:
    freq, mag = peaks[0]
    print(f"Dominant frequency: {freq/1e3:.2f} kHz at {mag:.1f} dB")

# Find multiple peaks
peaks = fft_result.get_peak_frequency(num_peaks=5)
for i, (freq, mag) in enumerate(peaks, 1):
    print(f"Peak {i}: {freq/1e3:.2f} kHz at {mag:.1f} dB")
```

### Plotting FFT

```python
import matplotlib.pyplot as plt

waveform = scope.get_waveform(1)
fft_result = scope.fft_analyzer.compute_fft(waveform)

# Plot magnitude spectrum
plt.figure(figsize=(12, 6))
plt.subplot(2, 1, 1)
plt.plot(fft_result.frequency/1e3, fft_result.magnitude)
plt.xlabel("Frequency (kHz)")
plt.ylabel("Magnitude (dB)")
plt.title("FFT Magnitude Spectrum")
plt.grid(True, alpha=0.3)

# Plot phase spectrum
plt.subplot(2, 1, 2)
plt.plot(fft_result.frequency/1e3, fft_result.phase)
plt.xlabel("Frequency (kHz)")
plt.ylabel("Phase (radians)")
plt.title("FFT Phase Spectrum")
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
```

### Power Spectral Density

For noisy signals, use Welch's method for better averaging:

```python
# Compute power spectral density
frequencies, psd = scope.fft_analyzer.compute_power_spectrum(
    waveform,
    window="hanning",
    nperseg=256  # Segment length
)

# Plot PSD
plt.figure(figsize=(12, 6))
plt.semilogy(frequencies/1e3, psd)
plt.xlabel("Frequency (kHz)")
plt.ylabel("Power Spectral Density (V²/Hz)")
plt.title("Power Spectral Density")
plt.grid(True, alpha=0.3)
plt.show()
```

### Spectrogram (Time-Frequency Analysis)

Analyze how frequency content changes over time:

```python
# Compute spectrogram
frequencies, times, spectrogram = scope.fft_analyzer.compute_spectrogram(
    waveform,
    window="hanning",
    nperseg=256
)

# Plot spectrogram
plt.figure(figsize=(12, 6))
plt.pcolormesh(times*1e3, frequencies/1e3, 10*np.log10(spectrogram), shading='gouraud')
plt.ylabel("Frequency (kHz)")
plt.xlabel("Time (ms)")
plt.title("Spectrogram")
plt.colorbar(label="Power (dB)")
plt.show()
```

## Math Channels

Math channels perform operations on captured waveforms.

### Accessing Math Channels

```python
with Oscilloscope('192.168.1.100') as scope:
    # Access math channels
    math1 = scope.math1
    math2 = scope.math2

    # Math channels become available after connection
    if math1 is not None:
        print("Math channel 1 available")
```

### Common Math Operations

```python
# Addition: C1 + C2
scope.math1.set_operation("C1+C2")

# Subtraction: C1 - C2
scope.math1.set_operation("C1-C2")

# Multiplication: C1 * C2
scope.math1.set_operation("C1*C2")

# Division: C1 / C2
scope.math1.set_operation("C1/C2")

# FFT of C1
scope.math1.set_operation("FFT(C1)")

# Integral of C1
scope.math1.set_operation("INTG(C1)")

# Derivative of C1
scope.math1.set_operation("DIFF(C1)")
```

**Note:** Exact syntax depends on oscilloscope model. Refer to your oscilloscope's SCPI programming manual for supported operations.

## Automation Classes

The automation module provides high-level classes for common data collection scenarios.

### DataCollector

Simplified interface for waveform capture:

```python
from scpi_control.automation import DataCollector

with DataCollector('192.168.1.100') as collector:
    # Capture single acquisition from multiple channels
    waveforms = collector.capture_single(channels=[1, 2])

    # Save data
    collector.save_data(waveforms, "capture_001", format="npz")

    # Capture batch of waveforms
    batch = collector.capture_batch(
        channels=[1, 2],
        count=10,
        delay=0.1  # 100ms between captures
    )

    print(f"Captured {len(batch)} acquisitions")
```

### TriggerWaitCollector

Wait for specific trigger events:

```python
from scpi_control.automation import TriggerWaitCollector

with TriggerWaitCollector('192.168.1.100') as tc:
    # Configure trigger
    tc.collector.scope.trigger.source = "C1"
    tc.collector.scope.trigger.slope = "POS"
    tc.collector.scope.trigger.level = 2.0
    tc.collector.scope.trigger.mode = "SINGLE"

    # Wait for trigger event
    waveforms = tc.wait_for_trigger(
        channels=[1, 2],
        max_wait=30.0,           # Maximum wait time (seconds)
        save_on_trigger=True,     # Automatically save when triggered
        output_dir="captures"     # Output directory
    )

    if waveforms:
        print("Event captured and saved!")
    else:
        print("Timeout - no event detected")
```

### Batch Data Collection

```python
from scpi_control.automation import DataCollector

with DataCollector('192.168.1.100') as collector:
    # Configure oscilloscope
    collector.scope.channel1.enabled = True
    collector.scope.channel2.enabled = True
    collector.scope.trigger.mode = "AUTO"

    # Collect 100 waveforms
    all_waveforms = []
    for i in range(100):
        waveforms = collector.capture_single([1, 2])
        all_waveforms.append(waveforms)

        # Save every 10 captures
        if (i + 1) % 10 == 0:
            collector.save_data(
                waveforms,
                f"batch_{i+1:03d}",
                format="npz"
            )
            print(f"Saved batch {i+1}")

    print(f"Collected {len(all_waveforms)} acquisitions")
```

## Screen Capture

Capture oscilloscope screen images.

### Capture Screen

```python
with Oscilloscope('192.168.1.100') as scope:
    # Capture screen as PNG
    image_data = scope.screen_capture.capture_screen(format="PNG")

    # Save to file
    with open("screen.png", "wb") as f:
        f.write(image_data)

    print("Screen captured to screen.png")

    # Other formats (model-dependent)
    # - "BMP": Windows Bitmap
    # - "JPEG": JPEG compressed
    # - "TIFF": TIFF format
```

### Automated Screen Capture

```python
import time

# Capture screens periodically
for i in range(10):
    image_data = scope.screen_capture.capture_screen(format="PNG")

    with open(f"screen_{i:03d}.png", "wb") as f:
        f.write(image_data)

    print(f"Captured screen {i+1}/10")
    time.sleep(5)  # Wait 5 seconds
```

## Reference Waveforms

Save and load reference waveforms in oscilloscope memory.

### Save Reference Waveform

```python
from scpi_control.reference_waveform import save_reference

# Capture current waveform
waveform = scope.get_waveform(1)

# Save to oscilloscope as reference
save_reference(scope, waveform, ref_number=1)  # RefA
# ref_number: 1=RefA, 2=RefB, 3=RefC, 4=RefD

print("Reference waveform saved to RefA")
```

### Load Reference Waveform

```python
from scpi_control.reference_waveform import load_reference

# Load reference from oscilloscope
ref_waveform = load_reference(scope, ref_number=1)  # RefA

# Compare with current measurement
current = scope.get_waveform(1)

import numpy as np
diff = np.abs(current.voltage - ref_waveform.voltage)
max_diff = np.max(diff)
print(f"Maximum difference from reference: {max_diff:.3f} V")
```

## Vector Graphics (XY Mode)

Draw shapes and graphics using XY mode (requires 'fun' extras).

### Installation

```bash
pip install "SCPI-Instrument-Control[fun]"
```

### Enable XY Mode

```python
with Oscilloscope('192.168.1.100') as scope:
    # Enable XY mode
    scope.vector_display.enable_xy_mode()

    # Configure channels for XY
    # Channel 1 = X axis
    # Channel 2 = Y axis
    scope.channel1.enabled = True
    scope.channel2.enabled = True
```

### Draw Shapes

```python
from scpi_control.vector_graphics import Shape

# Create shapes
circle = Shape.circle(radius=0.8, center=(0, 0))
square = Shape.rectangle(width=1.0, height=1.0)
line = Shape.line(start=(-0.5, -0.5), end=(0.5, 0.5))

# Draw shape
scope.vector_display.draw(circle)

# Draw multiple shapes
scope.vector_display.draw([circle, square, line])
```

### Custom Shapes

```python
# Define custom shape from points
import numpy as np

# Create star shape
angles = np.linspace(0, 2*np.pi, 11, endpoint=True)
radii = np.array([1.0, 0.4] * 5 + [1.0])
x = radii * np.cos(angles)
y = radii * np.sin(angles)

custom_shape = Shape.from_points(x, y)
scope.vector_display.draw(custom_shape)
```

### Animations

```python
import time
import numpy as np

# Rotating shape
for angle in np.linspace(0, 2*np.pi, 36):
    # Rotate circle
    x = 0.5 * np.cos(angle)
    y = 0.5 * np.sin(angle)

    circle = Shape.circle(radius=0.3, center=(x, y))
    scope.vector_display.draw(circle)

    time.sleep(0.05)
```

## Protocol Decoding

Some oscilloscope models support protocol decoding for I2C, SPI, UART, etc.

### Check Support

```python
# Check if protocol decoding is supported
if scope.model_capability.has_protocol_decoder:
    print("Protocol decoding supported")
```

### Enable Protocol Decoder

```python
# Configure I2C decoder (example)
scope.write("DECODE:MODE I2C")
scope.write("DECODE:I2C:SCL C1")  # Clock on channel 1
scope.write("DECODE:I2C:SDA C2")  # Data on channel 2
scope.write("DECODE:DISPLAY ON")

# Decode will appear on oscilloscope display
```

**Note:** Protocol decoding features vary by model. Consult your oscilloscope's programming manual for specific SCPI commands.

## Advanced Waveform Processing

### Signal Filtering

```python
from scipy import signal as sp_signal

waveform = scope.get_waveform(1)

# Low-pass filter
sos = sp_signal.butter(10, 1e6, 'low', fs=waveform.sample_rate, output='sos')
filtered = sp_signal.sosfilt(sos, waveform.voltage)

# High-pass filter
sos = sp_signal.butter(10, 1e6, 'high', fs=waveform.sample_rate, output='sos')
filtered = sp_signal.sosfilt(sos, waveform.voltage)

# Band-pass filter
sos = sp_signal.butter(10, [1e6, 10e6], 'bandpass', fs=waveform.sample_rate, output='sos')
filtered = sp_signal.sosfilt(sos, waveform.voltage)
```

### Savitzky-Golay Smoothing

```python
from scipy import signal as sp_signal

# Smooth waveform using Savitzky-Golay filter
smoothed = sp_signal.savgol_filter(
    waveform.voltage,
    window_length=51,  # Must be odd
    polyorder=3
)
```

### Peak Detection

```python
from scipy import signal as sp_signal

# Find peaks
peaks, properties = sp_signal.find_peaks(
    waveform.voltage,
    height=0.5,      # Minimum height
    distance=100,    # Minimum distance between peaks
    prominence=0.2   # Minimum prominence
)

print(f"Found {len(peaks)} peaks")
for i, peak_idx in enumerate(peaks):
    peak_time = waveform.time[peak_idx]
    peak_voltage = waveform.voltage[peak_idx]
    print(f"Peak {i+1}: {peak_voltage:.3f} V at {peak_time*1e6:.3f} µs")
```

### Cross-Correlation

Compare two waveforms:

```python
# Capture two channels
wf1 = scope.get_waveform(1)
wf2 = scope.get_waveform(2)

# Compute cross-correlation
correlation = np.correlate(wf1.voltage, wf2.voltage, mode='full')

# Find time delay
max_corr_idx = np.argmax(correlation)
center = len(wf1.voltage) - 1
delay_samples = max_corr_idx - center
delay_time = delay_samples / wf1.sample_rate

print(f"Time delay: {delay_time*1e9:.2f} ns")
```

## Statistics and Averaging

### Waveform Averaging

```python
# Capture multiple waveforms and average
num_averages = 10
waveforms = []

for i in range(num_averages):
    wf = scope.get_waveform(1)
    waveforms.append(wf.voltage)

# Average
averaged = np.mean(waveforms, axis=0)

# Standard deviation
std_dev = np.std(waveforms, axis=0)

print(f"Averaged {num_averages} waveforms")
print(f"Noise reduction: {20*np.log10(np.sqrt(num_averages)):.1f} dB")
```

### Histogram Analysis

```python
import matplotlib.pyplot as plt

waveform = scope.get_waveform(1)

# Create histogram
counts, bins, _ = plt.hist(waveform.voltage, bins=100)

plt.xlabel("Voltage (V)")
plt.ylabel("Count")
plt.title("Voltage Histogram")
plt.grid(True, alpha=0.3)
plt.show()

# Statistical analysis
mean_v = np.mean(waveform.voltage)
std_v = np.std(waveform.voltage)
print(f"Mean: {mean_v:.3f} V")
print(f"Std Dev: {std_v:.3f} V")
```

## Remote Operation Tips

### Network Performance

```python
# Increase timeout for slow networks
scope = Oscilloscope('192.168.1.100', timeout=10.0)

# For large data transfers
scope = Oscilloscope('192.168.1.100', timeout=30.0)
```

### Connection Pooling

For repeated operations, maintain connection:

```python
# Good - reuse connection
with Oscilloscope('192.168.1.100') as scope:
    for i in range(100):
        waveform = scope.get_waveform(1)
        # Process waveform

# Bad - reconnecting each time
for i in range(100):
    with Oscilloscope('192.168.1.100') as scope:
        waveform = scope.get_waveform(1)
```

### Error Recovery

```python
from scpi_control import SiglentTimeoutError, SiglentConnectionError
import time

MAX_RETRIES = 3

for attempt in range(MAX_RETRIES):
    try:
        waveform = scope.get_waveform(1)
        break  # Success
    except SiglentTimeoutError:
        print(f"Timeout on attempt {attempt + 1}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(1)
            # Retry
        else:
            raise
    except SiglentConnectionError as e:
        print(f"Connection error: {e}")
        # Reconnect
        scope.disconnect()
        time.sleep(2)
        scope.connect()
```

## Complete Advanced Example

Here's a comprehensive example combining multiple advanced features:

```python
from scpi_control import Oscilloscope
from scpi_control.automation import DataCollector
import numpy as np
import matplotlib.pyplot as plt

SCOPE_IP = '192.168.1.100'

# Collect and analyze data
with DataCollector(SCOPE_IP) as collector:
    print("Configuring oscilloscope...")

    # Configure channels
    collector.scope.channel1.enabled = True
    collector.scope.channel1.voltage_scale = 1.0
    collector.scope.trigger.mode = "NORMAL"
    collector.scope.trigger.source = "C1"
    collector.scope.trigger.level = 0.0

    # Capture waveform
    print("Capturing waveform...")
    waveforms = collector.capture_single([1])
    waveform = waveforms[1]

    # Time-domain analysis
    print("\nTime-domain analysis:")
    vpp = np.ptp(waveform.voltage)
    vrms = np.sqrt(np.mean(waveform.voltage**2))
    print(f"Vpp: {vpp:.3f} V")
    print(f"Vrms: {vrms:.3f} V")

    # Frequency-domain analysis
    print("\nFrequency-domain analysis:")
    fft_result = collector.scope.fft_analyzer.compute_fft(waveform)

    peaks = fft_result.get_peak_frequency(num_peaks=3)
    for i, (freq, mag) in enumerate(peaks, 1):
        print(f"Peak {i}: {freq/1e3:.2f} kHz at {mag:.1f} dB")

    # Create comprehensive plot
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))

    # Time domain
    axes[0].plot(waveform.time*1e3, waveform.voltage)
    axes[0].set_xlabel("Time (ms)")
    axes[0].set_ylabel("Voltage (V)")
    axes[0].set_title(f"Time Domain - Vpp={vpp:.3f}V, Vrms={vrms:.3f}V")
    axes[0].grid(True, alpha=0.3)

    # Frequency domain
    axes[1].plot(fft_result.frequency/1e3, fft_result.magnitude)
    axes[1].set_xlabel("Frequency (kHz)")
    axes[1].set_ylabel("Magnitude (dB)")
    axes[1].set_title("Frequency Domain (FFT)")
    axes[1].grid(True, alpha=0.3)

    # Histogram
    axes[2].hist(waveform.voltage, bins=100, edgecolor='black')
    axes[2].set_xlabel("Voltage (V)")
    axes[2].set_ylabel("Count")
    axes[2].set_title("Voltage Distribution")
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("analysis_complete.png", dpi=150)
    print("\nPlot saved to analysis_complete.png")

    # Save data
    collector.save_data(waveforms, "waveform_data", format="npz")
    print("Data saved to waveform_data.npz")

    plt.show()
```

## Next Steps

You've completed the User Guide! Here are some resources for further learning:

- [API Reference](../api/oscilloscope.md) - Detailed API documentation
- [Examples](../examples/beginner.md) - Real-world usage examples
- [GUI Guide](../gui/overview.md) - Learn about the GUI application
- [GitHub Repository](https://github.com/little-did-I-know/SCPI-Instrument-Control) - Source code and examples
