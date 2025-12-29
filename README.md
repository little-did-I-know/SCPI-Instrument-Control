# Siglent Oscilloscope Control

[![PyPI version](https://img.shields.io/pypi/v/Siglent-Oscilloscope.svg)](https://pypi.org/project/Siglent-Oscilloscope/)
[![Python Version](https://img.shields.io/pypi/pyversions/Siglent-Oscilloscope)](https://pypi.org/project/Siglent-Oscilloscope/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A professional Python package for controlling Siglent oscilloscopes via Ethernet/LAN. Features both a comprehensive programmatic API and a high-performance PyQt6-based GUI application with real-time visualization.

## Features

### Core Features
- **Programmatic API**: Control your oscilloscope from Python scripts
- **Automation & Data Collection**: High-level API for batch capture, continuous monitoring, and analysis
- **GUI Application**: Modern PyQt6-based graphical interface
- **Waveform Acquisition**: Capture and download waveform data in multiple formats (NPZ, CSV, MAT, HDF5)
- **Channel Configuration**: Control voltage scale, coupling, offset, bandwidth
- **Trigger Settings**: Configure trigger modes, levels, edge detection
- **Advanced Analysis**: Built-in FFT, SNR, THD, and statistical analysis tools

### GUI Features (New!)
- **High-Performance Live View**: Real-time waveform display at 1000+ fps using PyQtGraph
- **Interactive Visual Measurements**: Click-and-drag measurement markers directly on waveforms
  - 15+ measurement types: Frequency, Vpp, Rise Time, Duty Cycle, etc.
  - Visual gates and markers with real-time calculation
  - Save/load measurement configurations
  - Export results to CSV/JSON
- **Non-Blocking Updates**: Threaded data acquisition keeps GUI responsive
- **Reference Waveforms**: Save, overlay, and compare waveforms
- **Protocol Decoding**: I2C, SPI, UART, CAN, LIN support
- **Math Functions**: Custom math expressions on waveforms
- **VNC Display**: Embedded oscilloscope screen viewer

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

### Core Library
- Python 3.8+
- NumPy >= 1.24.0
- Matplotlib >= 3.7.0
- SciPy >= 1.10.0

### GUI Application (optional)
Install with `[gui]` extra to add:
- PyQt6 >= 6.6.0
- PyQt6-WebEngine >= 6.6.0
- PyQtGraph >= 0.13.0 (high-performance plotting)

### Optional Extras
- **HDF5 support**: Install with `[hdf5]` to add h5py >= 3.8.0
- **All features**: Install with `[all]` for complete functionality

## Connection

The oscilloscope must be connected to your network. The default SCPI port is 5024.

To find your oscilloscope's IP address:
1. Press **Utility** on the oscilloscope
2. Navigate to **I/O** settings
3. Check the **LAN** configuration

## GUI Application Guide

### Live View

The GUI features **high-performance real-time waveform viewing** powered by PyQtGraph:

```
Acquisition → Live View (Ctrl+R)
```

**Performance:**
- Real-time updates at 5-20 fps (configurable)
- 100x faster than traditional matplotlib-based viewers
- Non-blocking: GUI remains responsive during data acquisition
- Supports all 4 channels simultaneously

**Controls:**
- Enable channels in the "Channels" tab first
- Live view automatically acquires from enabled channels
- Adjust update rate by modifying `update_interval` in `live_view_worker.py`

### Visual Measurements

Interactive measurement markers that you can place and adjust directly on waveforms:

**How to use:**
1. Go to the **"Visual Measure"** tab
2. Select measurement type (Frequency, Vpp, Rise Time, etc.)
3. Select channel (CH1-CH4)
4. Click **"Add Marker"**
5. Marker auto-places on waveform
6. Drag marker gates to adjust measurement region
7. See real-time measurement updates

**Measurement Types:**
- **Frequency/Period**: Auto-detects signal period
- **Voltage**: Vpp, Amplitude, Max, Min, RMS, Mean
- **Timing**: Rise Time, Fall Time, Pulse Width, Duty Cycle

**Features:**
- **Save/Load Configs**: Save measurement setups for reuse
- **Export Results**: Export to CSV or JSON
- **Auto-Update**: Optional 1-second auto-refresh
- **Batch Mode**: Run multiple measurements simultaneously

**Example Workflow:**
```python
# In GUI:
# 1. Capture or enable live view
# 2. Visual Measure tab → Add Marker
# 3. Type: "Frequency", Channel: "CH1" → Add
# 4. Marker appears with measurement result
# 5. Save Config → "my_measurements.json"
# 6. Export Results → "results.csv"
```

### Other GUI Features

**Cursors:**
- Vertical cursors for time measurements
- Horizontal cursors for voltage measurements
- Delta calculations (ΔT, ΔV, frequency)

**Reference Waveforms:**
- Save waveforms as references
- Overlay comparisons
- Difference mode (live - reference)
- Calculate correlation

**Math Channels:**
- Custom expressions: `C1 + C2`, `C1 * 2`, etc.
- Real-time calculation

**FFT Analysis:**
- Frequency domain visualization
- Window function selection
- Peak detection

**Protocol Decode:**
- I2C, SPI, UART, CAN, LIN decoding
- Packet analysis and export

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

### Fully Tested
- **SDS800X HD Series**: SDS804X HD, SDS824X HD
- **SDS1000X-E Series**: SDS1102X-E, SDS1104X-E, SDS1202X-E, SDS1204X-E
- **SDS2000X Plus Series**: SDS2104X+, SDS2204X+, SDS2354X+
- **SDS5000X Series**: SDS5034X, SDS5054X, SDS5104X

### Compatibility
Should work with other Siglent oscilloscopes that support SCPI commands over Ethernet. Model-specific features are auto-detected via the `ModelCapability` registry.

**Note**: Some SCPI commands vary between models. The library includes model-specific command variants for HD, X, and Plus series.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details
