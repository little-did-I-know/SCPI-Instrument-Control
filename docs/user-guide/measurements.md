# Measurements

This guide covers automated measurements, measurement statistics, and cursor operations.

## Automated Measurements

The oscilloscope can perform automated measurements directly on waveforms without needing to capture the data.

### Quick Measurements

The library provides convenience methods for common measurements:

```python
from siglent import Oscilloscope

with Oscilloscope('192.168.1.100') as scope:
    # Configure channel
    scope.channel1.enabled = True
    scope.trigger.mode = "AUTO"

    # Voltage measurements
    vpp = scope.measurement.measure_vpp(1)          # Peak-to-peak
    amplitude = scope.measurement.measure_amplitude(1)  # Amplitude
    vrms = scope.measurement.measure_rms(1)          # RMS voltage
    vmean = scope.measurement.measure_mean(1)        # Mean voltage
    vmax = scope.measurement.measure_max(1)          # Maximum
    vmin = scope.measurement.measure_min(1)          # Minimum

    # Frequency/timing measurements
    freq = scope.measurement.measure_frequency(1)    # Frequency
    period = scope.measurement.measure_period(1)     # Period
    duty = scope.measurement.measure_duty_cycle(1)   # Duty cycle

    # Edge measurements
    rise = scope.measurement.measure_rise_time(1)    # Rise time
    fall = scope.measurement.measure_fall_time(1)    # Fall time

    print(f"Frequency: {freq/1e3:.2f} kHz")
    print(f"Vpp: {vpp:.3f} V")
    print(f"Vrms: {vrms:.3f} V")
```

## Available Measurements

### Voltage Measurements

```python
# Peak-to-peak voltage
vpp = scope.measurement.measure_vpp(1)
print(f"Vpp: {vpp:.3f} V")

# Amplitude (half of peak-to-peak)
amplitude = scope.measurement.measure_amplitude(1)
print(f"Amplitude: {amplitude:.3f} V")

# Maximum voltage
vmax = scope.measurement.measure_max(1)
print(f"Max: {vmax:.3f} V")

# Minimum voltage
vmin = scope.measurement.measure_min(1)
print(f"Min: {vmin:.3f} V")

# RMS voltage
vrms = scope.measurement.measure_rms(1)          # All samples
vrms_cycle = scope.measurement.measure_rms(1, cycle=True)  # One cycle
print(f"RMS: {vrms:.3f} V")
print(f"RMS (cycle): {vrms_cycle:.3f} V")

# Mean voltage
vmean = scope.measurement.measure_mean(1)        # All samples
vmean_cycle = scope.measurement.measure_mean(1, cycle=True)  # One cycle
print(f"Mean: {vmean:.3f} V")
print(f"Mean (cycle): {vmean_cycle:.3f} V")
```

!!! info "RMS vs Mean" - **RMS**: Root-mean-square, useful for AC signals and power calculations - **Mean**: Average value, useful for DC offset measurement - **cycle=True**: Measure over one period (for periodic signals) - **cycle=False**: Measure over entire displayed waveform

### Frequency and Timing Measurements

```python
# Frequency (Hz)
freq = scope.measurement.measure_frequency(1)
print(f"Frequency: {freq/1e6:.3f} MHz")

# Period (seconds)
period = scope.measurement.measure_period(1)
print(f"Period: {period*1e6:.3f} µs")

# Duty cycle (percent)
duty = scope.measurement.measure_duty_cycle(1)
print(f"Duty cycle: {duty:.1f}%")

# Rise time (seconds)
rise = scope.measurement.measure_rise_time(1)
print(f"Rise time: {rise*1e9:.2f} ns")

# Fall time (seconds)
fall = scope.measurement.measure_fall_time(1)
print(f"Fall time: {fall*1e9:.2f} ns")
```

### Measurement Type Reference

