# Visual Measurements

Complete guide to using the interactive visual measurement system in the GUI application.

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

The visual measurement system lets you measure signal properties by placing markers directly on waveforms. Instead of reading raw numbers only, you can see exactly where and how each measurement is being taken.

### Key Features

- **Interactive Markers**: add a marker for a chosen measurement type and channel; it auto-positions on the waveform
- **15+ Measurement Types**: frequency, voltage, and timing measurements
- **Real-Time Updates**: measurements update as new waveform data arrives (manual or auto-update)
- **Save/Load Configurations**: save marker setups for reuse
- **Batch Measurements**: run multiple markers simultaneously
- **Export Results**: export to CSV or JSON for analysis

### How It Works

1. **Add a Marker**: select measurement type and channel, click "Add Marker"
2. **Auto-Placement**: the marker automatically positions itself on the waveform
3. **Visual Feedback**: see gates and the measurement region on the display
4. **Live Results**: the measurement value appears in the marker list
5. **Update as Needed**: click "Update All Measurements" (or enable auto-update) to refresh values as the waveform changes

## Getting Started

### Prerequisites

1. **Install with GUI support**:

   ```bash
   pip install "SCPI-Instrument-Control[gui]"
   ```

2. **Connect to an oscilloscope**:
   - Launch: `siglent-gui`
   - Connect to your oscilloscope (enter IP address, or use a mock connection)
   - Enable at least one channel (Channels tab)

### Your First Measurement

1. **Capture a waveform**:
   - Click "Acquisition" → "Capture Single" (or start Live View)
   - Verify the waveform appears on the display

2. **Open Visual Measurements**:
   - Click the **"Visual Measure"** tab in the control panel

3. **Add a frequency marker**:
   - Type: **Frequency**
   - Channel: **CH1** (or whichever channel has your signal)
   - Click **"Add Marker"**

4. **See the result**:
   - The marker appears on the waveform with its gates
   - The measurement result shows in the marker list
   - The value updates when you click "Update All Measurements" (or automatically, if auto-update is enabled)

## Measurement Types

The type dropdown offers these measurements (grouped by marker class):

### Frequency and Period

**Types**: `FREQ` (Frequency), `PER` (Period)

**Best used for**: periodic signals (sine waves, square waves, clock signals, PWM) — any repetitive waveform.

### Voltage Measurements

**Types**:

- `PKPK` - Peak-to-Peak voltage
- `AMPL` - Amplitude (peak to mid-level)
- `MAX` - Maximum voltage
- `MIN` - Minimum voltage
- `RMS` - Root Mean Square voltage
- `MEAN` - Average voltage
- `TOP` - Top level
- `BASE` - Base level

**Best used for**: power supply ripple, signal amplitude verification, DC level measurements, noise floor analysis.

### Timing Measurements

**Types**:

- `RISE` - Rise time
- `FALL` - Fall time
- `WID` - Positive pulse width
- `NWID` - Negative pulse width
- `DUTY` - Duty cycle (percentage)

**Best used for**: edge rate verification, pulse width measurements, PWM duty cycle analysis, signal integrity checks.

## Using the Visual Measurement Panel

### Panel Layout

The panel has four groups, top to bottom:

- **Add Marker**: measurement type dropdown, channel dropdown (CH1-CH4), and an "Add Marker" button
- **Active Markers**: a checkable list of markers, each showing `M<n>: CH<n> <Type> = <value>`
- **Controls**: "Update All Measurements" and "Clear All Markers" (with a confirmation prompt)
- **File Operations**: "Save Configuration...", "Load Configuration...", and "Export Results..."

### Adding Markers

1. **Select measurement type** from the dropdown (15 types available)
2. **Select channel** (CH1-CH4)
3. **Click "Add Marker"**
   - The marker auto-positions on the waveform if data is available
   - It's assigned a unique ID (M1, M2, M3, ...)
   - The list is updated with the new marker

### Managing Markers

**Enable/Disable**:

- Check/uncheck a marker in the list — disabled markers are hidden but stay in the list

**Remove a Marker**:

- Select it in the list and click "Remove Selected"

**Clear All**:

- Click "Clear All Markers" and confirm — removes every marker

**Update Measurements**:

- **Manual**: click "Update All Measurements"
- **Automatic**: enable the auto-update checkbox — refreshes every second

