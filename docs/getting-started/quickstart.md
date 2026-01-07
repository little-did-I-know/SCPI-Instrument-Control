# Quick Start

Get up and running with the Siglent Oscilloscope Control library in 5 minutes!

## Installation

First, install the library:

=== "Basic (Programmatic Only)"
`bash
    pip install SCPI-Instrument-Control
    `

=== "With GUI"
`bash
    pip install "SCPI-Instrument-Control[gui]"
    `

=== "Everything"
`bash
    pip install "SCPI-Instrument-Control[all]"
    `

## Your First Script

Here's a simple script to connect and capture a waveform:

```python
from scpi_control import Oscilloscope

# Connect to oscilloscope (replace with your IP)
scope = Oscilloscope('192.168.1.100')
scope.connect()

# Print oscilloscope info
print(scope.identify())

# Configure channel 1
scope.channel1.enabled = True
scope.channel1.voltage_scale = 1.0  # 1V per division
scope.channel1.coupling = "DC"

# Trigger setup
scope.trigger.mode = "AUTO"
scope.trigger.source = "C1"
scope.trigger.level = 0.0

# Capture waveform
waveform = scope.get_waveform(1)
print(f"Captured {len(waveform.voltage)} samples")
print(f"Time range: {waveform.time[0]:.6f} to {waveform.time[-1]:.6f} seconds")
print(f"Voltage range: {waveform.voltage.min():.3f} to {waveform.voltage.max():.3f} V")

# Get measurements
freq = scope.measure.frequency(1)
vpp = scope.measure.vpp(1)
print(f"Frequency: {freq:.2f} Hz")
print(f"Peak-to-peak: {vpp:.3f} V")

# Clean up
scope.disconnect()
```

**Expected output:**

```
Siglent Technologies,SDS824X HD,SDSMMDD1XXXXX,8.2.5.1.37R9
Captured 140000 samples
Time range: -0.000070 to 0.000070 seconds
Voltage range: -2.456 to 2.512 V
Frequency: 1000.00 Hz
Peak-to-peak: 5.024 V
```

## Launch the GUI

Start the graphical interface:

```bash
siglent-gui
```

The GUI provides:

- **Live view** with real-time waveform updates
- **Visual measurements** with drag-and-drop markers
- **FFT analysis** for frequency domain
- **Protocol decoding** for I2C/SPI/UART
- **Export** to various formats

## Common Tasks

### Save a Waveform

```python
from scpi_control import Oscilloscope

scope = Oscilloscope('192.168.1.100')
scope.connect()

# Capture and save
waveform = scope.get_waveform(1)
waveform.save_csv("waveform.csv")
waveform.save_npz("waveform.npz")
```

### Multi-Channel Capture

```python
# Enable multiple channels
scope.channel1.enabled = True
scope.channel2.enabled = True

# Capture all enabled channels
waveforms = scope.get_waveforms()
for wf in waveforms:
    print(f"Channel {wf.channel}: {len(wf.voltage)} samples")
```

### Automated Measurements

```python
# Get all available measurements
measurements = {
    'frequency': scope.measure.frequency(1),
    'period': scope.measure.period(1),
    'amplitude': scope.measure.amplitude(1),
    'vpp': scope.measure.vpp(1),
    'vrms': scope.measure.vrms(1),
    'mean': scope.measure.mean(1),
    'rise_time': scope.measure.rise_time(1),
    'fall_time': scope.measure.fall_time(1),
}

for name, value in measurements.items():
    print(f"{name}: {value}")
```

### Context Manager (Recommended)

Use the context manager for automatic connection handling:

```python
from scpi_control import Oscilloscope

with Oscilloscope('192.168.1.100') as scope:
    # Connection is automatic
    waveform = scope.get_waveform(1)
    freq = scope.measure.frequency(1)
    print(f"Frequency: {freq} Hz")
    # Disconnection is automatic
```

## High-Level Automation

For data collection tasks, use the automation classes:

```python
from scpi_control.automation import DataCollector

# Automated data collection
with DataCollector('192.168.1.100') as collector:
    # Capture single waveform from channels 1 and 2
    waveforms = collector.capture_single([1, 2])

    # Save to files
    for wf in waveforms:
        wf.save_csv(f"ch{wf.channel}.csv")
```

## Next Steps

!!! tip "Learn More" - [Connection Setup](connection.md) - Configure network and connection settings - [Basic Usage](../user-guide/basic-usage.md) - Detailed usage guide - [Waveform Capture](../user-guide/waveform-capture.md) - Advanced capture techniques - [Measurements](../user-guide/measurements.md) - All measurement types - [GUI Guide](../gui/overview.md) - GUI application features

!!! example "Examples"
Check out the [examples directory](https://github.com/little-did-I-know/SCPI-Instrument-Control/tree/main/examples) for more code samples:

    - Basic oscilloscope control
    - Waveform capture and export
    - FFT analysis
    - Protocol decoding
    - Automation scripts

!!! info "API Reference"
For detailed API documentation, see:

    - [Oscilloscope API](../api/oscilloscope.md)
    - [Channel API](../api/channel.md)
    - [Trigger API](../api/trigger.md)
    - [Waveform API](../api/waveform.md)
