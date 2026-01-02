# Waveform Capture

This guide covers advanced waveform acquisition techniques, data handling, and saving options.

## Basic Waveform Acquisition

### Single Channel Capture

The simplest way to capture a waveform:

```python
from siglent import Oscilloscope

with Oscilloscope('192.168.1.100') as scope:
    # Configure channel
    scope.channel1.enabled = True
    scope.channel1.voltage_scale = 1.0

    # Capture waveform
    waveform = scope.get_waveform(channel=1)

    print(f"Captured {len(waveform)} samples")
    print(f"Sample rate: {waveform.sample_rate/1e9:.3f} GSa/s")
```

### Multi-Channel Capture

Capture from multiple channels simultaneously:

```python
# Enable channels
scope.channel1.enabled = True
scope.channel2.enabled = True
scope.channel3.enabled = True

# Capture all enabled channels at once
waveforms = scope.get_waveforms()

# Process each waveform
for wf in waveforms:
    print(f"Channel {wf.channel}: {len(wf.voltage)} samples")
    print(f"  Voltage range: {wf.voltage.min():.3f} to {wf.voltage.max():.3f} V")
```

!!! tip "Performance"
    Using `get_waveforms()` is more efficient than calling `get_waveform()` multiple times as it captures all channels in a single operation.

### Specific Channel Selection

You can also specify which channels to capture:

```python
# Capture only channels 1 and 3
waveforms = scope.get_waveforms(channels=[1, 3])

# Access specific waveform
wf1 = waveforms[0]  # Channel 1
wf3 = waveforms[1]  # Channel 3
```

## Waveform Data Structure

### WaveformData Object

Captured waveforms are returned as `WaveformData` objects with the following attributes:

```python
waveform = scope.get_waveform(1)

# Data arrays (numpy arrays)
times = waveform.time           # Time values in seconds
voltages = waveform.voltage     # Voltage values in volts

# Metadata
channel = waveform.channel      # Source channel number
sample_rate = waveform.sample_rate      # Samples/second
record_length = waveform.record_length  # Number of samples
timebase = waveform.timebase            # Seconds/division
voltage_scale = waveform.voltage_scale  # Volts/division
voltage_offset = waveform.voltage_offset # Offset in volts
```

### Array Operations

Since waveform data uses numpy arrays, you can perform vectorized operations:

```python
import numpy as np

waveform = scope.get_waveform(1)

# Statistical operations
mean_voltage = np.mean(waveform.voltage)
std_voltage = np.std(waveform.voltage)
peak_to_peak = np.ptp(waveform.voltage)  # max - min

# Find peaks
max_voltage = np.max(waveform.voltage)
max_index = np.argmax(waveform.voltage)
max_time = waveform.time[max_index]

print(f"Peak voltage: {max_voltage:.3f} V at t={max_time*1e6:.3f} µs")

# Signal processing
from scipy import signal

# Apply low-pass filter
filtered = signal.savgol_filter(waveform.voltage, window_length=51, polyorder=3)

# Find zero crossings
zero_crossings = np.where(np.diff(np.sign(waveform.voltage)))[0]
print(f"Found {len(zero_crossings)} zero crossings")
```

## Saving Waveform Data

### CSV Format

Save as CSV for easy import into Excel or other tools:

```python
waveform = scope.get_waveform(1)

# Save using WaveformData method
waveform.save_csv("waveform.csv")

# Or using the waveform module
scope.waveform.save_waveform(waveform, "waveform.csv", format="CSV")
```

CSV format:
```
Time (s),Voltage (V)
-0.000070,0.125
-0.000069,0.128
...
```

### NPZ Format (NumPy)

NPZ format preserves all metadata and is ideal for Python-to-Python workflows:

```python
# Save in NumPy compressed format
waveform.save_npz("waveform.npz")

# Load back
import numpy as np
data = np.load("waveform.npz")
time = data['time']
voltage = data['voltage']
sample_rate = float(data['sample_rate'])
```

