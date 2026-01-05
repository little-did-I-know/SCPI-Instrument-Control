# Visual Measurements

Visual measurements provide interactive, drag-and-drop markers for precise measurements directly on the waveform display. This guide covers how to use visual measurement markers effectively.

## Overview

Visual measurements allow you to:

- Add interactive markers to the waveform display
- Drag markers to measure specific points
- Calculate deltas between markers automatically
- Snap markers to waveform data points
- Label and customize markers
- Export measurement data

### Marker Types

**Voltage Markers (Horizontal)**

- Measure voltage values
- Horizontal lines across display
- Multiple markers for delta measurements

**Time Markers (Vertical)**

- Measure time values
- Vertical lines across display
- Calculate time differences

**Frequency Markers**

- Measure periods
- Calculate frequency from period
- Useful for periodic signals

## Adding Markers

### Using the Visual Measurements Tab

1. Open **Visual Measurements** tab in control panel
2. Click **Add Voltage Marker** or **Add Time Marker**
3. Marker appears on display
4. Drag to desired position

### Using Right-Click Menu

1. Right-click on waveform display
2. Select **Add Marker Here**
3. Choose marker type
4. Marker placed at click position

### Using Keyboard

Press `Ctrl+M` to add marker at cursor position

## Voltage Markers

### Creating Voltage Marker

**Method 1: Add from Tab**

```
1. Click "Add Voltage Marker" button
2. Marker appears at center
3. Drag to desired voltage
```

**Method 2: Right-Click**

```
1. Right-click at voltage position
2. Select "Add Voltage Marker"
3. Marker placed at click position
```

### Voltage Marker Features

**Display:**

- Horizontal line spanning display
- Label showing voltage value
- Color-coded for visibility

**Interaction:**

- Click and drag vertically to move
- Snaps to waveform if enabled
- Shows real-time voltage value

**Label Format:**

```
V1: 2.345 V
```

### Multiple Voltage Markers

Add multiple markers for delta measurements:

```
V1: 3.500 V
V2: 1.200 V
ΔV: 2.300 V  (automatic)
```

**Delta Calculation:**

- Automatically calculated between markers
- Shows voltage difference
- Updates as markers move

## Time Markers

### Creating Time Marker

**Method 1: Add from Tab**

```
1. Click "Add Time Marker" button
2. Marker appears at center
3. Drag to desired time
```

**Method 2: Right-Click**

```
1. Right-click at time position
2. Select "Add Time Marker"
3. Marker placed at click position
```

### Time Marker Features

**Display:**

- Vertical line from top to bottom
- Label showing time value
- Dotted or solid line style

**Interaction:**

- Click and drag horizontally to move
- Shows real-time time value
- Snaps to grid if enabled

**Label Format:**

```
T1: 125.3 µs
```

### Multiple Time Markers

Add multiple markers for timing measurements:

```
T1: 100.0 µs
T2: 125.0 µs
Δt: 25.0 µs   (automatic)
f = 40.0 kHz  (1/Δt)
```

**Delta Calculations:**

- Time difference (Δt)
- Frequency (1/Δt)
- Updates in real-time

## Frequency Markers

### Period Measurement

Use two time markers to measure period:

```
1. Add Time Marker at start of cycle (T1)
2. Add Time Marker at end of cycle (T2)
3. Δt = period
4. f = 1/Δt = frequency
```

**Example:**

```
T1: 0.00 µs
T2: 10.0 µs
Period: 10.0 µs
Frequency: 100.0 kHz
```

### Duty Cycle Measurement

Measure pulse width and duty cycle:

```
1. Add marker at pulse start (T1)
2. Add marker at pulse end (T2)
3. Add marker at next pulse start (T3)
4. High time: T2 - T1
5. Period: T3 - T1
6. Duty cycle: (T2-T1)/(T3-T1) × 100%
```

## Marker Management

### Marker List

All markers shown in Visual Measurements tab:

**Columns:**

- Type (Voltage/Time)
- Label
- Value
- Color
- Visible (checkbox)

**Actions:**

- Click to select
- Checkbox to show/hide
- Delete button to remove
- Edit button to configure

### Selecting Markers

**Click on Marker:**

- Selects marker
- Highlights in list
- Shows properties

**Click in List:**

- Selects from list
- Highlights on display
- Ready to edit

