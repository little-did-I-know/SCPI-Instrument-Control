# Vector Graphics

The Vector Graphics feature allows you to create and display custom shapes and patterns using XY mode, generate waveforms for animation, and export to arbitrary waveform generators (AWG). This guide covers creating vector graphics in the GUI.

## Overview

Vector graphics mode uses the oscilloscope's XY display mode to draw shapes, patterns, and animations by controlling two channels as X and Y coordinates. The GUI provides tools to:

- Create basic shapes (circles, squares, triangles, etc.)
- Draw custom paths and Lissajous figures
- Generate waveform data for AWG output
- Animate shapes and patterns
- Export to external AWG/DAC devices
- Visualize parametric equations

### Key Features

- **Shape Library**: Pre-defined shapes and patterns
- **Custom Path Drawing**: Draw freehand or define parametric equations
- **Waveform Generation**: Convert shapes to voltage waveforms
- **Animation**: Time-varying patterns and rotations
- **AWG Export**: Send to oscilloscope AWG or external generator
- **Preview Mode**: Real-time preview before output

## Installation

Vector graphics features require the 'fun' extras package:

```bash
pip install "Siglent-Oscilloscope[fun]"
```

**Dependencies:**

- NumPy (for waveform calculations)
- SciPy (for signal processing)
- PyQt6 (for GUI)

**Optional:**

- PyQtGraph (for high-performance preview)

## Accessing Vector Graphics

### Using Menu

**Tools → Vector Graphics** or `Ctrl+X`

Opens the Vector Graphics panel

### Using Toolbar

Click the **Vector Graphics** button (📐 icon)

### Docking Panel

Vector Graphics can be:

- Docked to main window
- Floating window
- Tabbed with other panels

## XY Mode Basics

### What is XY Mode?

XY mode displays one channel on the X-axis and another on the Y-axis, creating 2D plots instead of time-domain waveforms.

**Normal Time Mode:**

```
Y-axis: Voltage
X-axis: Time
```

**XY Mode:**

```
Y-axis: Channel 2 Voltage
X-axis: Channel 1 Voltage
```

### Enabling XY Mode

**In GUI:**

1. Vector Graphics panel
2. Click "Enable XY Mode"
3. Select channels for X and Y

**Channel Assignment:**

- X-axis: Usually Channel 1
- Y-axis: Usually Channel 2
- Adjustable in settings

### XY Mode Applications

**Lissajous Figures:**

- Compare two sine waves
- Measure phase relationships
- Frequency ratio visualization

**Example:**

```
C1: sin(ωt) → X-axis
C2: sin(2ωt) → Y-axis
Result: Lissajous figure (2:1 ratio)
```

**Shape Display:**

- Circles, ellipses
- Custom closed paths
- Vector drawings

**Parametric Equations:**

- Rose curves
- Spirals
- Mathematical patterns

## Shape Library

### Pre-Defined Shapes

The GUI includes a library of common shapes:

**Basic Shapes:**

- Circle
- Square
- Triangle
- Pentagon
- Hexagon
- Star

**Advanced Shapes:**

- Heart
- Infinity symbol
- Trefoil
- Lemniscate
- Spiral

**Lissajous Patterns:**

- 1:1, 1:2, 2:3 ratios
- Various phase offsets
- Amplitude variations

### Creating Shape from Library

**Steps:**

1. Open Vector Graphics panel
2. Click "Shape Library"
3. Select shape from list
4. Adjust parameters:
   - Size
   - Position
   - Rotation
   - Line width
5. Click "Generate"

**Example: Circle**

```
Shape: Circle
Radius: 1.0 V
Center X: 0.0 V
Center Y: 0.0 V
Points: 1000
Frequency: 1 kHz
```

### Shape Parameters

**Size:**

- Radius for circles
- Width/Height for rectangles
- Scale factor for custom shapes

**Position:**

- X offset
- Y offset
- Centers the shape

**Rotation:**

- Angle in degrees
- 0° to 360°
- Rotates around center

**Resolution:**

- Number of points
- Higher = smoother curves
- Typical: 500-2000 points

**Frequency:**

- Waveform frequency
- Affects display speed
- Typical: 100 Hz - 10 kHz

## Custom Path Drawing

### Freehand Drawing

**Interactive Drawing:**

1. Click "Draw Custom Path"
2. Use mouse to draw on canvas
3. Path automatically smoothed
4. Click "Finish" when done

**Features:**

- Automatic path smoothing
- Point reduction for efficiency
- Closed path option
- Undo/redo support