### MAT Format (MATLAB)

For MATLAB compatibility:

```python
# Requires scipy
waveform.save_mat("waveform.mat")
```

In MATLAB:
```matlab
data = load('waveform.mat');
plot(data.time, data.voltage);
```

### HDF5 Format

For large datasets with compression:

```python
# Requires h5py
waveform.save_hdf5("waveform.h5")

# Load back
import h5py
with h5py.File("waveform.h5", 'r') as f:
    time = f['time'][:]
    voltage = f['voltage'][:]
    metadata = dict(f.attrs)
```

## Plotting Waveforms

### Basic Plot with Matplotlib

```python
import matplotlib.pyplot as plt

waveform = scope.get_waveform(1)

plt.figure(figsize=(12, 6))
plt.plot(waveform.time * 1e6, waveform.voltage, linewidth=0.5)
plt.xlabel("Time (µs)")
plt.ylabel("Voltage (V)")
plt.title(f"Channel {waveform.channel} Waveform")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("waveform.png", dpi=150)
plt.show()
```

### Multi-Channel Plot

```python
import matplotlib.pyplot as plt

waveforms = scope.get_waveforms()

fig, axes = plt.subplots(len(waveforms), 1, figsize=(12, 3*len(waveforms)))
if len(waveforms) == 1:
    axes = [axes]

for ax, wf in zip(axes, waveforms):
    ax.plot(wf.time * 1e6, wf.voltage, linewidth=0.5)
    ax.set_xlabel("Time (µs)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title(f"Channel {wf.channel}")
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
```

### Live Plotting

For continuous visualization:

```python
import matplotlib.pyplot as plt
import matplotlib.animation as animation

fig, ax = plt.subplots(figsize=(12, 6))
line, = ax.plot([], [], linewidth=0.5)

ax.set_xlabel("Time (µs)")
ax.set_ylabel("Voltage (V)")
ax.set_title("Live Waveform")
ax.grid(True, alpha=0.3)

def update(frame):
    waveform = scope.get_waveform(1)
    line.set_data(waveform.time * 1e6, waveform.voltage)
    ax.relim()
    ax.autoscale_view()
    return line,

ani = animation.FuncAnimation(fig, update, interval=100, blit=True)
plt.show()
```

## Advanced Capture Techniques

### Continuous Capture Loop

Capture waveforms continuously:

```python
import time

capture_count = 100
waveforms_list = []

scope.channel1.enabled = True
scope.trigger.mode = "AUTO"

for i in range(capture_count):
    waveform = scope.get_waveform(1)
    waveforms_list.append(waveform)
    print(f"Captured {i+1}/{capture_count}")
    time.sleep(0.1)  # Small delay between captures

print(f"Captured {len(waveforms_list)} waveforms total")
```

### Trigger-Based Capture

Wait for specific events before capturing:

```python
# Configure for single trigger
scope.trigger.mode = "SINGLE"
scope.trigger.source = "C1"
scope.trigger.level = 1.0
scope.trigger.slope = "POS"

# Arm trigger
scope.trigger_single()

# Wait for trigger
import time
timeout = 5.0
start = time.time()
while (time.time() - start) < timeout:
    status = scope.query(":TRIG:STAT?").strip()
    if status == "Stop":
        # Trigger occurred, capture waveform
        waveform = scope.get_waveform(1)
        print("Triggered! Captured waveform.")
        break
    time.sleep(0.05)
else:
    print("Trigger timeout - no event detected")
```

### Batch Capture with Automation

Use the automation module for complex capture scenarios:

```python
from siglent.automation import DataCollector

with DataCollector('192.168.1.100') as collector:
    # Capture single waveform from multiple channels
    waveforms = collector.capture_single(channels=[1, 2])

    # Save to files
    collector.save_data(waveforms, "capture_001", format="npz")

    # Capture multiple acquisitions
    batch = collector.capture_batch(
        channels=[1, 2],
        count=10,
        delay=0.1  # 100ms between captures
    )

    print(f"Captured {len(batch)} acquisitions")
```

