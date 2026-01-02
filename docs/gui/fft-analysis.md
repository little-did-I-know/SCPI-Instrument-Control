# FFT Analysis

The FFT Analysis feature provides real-time frequency domain analysis of waveforms. This guide covers how to use FFT analysis in the GUI.

## Overview

Fast Fourier Transform (FFT) converts time-domain signals to frequency domain, revealing:

- Frequency components
- Harmonic content
- Noise characteristics
- Spectral purity
- Modulation analysis

### Key Features

- **Real-Time FFT**: Updates with live view
- **Multiple Windows**: Hanning, Hamming, Blackman, etc.
- **Peak Detection**: Automatic peak finding
- **Dual Display**: Time and frequency domain together
- **Export**: Save FFT data and plots
- **Customizable**: Scale, units, and display options

## Opening FFT Analysis

### Using Control Panel

1. Click **FFT** tab in left control panel
2. FFT panel opens
3. Configure settings
4. Enable FFT display

### Quick Access

- Toolbar → FFT button
- Or View menu → FFT Analysis
- Or `Ctrl+F` keyboard shortcut

## FFT Panel Controls

### Source Channel Selection

**Select Input Channel:**
- Dropdown menu: C1, C2, C3, C4
- Choose channel to analyze
- Can also select Math channels

**Requirements:**
- Channel must be enabled
- Waveform must be captured
- Sufficient data points

### Window Function

**Purpose:** Reduces spectral leakage

**Available Windows:**
- **Rectangular**: No windowing, best resolution
- **Hanning**: General purpose, good for most signals
- **Hamming**: Similar to Hanning
- **Blackman**: Low sidelobes, good for weak signals
- **Bartlett**: Triangular window
- **Flat-top**: Best for amplitude accuracy

**Selection:**
```
Window dropdown → Choose function
```

**When to Use:**
- **Hanning**: Default, good all-around
- **Blackman**: Finding weak signals near strong ones
- **Flat-top**: Accurate amplitude measurements
- **Rectangular**: Maximum frequency resolution

### Display Options

**Magnitude Scale:**
- **dB** (Decibels): Logarithmic scale
- **Linear**: Linear amplitude scale

**Toggle:**
```
☐ dB Scale
☑ Linear Scale
```

**Frequency Scale:**
- **Linear**: Equal frequency spacing
- **Logarithmic**: Equal spacing per decade

**Phase Display:**
```
☑ Show Phase
```
- Displays phase spectrum
- Shows phase angle vs frequency
- Useful for filter analysis

## FFT Display

### Frequency Spectrum View

**Main Display:**
- X-axis: Frequency (Hz, kHz, MHz)
- Y-axis: Magnitude (dB or linear)
- Plot shows spectral content

**Features:**
- Grid overlay
- Peak markers
- Cursor measurements
- Zoom and pan

### Dual View Mode

Show both time and frequency domain:

**Layout:**
```
┌─────────────────┬─────────────────┐
│  Time Domain    │  Frequency      │
│  Waveform       │  Spectrum (FFT) │
└─────────────────┴─────────────────┘
```

**Enable:**
- View menu → Dual View
- Or checkbox in FFT panel

### Split View Options

**Vertical Split:**
- Time domain on left
- FFT on right
- Wide format

**Horizontal Split:**
- Time domain on top
- FFT on bottom
- Tall format

## Peak Detection

### Automatic Peak Finding

**Enable:**
```
☑ Enable Peak Detection
```

**Settings:**
- Number of peaks: 1-10
- Minimum height threshold
- Minimum peak separation

### Peak Display

**Peak Table:**
```
Peak | Frequency    | Magnitude
-----|--------------|----------
1    | 1.000 kHz    | -10.5 dB
2    | 2.000 kHz    | -25.3 dB
3    | 3.000 kHz    | -35.1 dB
```

**On Plot:**
- Markers at peak frequencies
- Labels showing values
- Color-coded

### Peak Analysis

**Fundamental Frequency:**
- Highest peak (usually)
- Base frequency of signal

**Harmonics:**
- Peaks at integer multiples
- 2f, 3f, 4f, etc.
- Indicates distortion

**THD (Total Harmonic Distortion):**
```
THD = √(H2² + H3² + H4² + ...) / H1
```

Where:
- H1 = fundamental
- H2, H3, etc. = harmonics

## Live FFT

### Real-Time Analysis

**Enable Live View + FFT:**