| Measurement  | Method                 | Unit | Description                    |
| ------------ | ---------------------- | ---- | ------------------------------ |
| Peak-to-peak | `measure_vpp()`        | V    | Difference between max and min |
| Amplitude    | `measure_amplitude()`  | V    | Half of peak-to-peak           |
| Maximum      | `measure_max()`        | V    | Highest voltage value          |
| Minimum      | `measure_min()`        | V    | Lowest voltage value           |
| RMS          | `measure_rms()`        | V    | Root-mean-square voltage       |
| Mean         | `measure_mean()`       | V    | Average voltage                |
| Frequency    | `measure_frequency()`  | Hz   | Signal frequency               |
| Period       | `measure_period()`     | s    | Signal period                  |
| Duty Cycle   | `measure_duty_cycle()` | %    | Positive width / period × 100  |
| Rise Time    | `measure_rise_time()`  | s    | 10% to 90% rise time           |
| Fall Time    | `measure_fall_time()`  | s    | 90% to 10% fall time           |

## Generic Measurement Interface

You can also use the generic `measure()` method:

```python
# Using SCPI measurement types directly
vpp = scope.measurement.measure("PKPK", 1)      # Peak-to-peak
freq = scope.measurement.measure("FREQ", 1)     # Frequency
rise = scope.measurement.measure("RISE", 1)     # Rise time
fall = scope.measurement.measure("FALL", 1)     # Fall time
duty = scope.measurement.measure("DUTY", 1)     # Duty cycle

# Available SCPI types:
# "PKPK", "MAX", "MIN", "AMPL", "TOP", "BASE"
# "CMEAN", "MEAN", "RMS", "CRMS"
# "FREQ", "PER", "RISE", "FALL", "WID", "NWID", "DUTY"
```

## Measure All Common Parameters

Get all common measurements at once:

```python
# Measure everything
measurements = scope.measurement.measure_all(1)

# Print all measurements
for name, value in measurements.items():
    if value is not None:
        print(f"{name}: {value}")
    else:
        print(f"{name}: N/A")

# Access specific measurements
if measurements['frequency'] is not None:
    print(f"Frequency: {measurements['frequency']/1e3:.2f} kHz")

if measurements['vpp'] is not None:
    print(f"Vpp: {measurements['vpp']:.3f} V")
```

The `measure_all()` method returns a dictionary with:

- `vpp` - Peak-to-peak voltage
- `amplitude` - Amplitude
- `max` - Maximum voltage
- `min` - Minimum voltage
- `mean` - Mean voltage
- `rms` - RMS voltage
- `frequency` - Frequency
- `period` - Period

!!! tip "Error Handling"
`measure_all()` catches exceptions for individual measurements and returns `None` for failed measurements. This is useful when not all measurements are applicable to your signal.

## Measurement Table

The oscilloscope can display measurements in an on-screen table.

### Adding Measurements to Table

```python
# Add measurements to on-screen table
scope.measurement.add_measurement("PKPK", 1)      # Vpp on channel 1
scope.measurement.add_measurement("FREQ", 1)      # Frequency on channel 1
scope.measurement.add_measurement("RMS", 2)       # RMS on channel 2

# Add measurement with statistics enabled
scope.measurement.add_measurement("PKPK", 1, stat=True)
```

### Managing Measurement Table

```python
# Clear all measurements from table
scope.measurement.clear_measurements()

# Enable statistics for all measurements
scope.measurement.enable_statistics()

# Disable statistics
scope.measurement.disable_statistics()

# Reset statistics
scope.measurement.reset_statistics()
```

## Measurement Statistics

When statistics are enabled, the oscilloscope tracks min, max, mean, and standard deviation for each measurement.

```python
# Enable statistics
scope.measurement.enable_statistics()

# Add measurements
scope.measurement.add_measurement("PKPK", 1, stat=True)
scope.measurement.add_measurement("FREQ", 1, stat=True)

# Let measurements accumulate over time
import time
time.sleep(10)  # Collect stats for 10 seconds

# Statistics are shown on oscilloscope display
# They include: Current, Min, Max, Mean, Std Dev

# Reset to start fresh statistics
scope.measurement.reset_statistics()

# Disable when done
scope.measurement.disable_statistics()
```

!!! note "Statistics Display"
Statistics are displayed on the oscilloscope screen. To access them programmatically, you'll need to use screen capture or query specific measurement values multiple times and calculate statistics yourself.

## Cursors