### Trigger Wait Collector

For event-driven capture:

```python
from siglent.automation import TriggerWaitCollector

with TriggerWaitCollector('192.168.1.100') as tc:
    # Configure trigger
    tc.collector.scope.trigger.source = "C1"
    tc.collector.scope.trigger.slope = "POS"
    tc.collector.scope.trigger.level = 2.0

    # Wait for trigger (max 30 seconds)
    waveforms = tc.wait_for_trigger(
        channels=[1, 2],
        max_wait=30.0,
        save_on_trigger=True,
        output_dir="trigger_captures"
    )

    if waveforms:
        print("Trigger captured successfully!")
    else:
        print("No trigger detected within timeout")
```

## Memory Depth and Sample Rate

### Understanding the Relationship

The oscilloscope's memory depth and timebase determine the sample rate:

```python
waveform = scope.get_waveform(1)

print(f"Record length: {waveform.record_length:,} samples")
print(f"Sample rate: {waveform.sample_rate/1e9:.3f} GSa/s")
print(f"Timebase: {waveform.timebase*1e6:.3f} µs/div")

# Total time captured
total_time = waveform.record_length / waveform.sample_rate
print(f"Total time: {total_time*1e3:.3f} ms")

# Time resolution
time_resolution = 1.0 / waveform.sample_rate
print(f"Time resolution: {time_resolution*1e9:.3f} ns")
```

### Optimizing Memory Depth

```python
# For long captures, adjust timebase
scope.timebase = 1e-3  # 1 ms/div = 14 ms total (14 divisions)

# For high-resolution captures, use shorter timebase
scope.timebase = 1e-6  # 1 µs/div = 14 µs total

# Check actual sample rate achieved
waveform = scope.get_waveform(1)
print(f"Actual sample rate: {waveform.sample_rate/1e9:.3f} GSa/s")
```

## Data Processing Examples

### Calculate RMS Value

```python
import numpy as np

waveform = scope.get_waveform(1)
rms = np.sqrt(np.mean(waveform.voltage**2))
print(f"RMS voltage: {rms:.3f} V")
```

### Find Frequency from Time Domain

```python
import numpy as np

waveform = scope.get_waveform(1)

# Find zero crossings with positive slope
zero_crossings = []
for i in range(len(waveform.voltage) - 1):
    if waveform.voltage[i] <= 0 and waveform.voltage[i+1] > 0:
        zero_crossings.append(waveform.time[i])

if len(zero_crossings) >= 2:
    # Calculate period from average of crossing intervals
    periods = np.diff(zero_crossings)
    avg_period = np.mean(periods)
    frequency = 1.0 / avg_period
    print(f"Frequency: {frequency/1e3:.2f} kHz")
```

### Downsample Waveform

For large datasets, you may want to downsample:

```python
import numpy as np

waveform = scope.get_waveform(1)

# Downsample by factor of 10
factor = 10
time_ds = waveform.time[::factor]
voltage_ds = waveform.voltage[::factor]

print(f"Original: {len(waveform)} samples")
print(f"Downsampled: {len(time_ds)} samples")

# Or use decimation (includes filtering)
from scipy import signal
voltage_dec = signal.decimate(waveform.voltage, factor, ftype='fir')
time_dec = waveform.time[::factor][:len(voltage_dec)]
```

## Reference Waveforms

### Save as Reference

Save a waveform to the oscilloscope's internal memory as a reference:

```python
from siglent.reference_waveform import save_reference

# Capture current waveform
waveform = scope.get_waveform(1)

# Save as reference waveform in oscilloscope memory
save_reference(scope, waveform, ref_number=1)

# Reference will appear on oscilloscope display as RefA
```

### Load Reference Waveform

```python
from siglent.reference_waveform import load_reference

# Load reference waveform from oscilloscope
ref_waveform = load_reference(scope, ref_number=1)

print(f"Reference has {len(ref_waveform)} samples")
```