## Saving and Loading Configurations

### Why Save Configurations?

- **Reuse**: apply the same measurement setup across sessions
- **Share**: send configurations to colleagues
- **Batch**: load multiple markers at once

### Saving a Configuration

1. Add the markers you want to keep
2. Click **"Save Configuration..."**
3. Choose a location and filename (`.json` is added automatically if omitted)

### Loading a Configuration

1. Click **"Load Configuration..."**
2. Select a configuration file (`.json`)
3. Existing markers are cleared and replaced with the loaded set
4. Measurements are recalculated from the current waveform

### Default Configuration Directory

The save/load dialogs default to a per-user config directory under `measurement_configs/`:

- **Windows**: `%LOCALAPPDATA%\siglent\measurement_configs\`
- **macOS**: `~/Library/Application Support/siglent/measurement_configs/`
- **Linux**: `~/.config/siglent/measurement_configs/`

You can browse elsewhere from the file dialog.

## Exporting Results

### CSV Export

Exports the current marker list as comma-separated values (`Marker ID, Type, Channel, Value, Unit, Enabled`):

```csv
Marker ID,Type,Channel,Value,Unit,Enabled
M1,FREQ,1,1234.5,Hz,Yes
M2,PKPK,1,3.24,V,Yes
M3,RISE,2,45.2,ns,Yes
```

### JSON Export

Exports a timestamped results object with one entry per marker (id, type, channel, value, unit).

**To Export**:

1. Update all measurements first (click "Update All Measurements")
2. Click "Export Results..."
3. Choose CSV or JSON by the file extension you type

## Tips and Best Practices

### Getting Accurate Measurements

1. **Use an appropriate timebase**:
   - For frequency: show several complete cycles
   - For rise time: zoom in on the edge
   - For duty cycle: show the full period

2. **Check signal quality**:
   - Adequate voltage scale (signal fills most of the screen)
   - Low noise
   - Stable triggering

3. **Verify auto-placement**:
   - Check that the marker's gates encompass the intended region
   - For frequency, verify the gates span exactly one cycle

### Working with Multiple Channels

Add one marker per channel to compare signals directly in the marker list, e.g. a Frequency marker on CH1 and CH2 side by side to compare rates, or Rise Time on both channels to compare edge speed.

### Performance Tips

- Keep the marker count reasonable — fewer markers means faster updates
- Disable markers you're not using instead of removing them, if you'll need them again soon
- Auto-update adds a small refresh overhead per second; disable it if you don't need live updates

## Troubleshooting

### Marker Not Appearing

**Symptom**: click "Add Marker" but nothing shows on the waveform

**Possible causes**:

1. **No waveform data** — capture a waveform first (Single or Live View)
2. **Channel disabled** — enable the channel in the Channels tab
3. **Signal out of view** — autoscale or adjust timebase/voltage scale

### Incorrect Measurement Values

**Symptom**: the measurement result seems wrong

**Possible causes**:

1. **Auto-placement error** — check the gate positions visually; for frequency, verify the gates span exactly one cycle
2. **Wrong measurement type** — PKPK vs AMPL, WID vs DUTY, etc. can look similar but measure different things
3. **Signal quality issues** — increase averaging, reduce noise, check probe compensation
4. **Timebase too coarse** — zoom in for better resolution, especially for rise/fall time

### Cannot Save/Load Configuration

**Symptom**: error when saving or loading a configuration file

**Possible causes**:

1. **Permission denied** — check write permissions for the config directory, or save to a different folder
2. **Invalid JSON** — only edit configuration files by hand if you know the schema; prefer the panel's Save/Load buttons
3. **Missing directory** — the app creates its config directory automatically, but verify it exists if a save fails

### Auto-Update Not Working

**Symptom**: measurements don't update automatically

**Possible causes**:

1. **Auto-update disabled** — check the auto-update checkbox
2. **Waveform not changing** — auto-update only recalculates against the currently captured waveform; start Live View or re-capture for new data

## Next Steps

- [Interface Guide](interface.md) - Learn all GUI controls
- [Live View](live-view.md) - Use markers with continuous acquisition
- [FFT Analysis](fft-analysis.md) - Frequency domain measurements
- [User Guide: Measurements](../user-guide/measurements.md) - Automated (non-visual) measurements