Cursors allow manual measurement of voltage and time differences.

### Cursor Types

```python
# Turn off cursors
scope.measurement.set_cursor_type("OFF")

# Horizontal relative (time measurement)
scope.measurement.set_cursor_type("HREL")

# Vertical relative (voltage measurement)
scope.measurement.set_cursor_type("VREL")

# Horizontal reference
scope.measurement.set_cursor_type("HREF")

# Vertical reference
scope.measurement.set_cursor_type("VREF")
```

### Reading Cursor Values

```python
# Enable vertical cursors
scope.measurement.set_cursor_type("VREL")

# Get cursor values
cursor_data = scope.measurement.get_cursor_value()
print(f"Cursor type: {cursor_data['type']}")
print(f"Values: {cursor_data['values']}")

# Example output:
# Cursor type: VREL
# Values: ['1.00V', '2.00V', '1.00V']
```

!!! info "Cursor Types" - **HREL**: Horizontal relative - measures time difference - **VREL**: Vertical relative - measures voltage difference - **HREF**: Horizontal reference - time reference - **VREF**: Vertical reference - voltage reference - **OFF**: Cursors disabled

## Programmatic Measurement vs Automated Measurement

There are two ways to get measurements:

### 1. Oscilloscope Automated Measurements (Recommended)

```python
# Uses oscilloscope's built-in measurement algorithms
freq = scope.measurement.measure_frequency(1)
vpp = scope.measurement.measure_vpp(1)
```

**Advantages:**

- Fast (single SCPI command)
- Uses oscilloscope's optimized algorithms
- No data transfer needed
- More accurate for some measurements

### 2. Capture and Process Data

```python
# Capture waveform and process yourself
import numpy as np

waveform = scope.get_waveform(1)

# Calculate measurements manually
vpp = float(np.ptp(waveform.voltage))
vrms = float(np.sqrt(np.mean(waveform.voltage**2)))
vmean = float(np.mean(waveform.voltage))

# Find frequency from zero crossings
zero_crossings = np.where(np.diff(np.sign(waveform.voltage)))[0]
if len(zero_crossings) >= 2:
    periods = np.diff(waveform.time[zero_crossings])
    freq = 1.0 / np.mean(periods[::2])  # Every other crossing
```

**Advantages:**

- Full control over algorithm
- Access to raw data for custom analysis
- Can apply filtering before measurement
- Useful for complex or custom measurements

!!! tip "Best Practice"
Use automated measurements for standard parameters (frequency, Vpp, RMS, etc.) and capture data only when you need custom processing or the full waveform.

## Multi-Channel Measurements

Measure parameters across multiple channels:

```python
# Configure channels
scope.channel1.enabled = True
scope.channel2.enabled = True

# Measure same parameter on different channels
ch1_freq = scope.measurement.measure_frequency(1)
ch2_freq = scope.measurement.measure_frequency(2)

print(f"Channel 1: {ch1_freq/1e3:.2f} kHz")
print(f"Channel 2: {ch2_freq/1e3:.2f} kHz")

# Measure different parameters
ch1_vpp = scope.measurement.measure_vpp(1)
ch2_rms = scope.measurement.measure_rms(2)

# Get all measurements for all channels
all_measurements = {}
for ch in [1, 2, 3, 4]:
    try:
        all_measurements[ch] = scope.measurement.measure_all(ch)
    except:
        pass  # Channel not enabled or error

# Print results
for ch, meas in all_measurements.items():
    print(f"\nChannel {ch}:")
    for name, value in meas.items():
        if value is not None:
            print(f"  {name}: {value}")
```

## Measurement Error Handling

```python
from siglent import CommandError, InvalidParameterError

try:
    freq = scope.measurement.measure_frequency(1)
    print(f"Frequency: {freq} Hz")

except CommandError as e:
    # No signal or measurement failed
    print(f"Measurement failed: {e}")

except InvalidParameterError as e:
    # Invalid parameter (channel number, etc.)
    print(f"Invalid parameter: {e}")

# Safe measurement with fallback
try:
    freq = scope.measurement.measure_frequency(1)
except:
    freq = None

if freq is not None:
    print(f"Frequency: {freq/1e3:.2f} kHz")
else:
    print("Frequency measurement unavailable")
```