### Moving Markers

**Drag with Mouse:**

- Click and hold marker
- Drag to new position
- Release to set

**Keyboard:**

- Arrow keys for fine adjustment
- Shift+Arrow for larger steps
- Works when marker selected

**Numeric Input:**

- Double-click marker label
- Enter exact value
- Press Enter to apply

### Deleting Markers

**Individual:**

- Select marker
- Press `Delete` key
- Or click Delete button in list

**All:**

- Tools menu → Clear All Measurements
- Removes all markers

## Marker Properties

### Customizing Markers

**Label Text:**

- Double-click to edit
- Custom names (e.g., "Vmax", "Start Time")
- Displayed on marker

**Color:**

- Click color picker
- Choose from palette
- Custom RGB values

**Line Style:**

- Solid, dashed, or dotted
- Line width adjustment
- Opacity/transparency

**Font:**

- Label font size
- Font family
- Bold/italic

### Snap to Waveform

**Enable Snapping:**

- Checkbox in marker properties
- Marker follows waveform data
- Finds nearest data point

**Behavior:**

- Voltage markers snap to Y values
- Helps find peaks/troughs
- More accurate measurements

**Example:**

```
Without snap: V = 2.347 V (approximate)
With snap: V = 2.350 V (exact data point)
```

## Delta Measurements

### Automatic Deltas

When multiple markers of same type exist:

**Voltage Deltas:**

```
V1: 3.5 V
V2: 1.2 V
ΔV: 2.3 V (V1 - V2)
```

**Time Deltas:**

```
T1: 100 µs
T2: 150 µs
Δt: 50 µs (T2 - T1)
f: 20 kHz (1/Δt)
```

### Delta Display Options

**Show in Label:**

- Delta shown near markers
- Updates as markers move
- Toggle on/off

**Show in Table:**

- Delta measurements in list
- Export with other measurements
- Statistics tracking

## Advanced Measurements

### Rise Time Measurement

Measure 10%-90% rise time:

```
1. Find rising edge
2. Add V1 marker at 10% point
3. Add V2 marker at 90% point
4. Add T1 at V1 crossing
5. Add T2 at V2 crossing
6. Rise time = T2 - T1
```

### Overshoot Measurement

Measure overshoot amplitude:

```
1. Add V1 at steady-state level
2. Add V2 at peak overshoot
3. Overshoot = ((V2-V1)/V1) × 100%
```

### Phase Difference

Measure phase between channels:

```
1. Enable two channels
2. Find zero crossing on C1 (T1)
3. Find zero crossing on C2 (T2)
4. Phase difference = (T2-T1) × 360° / period
```

## Measurement Accuracy

### Precision

**Time Measurements:**

- Limited by sample rate
- Resolution = 1/sample_rate
- Example: 1 GSa/s → 1 ns resolution

**Voltage Measurements:**

- Limited by ADC resolution
- 8-bit: ~0.4% accuracy
- 12-bit: ~0.024% accuracy

### Improving Accuracy

**1. Increase Sample Rate:**

- Use shorter timebase
- Higher resolution
- Better time accuracy

**2. Enable Snap to Waveform:**

- Uses actual data points
- Eliminates interpolation error
- More precise readings

**3. Average Multiple Measurements:**

- Take several readings
- Calculate mean
- Reduces noise effects

**4. Use Statistics:**

- Enable measurement statistics
- View min/max/mean
- See standard deviation

## Working with Multiple Channels

### Channel-Specific Markers

Markers can be assigned to channels:

**Channel 1 Markers:**

- Snap to C1 waveform only
- Color matches C1
- Independent from other channels

**Channel 2 Markers:**

- Snap to C2 waveform
- Different color
- Separate measurements

### Cross-Channel Measurements

Measure between channels:

**Time Delay:**

```
1. Add T1 at C1 event
2. Add T2 at C2 event
3. Delay = T2 - T1
```

**Voltage Difference:**

```
1. Add V1 on C1
2. Add V2 on C2 (same time)
3. Difference = V1 - V2
```

## Exporting Measurements

### Export to CSV

Save marker measurements:

```
Marker, Type, Value, Unit
V1, Voltage, 3.500, V
V2, Voltage, 1.200, V
ΔV, Delta, 2.300, V
T1, Time, 100.0, µs
T2, Time, 150.0, µs
Δt, Delta, 50.0, µs
f, Frequency, 20.0, kHz
```

