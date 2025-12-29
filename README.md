# Siglent Oscilloscope Control

[![PyPI version](https://img.shields.io/pypi/v/Siglent-Oscilloscope.svg)](https://pypi.org/project/Siglent-Oscilloscope/)
[![Python Version](https://img.shields.io/pypi/pyversions/Siglent-Oscilloscope)](https://pypi.org/project/Siglent-Oscilloscope/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A professional Python package for controlling Siglent SD824x HD oscilloscopes via Ethernet/LAN. Features both a comprehensive programmatic API and an intuitive PyQt6-based GUI application.

## Features

- **Programmatic API**: Control your oscilloscope from Python scripts
- **Automation & Data Collection**: High-level API for batch capture, continuous monitoring, and analysis
- **GUI Application**: PyQt6-based graphical interface with styled connect/disconnect buttons
- **Waveform Acquisition**: Capture and download waveform data in multiple formats (NPZ, CSV, MAT, HDF5)
- **Channel Configuration**: Control voltage scale, coupling, offset, bandwidth
- **Trigger Settings**: Configure trigger modes, levels, edge detection
- **Measurements**: Automated measurements, cursors, and statistics
- **Live View**: Real-time waveform display
- **Advanced Analysis**: Built-in FFT, SNR, THD, and statistical analysis tools

## Installation

### From PyPI (recommended)

```bash
pip install Siglent-Oscilloscope
```

To include the optional GUI dependencies, install with the `gui` extra:

```bash
pip install "Siglent-Oscilloscope[gui]"
```

### From source

```bash
git clone git@github.com:little-did-I-know/Siglent-Oscilloscope.git
cd siglent
pip install -e .
```

Install with GUI support from source:

```bash
pip install -e ".[gui]"
```

### Development installation

```bash
pip install -e ".[dev]"
```

### Build & Publish (PyPI)

To create release artifacts that render correctly on PyPI:

```bash
python -m build
twine check dist/*
```

The `twine check` command validates the built distributions, including the long description rendered from `README.md`, before upload.

## Quick Start

### Programmatic Usage

```python
from siglent import Oscilloscope

# Connect to oscilloscope
scope = Oscilloscope('192.168.1.100')
scope.connect()

# Get device information
print(scope.identify())

# Configure channel 1
scope.channel1.set_scale(1.0)  # 1V/div
scope.channel1.set_coupling('DC')
scope.channel1.enable()

# Capture waveform
waveform = scope.get_waveform(channel=1)
print(f"Captured {len(waveform.time)} samples")

scope.disconnect()
```

### GUI Application

```bash
siglent-gui
```

Or from Python:
```python
from siglent.gui.app import main
main()
```

## Requirements

- Python 3.8+
- NumPy
- Matplotlib

For the GUI application, install the `gui` extra to add PyQt6 and PyQt6-WebEngine.

## Connection

The oscilloscope must be connected to your network. The default SCPI port is 5024.

To find your oscilloscope's IP address:
1. Press **Utility** on the oscilloscope
2. Navigate to **I/O** settings
3. Check the **LAN** configuration

## API Documentation

### Oscilloscope

```python
from siglent import Oscilloscope

# Connect
scope = Oscilloscope('192.168.1.100', port=5024, timeout=5.0)
scope.connect()

# Device information
print(scope.identify())  # Get *IDN? string
print(scope.device_info)  # Parsed device info dict

# Basic controls
scope.run()           # Start acquisition (AUTO mode)
scope.stop()          # Stop acquisition
scope.auto_setup()    # Auto setup
scope.reset()         # Reset to defaults
```

### Channels

```python
# Channel configuration (channels 1-4)
scope.channel1.enable()
scope.channel1.coupling = "DC"  # DC, AC, or GND
scope.channel1.voltage_scale = 1.0  # Volts/division
scope.channel1.voltage_offset = 0.0  # Volts
scope.channel1.probe_ratio = 10.0  # 10X probe
scope.channel1.bandwidth_limit = "OFF"  # ON or OFF

# Get configuration
config = scope.channel1.get_configuration()
```

### Trigger

```python
# Trigger configuration
scope.trigger.mode = "NORMAL"  # AUTO, NORM, SINGLE, STOP
scope.trigger.source = "C1"  # C1, C2, C3, C4, EX, LINE
scope.trigger.level = 0.0  # Trigger level in volts
scope.trigger.slope = "POS"  # POS (rising) or NEG (falling)

# Edge trigger setup
scope.trigger.set_edge_trigger(source="C1", slope="POS")

# Trigger actions
scope.trigger.single()  # Single trigger
scope.trigger.force()   # Force trigger
```

### Waveform Acquisition

```python
# Acquire waveform
waveform = scope.get_waveform(channel=1)

# Access data
print(waveform.time)      # Time array (numpy)
print(waveform.voltage)   # Voltage array (numpy)
print(waveform.sample_rate)
print(waveform.record_length)

# Save waveform
scope.waveform.save_waveform(waveform, "data.csv", format="CSV")
```

### Measurements

```python
# Individual measurements
freq = scope.measurement.measure_frequency(1)
vpp = scope.measurement.measure_vpp(1)
vrms = scope.measurement.measure_rms(1)
period = scope.measurement.measure_period(1)

# All measurements at once
measurements = scope.measurement.measure_all(1)
```

### Programmatic Data Collection & Automation

For advanced data collection workflows, use the high-level automation API:

```python
from siglent.automation import DataCollector

# Simple capture with automatic analysis
with DataCollector('192.168.1.100') as collector:
    # Capture waveforms
    data = collector.capture_single([1, 2])

    # Analyze waveform
    stats = collector.analyze_waveform(data[1])
    print(f"Vpp: {stats['vpp']:.3f}V, Freq: {stats['frequency']/1e3:.2f}kHz")

    # Save to file (supports NPZ, CSV, MAT, HDF5)
    collector.save_data(data, 'measurement.npz')
```

**Batch capture with configuration sweeps:**

```python
# Capture with different timebase and voltage settings
results = collector.batch_capture(
    channels=[1],
    timebase_scales=['1us', '10us', '100us'],
    voltage_scales={1: ['500mV', '1V', '2V']},
    triggers_per_config=5
)
collector.save_batch(results, 'batch_output')
```

**Continuous time-series collection:**

```python
# Collect data over time with automated file saving
collector.start_continuous_capture(
    channels=[1, 2],
    duration=300,          # 5 minutes
    interval=1.0,          # 1 capture per second
    output_dir='time_series_data',
    file_format='npz'
)
```

**Event-based trigger capture:**

```python
from siglent.automation import TriggerWaitCollector

with TriggerWaitCollector('192.168.1.100') as tc:
    # Configure trigger
    tc.collector.scope.trigger.set_source(1)
    tc.collector.scope.trigger.set_slope('POS')
    tc.collector.scope.trigger.set_level(1, 1.0)

    # Wait for trigger event
    data = tc.wait_for_trigger(channels=[1, 2], max_wait=30.0)
```

**Advanced analysis:**

```python
# Built-in analysis includes: Vpp, RMS, frequency, SNR, THD, etc.
analysis = collector.analyze_waveform(waveform)
print(f"SNR: {analysis['snr_db']:.2f} dB")
print(f"THD: {analysis['thd_percent']:.2f}%")
```

See `examples/` directory for complete automation examples including:
- Simple capture (`simple_capture.py`)
- Batch processing (`batch_capture.py`)
- Continuous monitoring (`continuous_capture.py`)
- Trigger-based capture (`trigger_based_capture.py`)
- Advanced analysis with visualization (`advanced_analysis.py`)

## Examples

See the `examples/` directory for complete working examples:

- **basic_usage.py** - Connection and basic operations
- **waveform_capture.py** - Capture and save waveforms
- **measurements.py** - Automated measurements
- **live_plot.py** - Real-time plotting

## Supported Models

Currently tested with:
- Siglent SDS824X HD

Should work with other Siglent oscilloscopes that support SCPI commands over Ethernet, but commands may need adjustment. Refer to your oscilloscope's programming manual.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details