## Complete Measurement Example

Here's a complete example that measures and logs parameters:

```python
from siglent import Oscilloscope
import time
import csv

SCOPE_IP = '192.168.1.100'
LOG_FILE = 'measurements.csv'
DURATION = 60  # seconds
INTERVAL = 1   # seconds

with Oscilloscope(SCOPE_IP) as scope:
    # Configure
    scope.channel1.enabled = True
    scope.channel1.voltage_scale = 1.0
    scope.trigger.mode = "AUTO"

    # Create CSV file
    with open(LOG_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Time', 'Frequency (Hz)', 'Vpp (V)', 'Vrms (V)', 'Duty Cycle (%)'])

        start_time = time.time()
        while (time.time() - start_time) < DURATION:
            try:
                # Get measurements
                freq = scope.measurement.measure_frequency(1)
                vpp = scope.measurement.measure_vpp(1)
                vrms = scope.measurement.measure_rms(1)
                duty = scope.measurement.measure_duty_cycle(1)

                # Calculate elapsed time
                elapsed = time.time() - start_time

                # Write to CSV
                writer.writerow([f"{elapsed:.1f}", freq, vpp, vrms, duty])

                # Print to console
                print(f"[{elapsed:5.1f}s] Freq: {freq/1e3:7.2f} kHz, "
                      f"Vpp: {vpp:5.3f} V, Vrms: {vrms:5.3f} V, "
                      f"Duty: {duty:5.1f}%")

            except Exception as e:
                print(f"Measurement error: {e}")

            # Wait for next measurement
            time.sleep(INTERVAL)

    print(f"\nMeasurements saved to {LOG_FILE}")
```

## Tips for Accurate Measurements

!!! tip "Signal Conditioning" - Ensure trigger is stable (use NORMAL mode for consistent measurements) - Set appropriate voltage scale (signal should fill 50-80% of display) - Use AC coupling to remove DC offset if measuring AC signals - Enable bandwidth limiting to reduce noise

!!! tip "Frequency Measurements" - Requires periodic signal with clear edges - Works best with at least 2-3 cycles on screen - May fail on noisy or irregular signals - Use appropriate timebase (show at least 2 periods)

!!! tip "Timing Measurements (Rise/Fall Time)" - Requires fast sampling rate relative to edge speed - Set timebase to show edge detail - Single edge should occupy 2-3 divisions - Use 20 MHz bandwidth limit for noisy signals

!!! tip "Voltage Measurements" - Calibrate probe attenuation (set probe_ratio correctly) - Allow signal to stabilize before measuring - Use averaging or statistics for noisy signals - Check for clipping (signal exceeds display range)

## Troubleshooting

### "No valid measurement" errors

```python
# Check if signal is present
try:
    freq = scope.measurement.measure_frequency(1)
except:
    # Possible causes:
    # 1. Channel not enabled
    if not scope.channel1.enabled:
        scope.channel1.enabled = True

    # 2. No signal
    waveform = scope.get_waveform(1)
    if np.ptp(waveform.voltage) < 0.01:  # Less than 10mV
        print("Warning: Signal amplitude very low")

    # 3. Trigger not stable
    scope.trigger.mode = "AUTO"
```

### Inconsistent measurements

```python
# Use statistics to see variation
scope.measurement.enable_statistics()
scope.measurement.add_measurement("FREQ", 1, stat=True)

# Take multiple measurements
measurements = []
for i in range(10):
    measurements.append(scope.measurement.measure_frequency(1))
    time.sleep(0.1)

import numpy as np
print(f"Mean: {np.mean(measurements):.2f} Hz")
print(f"Std Dev: {np.std(measurements):.2f} Hz")
print(f"Range: {np.ptp(measurements):.2f} Hz")
```

## Next Steps

- [Trigger Control](trigger-control.md) - Improve measurement stability with proper triggering
- [Advanced Features](advanced-features.md) - FFT analysis and advanced signal processing
- [Waveform Capture](waveform-capture.md) - Capture data for custom measurements