**To Export:**

1. Visual Measurements tab
2. Click "Export" button
3. Choose file location
4. Save as CSV

### Include in Waveform Export

When saving waveform data:

- Checkbox: "Include markers"
- Marker positions saved
- Reload with waveform

## Tips and Best Practices

### Effective Measurement

!!! tip "Marker Placement" - Use snap-to-waveform for accuracy - Zoom in for precise positioning - Use cursors for reference - Label markers clearly

### Organization

!!! tip "Managing Many Markers" - Use consistent naming (V1, V2, V3...) - Color code by function - Hide markers not currently needed - Group related markers

### Accuracy

!!! tip "Precise Measurements" - Enable snap to waveform - Increase sample rate for time measurements - Use multiple markers and average - Enable measurement statistics

### Workflow

!!! tip "Efficient Workflow" - Right-click to add markers quickly - Use keyboard shortcuts - Save marker configurations - Export measurements for documentation

## Keyboard Shortcuts

| Shortcut      | Action                    |
| ------------- | ------------------------- |
| `Ctrl+M`      | Add marker at cursor      |
| `Delete`      | Remove selected marker    |
| `Arrow keys`  | Fine-tune marker position |
| `Shift+Arrow` | Large steps               |
| `Tab`         | Select next marker        |
| `Shift+Tab`   | Select previous marker    |

## Troubleshooting

### Marker Not Snapping

**Problem:** Snap to waveform not working

**Solutions:**

1. Enable "Snap to Waveform" in marker properties
2. Ensure channel is enabled and visible
3. Check waveform has data at marker position
4. Zoom in if waveform is too small

### Inaccurate Measurements

**Problem:** Measurements don't match expected values

**Solutions:**

1. Check probe ratio settings
2. Verify voltage scale calibration
3. Enable snap to waveform
4. Increase sample rate for time measurements
5. Check for aliasing

### Markers Disappeared

**Problem:** Markers not visible

**Solutions:**

1. Check visibility checkbox in marker list
2. Markers may be off-screen (reset zoom)
3. Verify markers weren't accidentally deleted
4. Check if correct channel is displayed

### Can't Move Marker

**Problem:** Marker won't drag

**Solutions:**

1. Click directly on marker line
2. Ensure marker is selected
3. Try using arrow keys instead
4. Check if marker is locked

## Examples

### Example 1: Measure Pulse Width

```
Objective: Measure positive pulse width

Steps:
1. Enable channel with pulse signal
2. Set trigger to rising edge
3. Add Time Marker (T1) at rising edge
4. Add Time Marker (T2) at falling edge
5. Read Δt = pulse width

Result: Δt = 125.3 µs
```

### Example 2: Measure Peak-to-Peak

```
Objective: Measure signal Vpp

Steps:
1. Capture waveform
2. Enable snap to waveform
3. Add Voltage Marker (V1) at maximum
4. Add Voltage Marker (V2) at minimum
5. Read ΔV = Vpp

Result: ΔV = 5.02 V
```

### Example 3: Measure Frequency

```
Objective: Measure signal frequency

Steps:
1. Capture periodic signal
2. Add Time Marker (T1) at zero crossing
3. Add Time Marker (T2) at next zero crossing (same direction)
4. Read period (Δt)
5. Frequency automatically calculated

Result:
  Period = 10.04 µs
  Frequency = 99.6 kHz
```

### Example 4: Rise Time (10%-90%)

```
Objective: Measure 10%-90% rise time

Steps:
1. Capture rising edge
2. Calculate 10% and 90% levels:
   Vmin = 0 V, Vmax = 5 V
   V10% = 0.5 V, V90% = 4.5 V
3. Add V1 marker at 0.5 V
4. Add T1 marker where waveform crosses V1
5. Add V2 marker at 4.5 V
6. Add T2 marker where waveform crosses V2
7. Rise time = T2 - T1

Result: Rise time = 2.3 ns
```

## Next Steps

- [Interface Guide](interface.md) - Learn all GUI controls
- [Live View](live-view.md) - Use markers in real-time display
- [FFT Analysis](fft-analysis.md) - Frequency domain measurements
- [User Guide: Measurements](../user-guide/measurements.md) - Automated measurements