### Parametric Equations

**Define Custom Shapes:**

Enter X and Y as functions of parameter t:

**Example: Rose Curve**

```
X(t) = cos(3t) * cos(t)
Y(t) = cos(3t) * sin(t)
t: 0 to 2π
Points: 1000
```

**Example: Spiral**

```
X(t) = t * cos(10t)
Y(t) = t * sin(10t)
t: 0 to 2π
Points: 2000
```

**Example: Lissajous (3:2 ratio)**

```
X(t) = sin(3*ω*t)
Y(t) = sin(2*ω*t + π/2)
ω = 2π * frequency
```

### Supported Functions

**Mathematical:**

- sin(x), cos(x), tan(x)
- sqrt(x), exp(x), log(x)
- abs(x), sign(x)

**Constants:**

- pi (π)
- e (Euler's number)
- Custom constants

**Operations:**

- +, -, \*, /
- \*\* (power)
- Parentheses

### Path Editor

**Edit Points:**

- Add/remove points
- Drag points to adjust
- Bezier curve handles
- Snap to grid

**Path Operations:**

- Scale
- Rotate
- Mirror (horizontal/vertical)
- Reverse direction

**Path Properties:**

- Total length
- Number of points
- Bounding box
- Closed/open path

## Waveform Generation

### Converting Shape to Waveform

The shape is converted to two waveforms (X and Y):

**Process:**

1. Shape path defined (library or custom)
2. Path sampled at N points
3. X coordinates → Channel 1 waveform
4. Y coordinates → Channel 2 waveform
5. Both waveforms synchronized

**Example:**

```
Circle at origin, radius 1V, 1000 points:

X[n] = cos(2π * n/1000)
Y[n] = sin(2π * n/1000)
n = 0 to 999
```

### Waveform Parameters

**Sample Rate:**

- Determines time resolution
- Higher rate = smoother display
- Typical: 1 kSa/s to 1 MSa/s

**Frequency:**

- How fast shape is drawn
- Lower frequency = slower, smoother
- Higher frequency = faster, may flicker
- Typical: 100 Hz - 5 kHz

**Amplitude:**

- Voltage range
- X and Y independent
- Must fit within oscilloscope range
- Typical: ±1V to ±5V

**DC Offset:**

- Center position
- X and Y independent
- Shifts shape on screen
- Typical: 0V (centered)

### Waveform Preview

**Real-Time Preview:**

- Shows generated waveforms
- Time domain view (both channels)
- XY mode preview
- FFT spectrum view

**Preview Controls:**

- Zoom in/out
- Pan
- Measure points
- Cursors

**Updates:**

- Automatic when parameters change
- Adjustable update rate
- Pause preview for performance

## Animation

### Animated Shapes

**Types of Animation:**

**Rotation:**

- Rotate shape over time
- Speed adjustable
- Clockwise/counter-clockwise

**Scaling:**

- Grow/shrink
- Pulsing effect
- Sine wave modulation

**Translation:**

- Move shape
- Circular orbit
- Linear path

**Morphing:**

- Transition between shapes
- Smooth interpolation

### Animation Parameters

**Rotation Animation:**

```
Rotation Speed: 30°/s
Direction: Clockwise
Loop: Continuous
```

Implemented as:

```python
angle(t) = angle_start + rotation_speed * t
X_rotated = X * cos(angle) - Y * sin(angle)
Y_rotated = X * sin(angle) + Y * cos(angle)
```

**Pulsing Animation:**

```
Pulse Frequency: 2 Hz
Min Scale: 0.5
Max Scale: 1.5
```

Implemented as:

```python
scale(t) = 1.0 + 0.5 * sin(2π * 2 * t)
X_scaled = X * scale(t)
Y_scaled = Y * scale(t)
```

### Animation Timeline

**Timeline Editor:**

- Keyframe-based animation
- Drag keyframes on timeline
- Interpolation between keyframes
- Loop/ping-pong modes

**Keyframes:**

- Position
- Scale
- Rotation
- Opacity (via amplitude)

**Playback Controls:**

- Play/pause
- Speed control
- Frame-by-frame stepping
- Export as image sequence

## Outputting to AWG

### Internal AWG (if available)

Some Siglent oscilloscopes have built-in AWG:

**Output to AWG:**

1. Generate waveform
2. Click "Send to AWG"
3. Select AWG channels
4. Configure output settings
5. Enable AWG output

**AWG Settings:**

- Frequency
- Amplitude
- Offset
- Output impedance (50Ω / High-Z)

**Example:**

```
AWG Ch1 (X): Circle X-component
  Frequency: 1 kHz
  Amplitude: 1 Vpp
  Offset: 0 V

AWG Ch2 (Y): Circle Y-component
  Frequency: 1 kHz
  Amplitude: 1 Vpp
  Offset: 0 V
```

### External AWG/DAC

**Export Waveform Data:**

**Formats:**

- CSV (time, voltage)
- WAV (audio format, for some AWGs)
- Binary (raw samples)
- Arbitrary waveform format (manufacturer-specific)

**Export Steps:**

1. Generate waveform
2. File → Export Waveform
3. Choose format
4. Save files (X and Y separate or combined)
5. Load into external AWG

**CSV Format Example:**

```csv
Time (s), X Voltage (V), Y Voltage (V)
0.000000, 1.000000, 0.000000
0.000001, 0.999500, 0.031411
0.000002, 0.998001, 0.062791
...
```

### Synchronization

**Critical for XY Display:**

- Both channels must be synchronized
- Same sample rate
- Same start time
- Same number of points

**Synchronization Tips:**

- Use same AWG for both outputs
- If using two AWGs, use external sync
- Check relative phase
- Verify with oscilloscope XY mode

## Display Settings

### XY Mode Display

**Aspect Ratio:**

- 1:1 (square) - Default
- 4:3 (standard)
- 16:9 (widescreen)
- Custom

**Persistence:**

- Infinite persistence shows complete path
- Short persistence for animated shapes
- Adjustable decay time

**Line Style:**

- Solid line
- Dotted/dashed (shows direction)
- Color gradient (shows time progression)
- Brightness modulation

**Grid:**

- Show/hide grid
- Grid spacing
- Polar grid option (for circular shapes)

### Color and Brightness

**Color Modes:**

- Single color
- Gradient (start to end)
- Rainbow (full spectrum)
- Custom palette

**Brightness:**

- Constant
- Modulated (shows speed)
- Fades at endpoints

## Practical Examples

### Example 1: Display a Circle

**Objective:** Display a perfect circle in XY mode

**Steps:**

```
1. Open Vector Graphics panel
2. Shape Library → Circle
3. Parameters:
   Radius: 2.0 V
   Center: (0, 0)
   Points: 1000
   Frequency: 1 kHz
4. Click "Generate"
5. Enable XY Mode
6. Adjust oscilloscope:
   C1: 1 V/div, 0 V offset
   C2: 1 V/div, 0 V offset
7. View circle on screen
```

**Result:** Perfect circle displayed on oscilloscope

### Example 2: Lissajous Figure (3:2)

**Objective:** Create a 3:2 Lissajous pattern

**Custom Equation:**

```
X(t) = sin(3 * 2π * f * t)
Y(t) = sin(2 * 2π * f * t)
f = 100 Hz
t: 0 to 1 s
Sample rate: 10 kSa/s
```

**Settings:**

```
Amplitude X: 2 V
Amplitude Y: 2 V
Offset: 0 V
```

**Result:** Three-lobed Lissajous figure

### Example 3: Rotating Square

**Objective:** Animate a rotating square

**Steps:**

```
1. Shape Library → Square
2. Size: 2V × 2V
3. Animation:
   Type: Rotation
   Speed: 45°/s
   Loop: Continuous
4. Generate and preview
5. Send to AWG (if available)
   Or preview in real-time
```

**Result:** Square rotates continuously

### Example 4: Heart Shape

**Objective:** Display a heart using parametric equations

**Parametric Equations:**

```
X(t) = 16 * sin³(t)
Y(t) = 13*cos(t) - 5*cos(2t) - 2*cos(3t) - cos(4t)
t: 0 to 2π
Scale: 0.1 (to fit ±5V range)
```

**Steps:**

```
1. Custom Path → Parametric
2. Enter equations above
3. Set t range and points
4. Generate and preview
5. Adjust scale to fit display
```

**Result:** Heart shape displayed

### Example 5: Spiral Animation

**Objective:** Expanding/contracting spiral

**Parametric with Animation:**

```
X(t, anim) = anim * t * cos(10t)
Y(t, anim) = anim * t * sin(10t)
t: 0 to 2π
anim: 0.5 to 1.5 (sine wave modulation)
```

**Animation:**

```
anim(time) = 1.0 + 0.5 * sin(2π * 1 Hz * time)
```

**Result:** Spiral that grows and shrinks

## Advanced Features

### Multi-Path Compositions

**Combine Multiple Shapes:**

- Draw several shapes sequentially
- Rapid switching between paths
- Creates composite images

**Implementation:**

- Switch between waveforms rapidly
- Use blanking signal to control visibility
- Requires fast AWG or pattern generator

### 3D Projections

**Project 3D shapes to 2D:**

- Define shape in 3D (X, Y, Z)
- Apply rotation matrix
- Project to XY plane
- Animate rotation for 3D effect

**Example: Rotating Cube**

```python
# Define cube vertices in 3D
# Apply rotation matrix
# Project to 2D (X, Y)
# Connect vertices with lines
# Animate rotation angles
```

### Bitmap to Vector

**Convert Images to Vector Paths:**

1. Import bitmap image
2. Edge detection
3. Trace edges to paths
4. Simplify path (reduce points)
5. Export as waveform

**Use Cases:**

- Display logos
- Custom artwork
- Text rendering

### Text Rendering

**Display Text:**

- Use vector font
- Convert characters to paths
- Generate waveform
- Display in XY mode

**Font Options:**

- Hershey vector fonts
- Single-stroke fonts
- Custom fonts

## Troubleshooting

### Shape Not Displaying

**Problem:** XY mode enabled but no shape visible

**Solutions:**

1. **Check Channels Enabled**
   - Both X and Y channels must be on
   - Verify in Channels tab

2. **Verify Voltage Scales**
   - Shape may be off-screen
   - Adjust V/div to see full shape
   - Use Auto Scale

3. **Check Waveform Generated**
   - Preview shows waveforms
   - Non-zero amplitude
   - Correct frequency

4. **Verify AWG Output**
   - AWG enabled and running
   - Cables connected correctly
   - Output impedance correct

### Distorted Shape

**Problem:** Shape is stretched or squashed

**Solutions:**

1. **Match Voltage Scales**
   - Set C1 and C2 to same V/div
   - Equal scales for equal aspect ratio

2. **Check Probe Ratios**
   - Both channels same probe ratio
   - Usually 1X for AWG output

3. **Verify Calibration**
   - Oscilloscope calibrated
   - AWG calibrated
   - Check with known signal (circle)

### Flickering Display

**Problem:** Shape flickers or is unstable

**Solutions:**

1. **Adjust Frequency**
   - Too high: Flickers
   - Too low: Draws slowly
   - Sweet spot: 500 Hz - 2 kHz

2. **Check Synchronization**
   - X and Y must be synchronized
   - Same start time
   - Use same AWG for both

3. **Persistence Settings**
   - Enable infinite persistence
   - Or increase persistence time
   - Helps with slower shapes

### Incomplete Shape

**Problem:** Shape not closed or has gaps

**Solutions:**

1. **Increase Points**
   - More points = smoother curve
   - Try 1000-2000 points

2. **Check Path Closure**
   - For closed shapes, first point = last point
   - Enable "Close Path" option

3. **Adjust Sample Rate**
   - Higher sample rate
   - More samples per cycle

### Animation Jerky

**Problem:** Animation not smooth

**Solutions:**

1. **Increase Frame Rate**
   - Higher update rate
   - May impact performance

2. **Reduce Animation Speed**
   - Slower animations appear smoother
   - Adjust speed parameter

3. **Check CPU Load**
   - Close unnecessary apps
   - Reduce preview resolution
   - Use PyQtGraph if available

## Tips and Best Practices

### Shape Design

!!! tip "Good Shapes for XY Display" - **Closed paths** work best (circle, square) - **Smooth curves** display better than sharp angles - **Equal aspect ratio** requires matching X and Y scales - **1000-2000 points** is optimal resolution

### Frequency Selection

!!! tip "Choosing Frequency" - **100-500 Hz**: Best for complex shapes - **500-2000 Hz**: Good balance for most shapes - **2-5 kHz**: Simple shapes, faster animation - **>5 kHz**: May flicker, test on scope

### Amplitude Range

!!! tip "Voltage Levels" - Stay within ±5V for most scopes - Use full range for best resolution - Match AWG output to scope input range - Account for probe attenuation

### Performance

!!! tip "Optimizing Performance" - Use PyQtGraph for preview (10x faster) - Reduce points for faster generation - Disable preview during parameter adjustment - Export to AWG for best display quality

### Synchronization

!!! tip "Keeping X and Y in Sync" - Use same AWG for both channels - If separate AWGs, use external clock sync - Check phase alignment with simple shapes - Test with circle before complex shapes

## Keyboard Shortcuts

| Shortcut     | Action                     |
| ------------ | -------------------------- |
| `Ctrl+X`     | Open Vector Graphics panel |
| `Ctrl+N`     | New shape                  |
| `Ctrl+G`     | Generate waveform          |
| `Ctrl+P`     | Preview                    |
| `Ctrl+E`     | Export to AWG              |
| `Space`      | Play/pause animation       |
| `Arrow keys` | Fine-tune position         |
| `Ctrl+Arrow` | Large position steps       |
| `+/-`        | Increase/decrease size     |
| `R`          | Rotate 90°                 |

## Example Workflows

### Workflow 1: Quick Circle Test

```
Purpose: Verify XY mode is working

1. Vector Graphics → Shape Library
2. Select "Circle"
3. Keep defaults (radius=1V, 1kHz)
4. Click "Generate"
5. Enable XY Mode
6. Adjust scope: C1 and C2 to 500mV/div
7. Should see perfect circle

Time: 30 seconds
```

### Workflow 2: Custom Logo Display

```
Purpose: Display company logo on oscilloscope

1. Import logo image (bitmap)
2. Vector Graphics → Bitmap to Vector
3. Adjust edge detection threshold
4. Simplify path (reduce points to <2000)
5. Scale to fit ±5V range
6. Generate waveform
7. Export to AWG
8. Display on oscilloscope

Time: 5-10 minutes
```

### Workflow 3: Animated Presentation

```
Purpose: Create animated shape for demo

1. Design shape (heart, star, etc.)
2. Add rotation animation (30°/s)
3. Add pulsing (2 Hz sine)
4. Preview animation
5. Adjust timing and speeds
6. Export animation keyframes
7. Send to AWG with automation

Time: 10-15 minutes
```

## Integration with Other Features

### With Live View

**Real-Time XY Display:**

- Enable Live View
- Switch to XY mode
- See shape update in real-time
- Adjust parameters dynamically

### With FFT Analysis

**Analyze Waveform Components:**

- Generate shape waveform
- Run FFT on X and Y channels
- See frequency components
- Verify harmonic content

### With Measurements

**Measure Shape Properties:**

- Vpp (size of shape)
- Frequency (drawing speed)
- Phase (X vs Y offset)
- Duty cycle (for non-symmetric shapes)

### With Reference Waveforms

**Compare Shapes:**

- Save current shape as reference
- Generate new shape
- Overlay in XY mode
- See differences

## Mathematical Background

### Parametric Equations

**General Form:**

```
X = f(t)
Y = g(t)
t ∈ [t_start, t_end]
```

**Common Parametric Shapes:**

**Circle:**

```
X(t) = R * cos(t)
Y(t) = R * sin(t)
t: 0 to 2π
```

**Ellipse:**

```
X(t) = a * cos(t)
Y(t) = b * sin(t)
t: 0 to 2π
```

**Lissajous (m:n ratio):**

```
X(t) = A * sin(m*ω*t + φ)
Y(t) = B * sin(n*ω*t)
```

**Rose Curve (k petals):**

```
X(t) = cos(k*t) * cos(t)
Y(t) = cos(k*t) * sin(t)
```

### Rotation Matrix

**Rotate point (x, y) by angle θ:**

```
X' = x*cos(θ) - y*sin(θ)
Y' = x*sin(θ) + y*cos(θ)
```

**For animation:**

```
θ(t) = ω * t
ω = rotation speed (rad/s)
```

### Scaling Transform

**Scale by factor s:**

```
X' = s * X
Y' = s * Y
```

**Anisotropic scaling:**

```
X' = sx * X
Y' = sy * Y
```

## Safety and Limitations

### AWG Limitations

!!! warning "AWG Output Limits" - Check maximum voltage rating - Don't exceed current limits - Verify load impedance - Use appropriate cables

### Oscilloscope Input

!!! warning "Protect Oscilloscope Inputs" - Stay within ±400V (typical max input) - Check probe rating - Don't connect AWG directly to HV circuits - Use proper grounding

### Frequency Limits

**Sample Rate Nyquist:**

- AWG sample rate ≥ 2 × max frequency component
- Higher sample rate for smoother curves
- Check AWG specifications

**Display Refresh:**

- Some shapes require higher persistence
- Flickering possible at high frequencies
- Adjust based on oscilloscope capabilities

## Next Steps

- [Interface Guide](interface.md) - Learn all GUI controls
- [Live View](live-view.md) - Use XY mode in real-time display
- [FFT Analysis](fft-analysis.md) - Analyze waveform harmonics
- [User Guide: Advanced Features](../user-guide/advanced-features.md) - Programmatic waveform generation
