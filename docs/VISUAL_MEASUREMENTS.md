# Visual Measurements Guide

Complete guide to using the interactive visual measurement system in the Siglent Oscilloscope GUI.

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [Measurement Types](#measurement-types)
- [Using the Visual Measurement Panel](#using-the-visual-measurement-panel)
- [Saving and Loading Configurations](#saving-and-loading-configurations)
- [Exporting Results](#exporting-results)
- [Tips and Best Practices](#tips-and-best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

The visual measurement system allows you to interactively measure signal properties by placing visual markers directly on waveforms. Instead of selecting measurements from dropdowns, you can see exactly where and how each measurement is being taken.

### Key Features

- **Interactive Markers**: Click to add, drag to adjust measurement regions
- **15+ Measurement Types**: Frequency, voltage, timing, and more
- **Real-Time Updates**: Measurements update as you adjust marker positions
- **Save/Load Configurations**: Save measurement setups for reuse
- **Batch Measurements**: Run multiple measurements simultaneously
- **Export Results**: Export to CSV or JSON for analysis

### How It Works

1. **Add a Marker**: Select measurement type and channel, click "Add Marker"
2. **Auto-Placement**: Marker automatically positions itself on the waveform
3. **Visual Feedback**: See gates, thresholds, and measurement regions
4. **Live Results**: Measurement value updates in real-time
5. **Adjust as Needed**: Drag marker gates to refine measurement region

## Getting Started

### Prerequisites

1. **Install with GUI support**:

   ```bash
   pip install "SCPI-Instrument-Control[gui]"
   ```

2. **Connect to oscilloscope**:
   - Launch: `siglent-gui`
   - Connect to your oscilloscope (enter IP address)
   - Enable at least one channel (Channels tab)

### Your First Measurement

1. **Capture a waveform**:
   - Click "Acquisition" → "Capture Single" (or start Live View)
   - Verify waveform appears on display

2. **Open Visual Measurements**:
   - Click the **"Visual Measure"** tab in the control panel

3. **Add a frequency marker**:
   - Measurement Type: **Frequency**
   - Channel: **CH1** (or whichever channel has your signal)
   - Click **"Add Marker"**

4. **See the result**:
   - Marker appears on waveform with two vertical gates
   - Measurement result shows in the marker list
   - Value updates automatically if using Live View

## Measurement Types

### Frequency and Period

**Types**: `FREQ` (Frequency), `PER` (Period)

**Visual Representation**:

- Two vertical blue dashed lines spanning one signal cycle
- Arc connector between gates showing measured period
- Label displays frequency in Hz, kHz, or MHz

**How It Works**:

- Auto-detects signal period using zero-crossing detection
- Falls back to peak detection for non-zero-crossing signals
- Gates can be manually adjusted to measure specific cycles

**Best Used For**:

- Periodic signals (sine waves, square waves, etc.)
- Clock signals
- PWM signals
- Any repetitive waveform

**Example**:

```
Signal: 1 kHz square wave
Result: 1.000 kHz
Gates: Positioned at start and end of one complete cycle
```

### Voltage Measurements

**Types**:

- `PKPK` - Peak-to-Peak voltage
- `AMPL` - Amplitude (peak to mid-level)
- `MAX` - Maximum voltage
- `MIN` - Minimum voltage
- `RMS` - Root Mean Square voltage
- `MEAN` - Average voltage
- `TOP` - Top level (98% of signal)
- `BASE` - Base level (2% of signal)

**Visual Representation**:

- Yellow horizontal lines at measured voltage levels
- Vertical brackets showing span (for PKPK, AMPL)
- Label with voltage value in V, mV, or µV

**How It Works**:

- Analyzes voltage data within gate region
- Computes statistical measures using NumPy
- RMS uses true RMS calculation (not peak/√2)

**Best Used For**:

- Power supply ripple measurements
- Signal amplitude verification
- DC level measurements
- Noise floor analysis

**Example**:

```
Signal: 3.3V ± 100mV square wave
PKPK Result: 200 mV (min to max span)
AMPL Result: 100 mV (mid to peak)
MEAN Result: 3.30 V (average level)
```

### Timing Measurements

**Types**:

- `RISE` - Rise time (10% to 90%)
- `FALL` - Fall time (90% to 10%)
- `WID` - Positive pulse width (50% to 50%)
- `NWID` - Negative pulse width
- `DUTY` - Duty cycle (percentage)

**Visual Representation**:

- Magenta threshold lines at 10%/90% levels (for rise/fall)
- Vertical gates spanning the measurement region
- Shaded region highlighting measured time interval
- Label with time in s, ms, µs, or ns

**How It Works**:

- Calculates 10%/90% thresholds from signal amplitude
- Finds edge crossings using linear interpolation
- Measures time between crossing points

**Best Used For**:

- Edge rate verification
- Pulse width measurements
- PWM duty cycle analysis
- Signal integrity checks

**Example**:

```
Signal: 5V logic with 10ns rise time
RISE Result: 10.2 ns
Gates: Show 10% (0.5V) and 90% (4.5V) thresholds
```

## Using the Visual Measurement Panel

### Panel Layout

```
┌─ Visual Measurements ──────────────────────┐
│                                             │
│  Measurement Type: [Frequency      ▼]      │
│  Channel:         [CH1             ▼]      │
│  [Add Marker]  [Load Config...]            │
│                                             │
│  ┌─ Active Markers ────────────────────┐  │
│  │ ☑ M1: CH1 Frequency    1.234 kHz   │  │
│  │ ☑ M2: CH1 Rise Time     45.2 ns    │  │
│  │ ☐ M3: CH2 Vpp           3.24 V     │  │
│  └─────────────────────────────────────┘  │
│                                             │
│  [Update All]  [Clear All]                 │
│  [Save Config...]  [Export Results...]     │
│                                             │
│  ☑ Auto-Update (1s refresh)                │
└─────────────────────────────────────────────┘
```

### Adding Markers

1. **Select measurement type** from dropdown
   - Choose from 15+ measurement types
   - Hover over types for descriptions

2. **Select channel** (CH1-CH4)
   - Only enabled channels are available

3. **Click "Add Marker"**
   - Marker appears on waveform
   - Auto-positions based on signal characteristics
   - Assigned unique ID (M1, M2, M3, ...)

### Managing Markers

**Enable/Disable**:

- Check/uncheck marker in list
- Disabled markers are hidden but configuration is preserved

**Remove Marker**:

- Select marker in list
- Click "Clear Selected" or "Clear All"

**Update Measurements**:

- **Manual**: Click "Update All" button
- **Automatic**: Enable "Auto-Update" checkbox
  - Refreshes every 1 second
  - Only updates if waveform has changed

### Adjusting Marker Position

> **Note**: In current implementation (matplotlib-based), markers auto-position.
> Manual adjustment via dragging is available in the PyQtGraph version (future update).

To adjust measurement region:

1. Remove existing marker
2. Add new marker (will auto-position to current waveform)
3. Or modify gate positions in saved configuration file

## Saving and Loading Configurations

### Why Save Configurations?

- **Reuse**: Apply same measurement setup across different sessions
- **Share**: Send configurations to colleagues
- **Templates**: Build measurement libraries for common test scenarios
- **Batch**: Load multiple markers at once

### Saving a Configuration

1. **Add desired markers** to waveform
2. **Click "Save Config..."**
3. **Choose location and filename**
   - Default: `~/Documents/siglent/measurement_configs/`
   - File format: JSON (`.json` extension)
4. **Enter configuration name** when prompted

### Loading a Configuration

1. **Click "Load Config..."**
2. **Select configuration file** (`.json`)
3. **Markers automatically added** to waveform
4. **Measurements calculated** from current waveform

### Configuration File Format

Configurations are stored as JSON:

```json
{
  "name": "Power Supply Analysis",
  "version": "1.0",
  "created_at": "2025-12-29T10:30:00",
  "metadata": {
    "description": "Standard power supply measurements",
    "author": "Your Name"
  },
  "markers": [
    {
      "id": "M1",
      "measurement_type": "FREQ",
      "channel": 1,
      "enabled": true,
      "gates": {
        "start_x": -0.0001,
        "end_x": 0.0001
      },
      "visual_style": {
        "color": "#00CED1"
      },
      "result": 100000.0,
      "unit": "Hz"
    }
  ]
}
```

You can edit these files manually to:

- Adjust gate positions precisely
- Change marker colors
- Add metadata/notes
- Disable specific markers

### Default Configuration Directory

**Windows**: `C:\Users\YourName\AppData\Local\siglent\measurement_configs\`

**macOS**: `~/Library/Application Support/siglent/measurement_configs/`

**Linux**: `~/.config/siglent/measurement_configs/`

## Exporting Results

### CSV Export

Exports measurement results as comma-separated values:

```csv
Marker ID,Type,Channel,Value,Unit,Timestamp
M1,FREQ,1,1234.5,Hz,2025-12-29 10:30:15
M2,PKPK,1,3.24,V,2025-12-29 10:30:15
M3,RISE,2,45.2,ns,2025-12-29 10:30:15
```

**Use Cases**:

- Import into Excel, Google Sheets
- Analysis with pandas/numpy
- Charting and visualization
- Automated test reporting

**How to Export**:

1. Update all measurements (click "Update All")
2. Click "Export Results..."
3. Choose "CSV" format
4. Select save location

### JSON Export

Exports complete configuration + results:

```json
{
  "name": "Measurement Results",
  "exported_at": "2025-12-29T10:30:15",
  "measurements": [
    {
      "marker_id": "M1",
      "type": "FREQ",
      "channel": 1,
      "value": 1234.5,
      "unit": "Hz",
      "gates": { "start_x": -0.0001, "end_x": 0.0001 }
    }
  ]
}
```

**Use Cases**:

- Machine-readable format
- Integration with automated systems
- Preserves full measurement context
- Re-import into application

## Tips and Best Practices

### Getting Accurate Measurements

1. **Use appropriate timebase**:
   - For frequency: Show 3-5 complete cycles
   - For rise time: Zoom in on edge
   - For duty cycle: Show full period

2. **Check signal quality**:
   - Adequate voltage scale (signal fills ~80% of screen)
   - Low noise (consider averaging or filtering)
   - Proper triggering (stable display)

3. **Verify auto-placement**:
   - Check that marker gates encompass intended region
   - For frequency, verify gates span exactly one cycle
   - For timing, ensure edge is within gate region

### Working with Multiple Channels

**Compare signals**:

```
M1: CH1 Frequency → 1.000 kHz
M2: CH2 Frequency → 1.000 kHz
M3: CH1 Rise Time → 10.2 ns
M4: CH2 Rise Time → 25.8 ns
→ Conclusion: CH2 has slower edges
```

**Analyze relationships**:

```
M1: CH1 Duty Cycle → 25%
M2: CH2 Phase shift → Measure delay between CH1/CH2 edges
```

### Batch Measurement Workflows

**Power Supply Test**:

1. Load "Power Supply Config" (FREQ, PKPK, RMS ripple)
2. Connect to each supply output
3. Update measurements
4. Export results to CSV
5. Move to next supply

**Signal Integrity Suite**:

1. Load "Signal Integrity Config" (RISE, FALL, OVERSHOOT, RINGING)
2. Apply to test signal
3. Auto-update enabled
4. Monitor in real-time
5. Export when stable

### Performance Tips

**Live View Mode**:

- Keep marker count reasonable (<10 markers)
- Disable unused markers instead of removing
- Auto-update adds ~1s overhead per refresh

**Large Waveforms**:

- Zoom in to region of interest first
- Markers calculate over visible data only
- Better performance with fewer samples

## Troubleshooting

### Marker Not Appearing

**Symptom**: Click "Add Marker" but nothing shows on waveform

**Possible Causes**:

1. **No waveform data**
   - Solution: Capture waveform first (Single or Live View)

2. **Channel disabled**
   - Solution: Enable channel in Channels tab

3. **Signal out of view**
   - Solution: Autoscale or adjust timebase/voltage scale

### Incorrect Measurement Values

**Symptom**: Measurement result seems wrong

**Possible Causes**:

1. **Auto-placement error**
   - Solution: Check gate positions visually
   - For frequency: Verify gates span exactly one cycle

2. **Wrong measurement type**
   - Solution: PKPK vs AMPL, WID vs DUTY, etc.
   - Verify you selected intended measurement

3. **Signal quality issues**
   - Solution: Increase averaging, reduce noise
   - Check probe compensation

4. **Timebase too coarse**
   - Solution: Zoom in for better resolution
   - Especially important for rise/fall time

### Cannot Save/Load Configuration

**Symptom**: Error when saving or loading configuration files

**Possible Causes**:

1. **Permission denied**
   - Solution: Check write permissions for config directory
   - Try saving to Documents folder instead

2. **Invalid JSON**
   - Solution: Use "Save Config" button instead of manual editing
   - Validate JSON syntax if editing manually

3. **Missing directory**
   - Solution: Create config directory manually
   - Application should auto-create, but verify it exists

### Auto-Update Not Working

**Symptom**: Measurements don't update automatically

**Possible Causes**:

1. **Auto-Update disabled**
   - Solution: Check "Auto-Update" checkbox

2. **Not in Live View mode**
   - Solution: Auto-update requires continuous waveform capture
   - Start Live View for real-time updates

3. **Waveform not changing**
   - Solution: Auto-update only refreshes when new data arrives
   - Verify oscilloscope is running (not stopped)

### Slow Performance

**Symptom**: GUI lags when adding/updating markers

**Possible Causes**:

1. **Too many markers**
   - Solution: Remove unused markers
   - Disable instead of keeping all visible

2. **Large waveform**
   - Solution: Reduce record length on oscilloscope
   - Zoom in to specific region

3. **Auto-update + Live View**
   - Solution: Disable auto-update if not needed
   - Increase auto-update interval (edit code: default 1s)

## Advanced Usage

### Custom Measurement Setups

**Example: Power Supply Startup Analysis**

Configuration:

- M1: CH1 RISE (startup time)
- M2: CH1 PKPK (overshoot)
- M3: CH1 MEAN (final voltage)
- M4: CH2 FREQ (switcher frequency)

Workflow:

1. Single-shot trigger on startup event
2. Load configuration
3. Update measurements
4. Export results
5. Compare across multiple units

### Integration with Automation

**Programmatic Control** (future enhancement):

```python
from scpi_control.gui.widgets.visual_measurement_panel import VisualMeasurementPanel
from scpi_control.measurement_config import MeasurementConfigSet

# Load configuration
config = MeasurementConfigSet.load_from_file("test_suite.json")

# Apply to panel
panel.load_configuration(config)

# Get results
results = panel.get_all_measurements()
```

### Building Measurement Libraries

**Organize by category**:

```
~/Documents/siglent/measurement_configs/
  ├── power_supply/
  │   ├── startup.json
  │   ├── ripple.json
  │   └── transient.json
  ├── signal_integrity/
  │   ├── edge_rates.json
  │   ├── jitter.json
  │   └── overshoot.json
  └── digital/
      ├── timing.json
      ├── setup_hold.json
      └── clock.json
```

**Share with team**:

- Store in shared network location
- Version control with git
- Include documentation in metadata

## Keyboard Shortcuts

| Action         | Shortcut       |
| -------------- | -------------- |
| Add Marker     | `Ctrl+M`       |
| Update All     | `Ctrl+U`       |
| Clear All      | `Ctrl+Shift+C` |
| Save Config    | `Ctrl+S`       |
| Load Config    | `Ctrl+O`       |
| Export Results | `Ctrl+E`       |

> **Note**: Keyboard shortcuts available in future release

## Further Reading

- **README.md**: General application overview and installation
- **API Documentation**: Programmatic measurement API
- **CHANGELOG.md**: Version history and recent changes
- **Examples**: See `examples/` directory for automation scripts

## Support

For issues, questions, or feature requests:

- GitHub Issues: https://github.com/little-did-I-know/SCPI-Instrument-Control/issues
- Documentation: README.md
- Examples: `examples/` directory

---

**Version**: 0.2.0
**Last Updated**: 2025-12-29
**Compatibility**: Siglent Oscilloscope Python Package v0.2.0+