## Performance Tips

!!! tip "Capture Speed"
    - Disable channels you don't need
    - Use appropriate timebase (shorter = faster transfer)
    - Use `get_waveforms()` for multi-channel instead of multiple `get_waveform()` calls
    - Consider using automation classes for complex workflows

!!! tip "Memory Usage"
    - Each waveform can be several MB (140,000 samples × 2 arrays × 8 bytes ≈ 2.2 MB)
    - Downsample if you don't need full resolution
    - Save to disk and free memory for long captures
    - Use NPZ format with compression for efficient storage

!!! tip "Data Quality"
    - Always check `sample_rate` to ensure you're capturing at expected rate
    - Verify `record_length` matches your expectations
    - Use appropriate timebase for your signal frequency
    - Enable bandwidth limiting to reduce high-frequency noise

## Troubleshooting

### Empty or Corrupted Waveforms

```python
waveform = scope.get_waveform(1)

# Check if data is valid
if len(waveform) == 0:
    print("ERROR: No data captured")
elif waveform.sample_rate is None:
    print("ERROR: Invalid sample rate")
else:
    print(f"OK: {len(waveform)} samples at {waveform.sample_rate/1e9:.3f} GSa/s")
```

### Timeout Issues

```python
# Increase timeout for large captures
scope = Oscilloscope('192.168.1.100', timeout=30.0)  # 30 second timeout

try:
    waveform = scope.get_waveform(1)
except SiglentTimeoutError:
    print("Capture timed out - try reducing memory depth or increasing timeout")
```

### Channel Not Enabled

```python
# Verify channel is enabled before capture
if not scope.channel1.enabled:
    print("Warning: Channel 1 is not enabled!")
    scope.channel1.enabled = True

waveform = scope.get_waveform(1)
```

## Complete Example

Here's a complete waveform capture, processing, and visualization example:

```python
from siglent import Oscilloscope
import numpy as np
import matplotlib.pyplot as plt

SCOPE_IP = '192.168.1.100'

with Oscilloscope(SCOPE_IP) as scope:
    # Configure acquisition
    scope.channel1.enabled = True
    scope.channel1.voltage_scale = 1.0
    scope.channel1.coupling = "DC"
    scope.trigger.mode = "AUTO"
    scope.timebase = 1e-3  # 1 ms/div

    # Capture waveform
    print("Capturing waveform...")
    waveform = scope.get_waveform(1)

    # Display information
    print(f"Samples: {len(waveform):,}")
    print(f"Sample rate: {waveform.sample_rate/1e9:.3f} GSa/s")
    print(f"Duration: {waveform.time[-1]*1e3:.3f} ms")

    # Calculate statistics
    vpp = np.ptp(waveform.voltage)
    vrms = np.sqrt(np.mean(waveform.voltage**2))
    vmean = np.mean(waveform.voltage)

    print(f"\nStatistics:")
    print(f"  Vpp: {vpp:.3f} V")
    print(f"  Vrms: {vrms:.3f} V")
    print(f"  Vmean: {vmean:.3f} V")

    # Save data
    print("\nSaving data...")
    waveform.save_csv("waveform.csv")
    waveform.save_npz("waveform.npz")
    print("Data saved to waveform.csv and waveform.npz")

    # Plot
    print("Plotting...")
    plt.figure(figsize=(12, 6))
    plt.plot(waveform.time * 1e3, waveform.voltage, linewidth=0.5)
    plt.xlabel("Time (ms)")
    plt.ylabel("Voltage (V)")
    plt.title(f"Channel {waveform.channel} - Vpp={vpp:.3f}V, Vrms={vrms:.3f}V")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("waveform.png", dpi=150)
    print("Plot saved to waveform.png")
    plt.show()
```

## Next Steps

- [Measurements](measurements.md) - Automated measurements and statistics
- [Trigger Control](trigger-control.md) - Advanced trigger configuration
- [Advanced Features](advanced-features.md) - FFT analysis and math channels