1. Start Live View (`Ctrl+L`)
2. Open FFT tab
3. FFT updates in real-time
4. Watch spectral changes

**Frame Rate:**
- Depends on FFT size
- Typical: 10-100 updates/sec
- Balances speed vs resolution

### Dynamic Range

**Auto-Scaling:**
```
☑ Auto Scale Magnitude
```
- Automatically adjusts Y-axis
- Keeps peaks visible
- Adapts to signal changes

**Manual Range:**
- Set min/max magnitude
- Fixed scale for comparison
- Better for monitoring

## FFT Settings

### FFT Size

**Number of Points:**
- 256, 512, 1024, 2048, 4096, 8192
- More points = better frequency resolution
- Fewer points = faster updates

**Trade-offs:**
```
Larger FFT:
  ✓ Better frequency resolution
  ✗ Slower computation
  ✗ Less time resolution

Smaller FFT:
  ✓ Faster updates
  ✓ Better time resolution
  ✗ Coarser frequency resolution
```

### Frequency Range

**Nyquist Limit:**
```
Max frequency = Sample Rate / 2
```

**Example:**
- Sample rate: 1 GSa/s
- Max frequency: 500 MHz

**Display Range:**
- Full range: DC to Nyquist
- Custom range: Zoom to region of interest

### Averaging

**Enable Averaging:**
```
☑ Average FFT
Number of averages: 10
```

**Benefits:**
- Reduces noise
- Smooths spectrum
- Better for weak signals

**Types:**
- **Linear**: Simple average
- **Exponential**: Weighted average, more recent data

## Measurement Cursors

### Frequency Cursors

**Add Cursors:**
- Right-click FFT display
- Select "Add Frequency Cursor"
- Or use cursor panel

**Features:**
- Measure specific frequencies
- Read magnitude at cursor
- Delta between cursors

**Example:**
```
Cursor 1: 1.000 kHz, -12.5 dB
Cursor 2: 2.000 kHz, -28.3 dB
Δf: 1.000 kHz
ΔMag: -15.8 dB
```

### Peak Markers

**Auto-Markers:**
- Automatically placed at peaks
- Track peak movement
- Show frequency and level

**Manual Markers:**
- Place at any frequency
- Measure harmonics
- Compare levels

## Exporting FFT Data

### Export Spectrum

**File Formats:**
- **CSV**: Frequency, magnitude, phase
- **NPZ**: NumPy format with metadata
- **MAT**: MATLAB format

**To Export:**
1. FFT tab → Export button
2. Choose format
3. Select file location
4. Save

**CSV Format:**
```
Frequency (Hz), Magnitude (dB), Phase (rad)
0.00, -80.5, 0.0
100.00, -65.2, 0.52
200.00, -55.1, 1.04
...
```

### Export Plot

**Save Image:**
- PNG, PDF, SVG formats
- High resolution
- Include or exclude annotations

**To Export:**
1. Right-click FFT display
2. "Export Image"
3. Choose format and settings
4. Save

## Applications

### Frequency Measurement

**Measure Signal Frequency:**

1. Capture waveform
2. Enable FFT
3. Enable peak detection
4. Read fundamental frequency

**Accuracy:**
- Limited by FFT resolution
- Resolution = Sample Rate / FFT Size
- Example: 1 GSa/s / 8192 = 122 kHz resolution

### Harmonic Analysis

**Identify Harmonics:**

1. Look for peaks at multiples of fundamental
2. Measure harmonic levels
3. Calculate THD

**Example:**
```
Fundamental (f₀): 1.00 kHz @ -10 dB
2nd Harmonic (2f₀): 2.00 kHz @ -30 dB
3rd Harmonic (3f₀): 3.00 kHz @ -40 dB
```

### Noise Analysis

**Measure Noise Floor:**

1. Capture signal
2. Enable FFT
3. Look at regions without peaks
4. Noise floor = baseline level

**Signal-to-Noise Ratio:**
```
SNR = Peak Level - Noise Floor
```

**Example:**
- Peak: -10 dB
- Noise floor: -70 dB
- SNR: 60 dB

### Modulation Analysis

**AM (Amplitude Modulation):**
- Carrier frequency peak
- Sidebands at carrier ± modulation frequency

**FM (Frequency Modulation):**
- Carrier and sidebands
- Sideband spacing = modulation frequency
- Bessel function pattern

## Advanced FFT Features

### Spectrogram View

