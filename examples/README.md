# Siglent Oscilloscope Control Examples

This directory contains example scripts demonstrating various features of the Siglent oscilloscope control package.

## Examples

### basic_usage.py
Basic oscilloscope control demonstrating:
- Connecting to the oscilloscope
- Configuring channels (coupling, scale, offset, probe ratio)
- Setting up triggers
- Performing measurements

**Usage:**
```bash
python basic_usage.py
```

### waveform_capture.py
Waveform acquisition and export demonstrating:
- Capturing waveform data from a channel
- Saving waveform to CSV file
- Plotting waveform with matplotlib
- Exporting plot to PNG image

**Usage:**
```bash
python waveform_capture.py
```

**Output:**
- `waveform.csv` - Waveform data in CSV format
- `waveform.png` - Waveform plot image

### measurements.py
Automated measurements demonstrating:
- Individual measurements (frequency, Vpp, RMS, period, etc.)
- Batch measurements on a channel
- Using the measurement API

**Usage:**
```bash
python measurements.py
```

### live_plot.py
Real-time waveform plotting demonstrating:
- Live waveform acquisition
- Animated matplotlib plotting
- Multi-channel display

**Usage:**
```bash
python live_plot.py
```

**Note:** Close the plot window to stop the live view.

## Configuration

Before running the examples, update the `SCOPE_IP` variable in each script to match your oscilloscope's IP address.

To find your oscilloscope's IP address:
1. Press **Utility** on the oscilloscope
2. Navigate to **I/O** settings
3. Check the **LAN** configuration

## Requirements

All examples require the siglent package to be installed:

```bash
cd /path/to/Siglent
pip install -e .
```

## Programmatic Data Collection Examples

The following examples demonstrate the high-level automation API for programmatic data collection and analysis:

### simple_capture.py
Single waveform capture with analysis:
- Connecting to the oscilloscope
- Capturing waveforms from multiple channels
- Analyzing waveform data (Vpp, RMS, frequency)
- Saving waveforms to file (NumPy format)

**Usage:**
```bash
python simple_capture.py
```

**Output:**
- Console output with waveform statistics
- `simple_capture_ch1.npz` and `simple_capture_ch2.npz` files

---

### batch_capture.py
Batch capture with configuration sweeps:
- Capturing with different timebase scales
- Capturing with different voltage scales
- Progress tracking during batch operations
- Saving batch results with metadata

**Usage:**
```bash
python batch_capture.py
```

**Output:**
- Console progress updates
- `batch_output/` directory with waveforms and metadata

**Use Cases:** Automated testing, signal characterization, parameter sweeps

---

### continuous_capture.py
Time-series data collection:
- Continuous capture over specified duration
- Capturing to memory (short durations)
- Capturing to files (long durations)
- Statistical analysis of time-varying signals

**Usage:**
```bash
python continuous_capture.py
```

**Output:**
- Console statistics for memory-based capture
- `continuous_data/` directory with timestamped files

**Use Cases:** Signal monitoring, stability testing, long-term logging

---

### trigger_based_capture.py
Event-based waveform capture:
- Configuring trigger conditions (source, edge, level)
- Waiting for specific trigger events
- Capturing single and multiple trigger events
- Event-based data collection

**Usage:**
```bash
python trigger_based_capture.py
```

**Output:**
- `trigger_captures/` directory with triggered waveforms
- `multi_trigger_captures/` directory with multiple events

**Use Cases:** Sporadic event capture, glitch detection, intermittent signal troubleshooting

---

### advanced_analysis.py
Advanced signal analysis and visualization:
- Advanced measurements (SNR, THD)
- FFT spectrum analysis
- Statistical distribution analysis
- Visualization with matplotlib
- Automated report generation

**Usage:**
```bash
python advanced_analysis.py
```

**Output:**
- Interactive matplotlib plots (time-domain, frequency spectrum, histogram)
- `analyzed_waveform.npz` - Raw data
- `analysis_report.txt` - Complete analysis report

**Requirements:** matplotlib, numpy

---

## File Formats

The automation API supports multiple export formats:

| Format | Extension | Best For | Metadata |
|--------|-----------|----------|----------|
| NumPy | .npz | Python analysis | Yes |
| CSV | .csv | Spreadsheet tools | Optional |
| MATLAB | .mat | MATLAB/Simulink | Yes |
| HDF5 | .h5 | Large datasets | Yes |

Change format using the `format` parameter:
```python
collector.save_data(waveforms, 'output.mat', format='mat')
```

## Quick Start - Programmatic API

```python
from siglent.automation import DataCollector

# Simple capture
with DataCollector('192.168.1.100') as collector:
    data = collector.capture_single([1, 2])
    stats = collector.analyze_waveform(data[1])
    print(f"Vpp: {stats['vpp']:.3f}V")
    collector.save_data(data, 'measurement.npz')
```

## Tips

- Make sure your oscilloscope is connected to the same network as your computer
- Ensure the SCPI port (5024) is accessible
- Some commands may vary slightly between oscilloscope models - refer to your programming manual
- Enable at least one channel before capturing waveforms
- Use AUTO trigger mode for continuous acquisition
- Use NORMAL or SINGLE mode for specific trigger conditions
- For long captures, save to files instead of memory to avoid memory issues
- Use context managers (`with` statements) for automatic connection cleanup