**Time-Frequency Display:**
- Shows how spectrum changes over time
- Color map: frequency vs time vs magnitude
- Good for transient signals

**Enable:**
```
FFT tab → Display Mode → Spectrogram
```

**Features:**
- Time on X-axis
- Frequency on Y-axis
- Color shows magnitude
- Waterfall effect

### Power Spectral Density

**PSD Mode:**
- Power per frequency bin
- Units: V²/Hz or dBm/Hz
- Better for noise analysis

**Enable:**
```
FFT tab → Mode → PSD
```

### Overlap Processing

**Windowed Overlap:**
- Consecutive FFTs overlap
- Smoother spectrum
- Better time resolution

**Settings:**
- 0%: No overlap
- 50%: Common choice
- 75%: Maximum smoothing

## Troubleshooting

### No FFT Display

**Problem:** FFT panel empty

**Solutions:**
1. Ensure channel is enabled
2. Capture waveform first
3. Check FFT is enabled (checkbox)
4. Verify sufficient data points

### Noisy Spectrum

**Problem:** Spectrum very noisy

**Solutions:**
1. Enable averaging
2. Increase number of averages
3. Use Blackman window
4. Check for electromagnetic interference

### Poor Frequency Resolution

**Problem:** Can't resolve close frequencies

**Solutions:**
1. Increase FFT size (e.g., 8192 points)
2. Use longer capture time
3. Use rectangular window for best resolution
4. Reduce frequency span (zoom in)

### Spectral Leakage

**Problem:** Energy spreading to adjacent bins

**Solutions:**
1. Use windowing function (Hanning, Blackman)
2. Increase FFT size
3. Adjust sample rate for integer periods
4. Use flat-top window for amplitude accuracy

## Tips and Best Practices

### Window Selection

!!! tip "Choosing Windows"
    - **General use**: Hanning window
    - **Amplitude accuracy**: Flat-top window
    - **Weak signals**: Blackman window
    - **Best resolution**: Rectangular (no window)

### FFT Size

!!! tip "Optimizing FFT Size"
    - Larger size: Better frequency resolution
    - Smaller size: Faster updates, better for live view
    - Common sizes: 1024, 2048, 4096
    - Use power of 2 for fastest computation

### Averaging

!!! tip "Using Averaging"
    - Always average for noise reduction
    - 10-100 averages typical
    - More averages = smoother spectrum
    - Exponential averaging for tracking changes

### Measurement

!!! tip "Accurate Measurements"
    - Use peak detection for automatic measurement
    - Cursors for manual measurement
    - Enable averaging for stability
    - Check Nyquist limit (max freq = sample rate / 2)

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+F` | Open FFT panel |
| `Ctrl+P` | Toggle peak detection |
| `Ctrl+A` | Toggle averaging |
| `Ctrl+D` | Toggle dual view |
| `Ctrl+E` | Export FFT data |

## Example Workflows

### Example 1: Measure Fundamental Frequency

```
Objective: Accurately measure signal frequency

Steps:
1. Capture waveform (Ctrl+C)
2. Open FFT tab
3. Select source channel
4. Enable peak detection
5. Read fundamental frequency from peak table

Result: f₀ = 1.0234 kHz
```

### Example 2: Analyze Harmonics

```
Objective: Measure harmonic distortion

Steps:
1. Capture waveform
2. Enable FFT with Hanning window
3. Enable peak detection (find 5 peaks)
4. Identify fundamental and harmonics
5. Calculate THD from harmonic levels

Result:
  f₀ = 1.00 kHz @ -10 dB (fundamental)
  2f₀ = 2.00 kHz @ -35 dB (2nd harmonic)
  3f₀ = 3.00 kHz @ -45 dB (3rd harmonic)
  THD = 2.8%
```

### Example 3: Find Interference

```
Objective: Identify unwanted frequency components

Steps:
1. Capture signal in FFT mode
2. Use Blackman window (good for weak signals)
3. Enable averaging (100 averages)
4. Look for unexpected peaks
5. Use cursors to measure interference frequency

Result: Interference at 50 Hz (power line)
```

## Next Steps

- [Visual Measurements](visual-measurements.md) - Measure FFT peaks with markers
- [User Guide: Advanced Features](../user-guide/advanced-features.md) - Programmatic FFT analysis
- [Interface Guide](interface.md) - Learn all GUI controls
- [Live View](live-view.md) - Real-time FFT updates
