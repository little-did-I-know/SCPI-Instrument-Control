# Live View

The Live View feature provides continuous real-time waveform display, allowing you to monitor signals as they change. This guide covers how to use Live View effectively.

## Overview

Live View continuously captures and displays waveforms from your oscilloscope, creating a real-time visualization similar to the oscilloscope's own screen but with additional features and customization options.

### Key Features

- **High Frame Rate**: Up to 1000+ fps with PyQtGraph
- **Low Latency**: Minimal delay between capture and display
- **Multi-Channel**: Display up to 4 channels simultaneously
- **Auto-Scaling**: Automatic signal amplitude adjustment
- **Continuous Update**: Non-stop waveform updates
- **Zero Configuration**: Works out of the box

## Starting Live View

### Using the Toolbar

1. Click the **Live View** button (▶️ icon)
2. Waveforms begin updating automatically
3. Click again (or press `Esc`) to stop

### Using Keyboard Shortcut

Press `Ctrl+L` to toggle Live View on/off

### Using Menu

**View → Live View** or check the menu item

## Live View Interface

### Live View Indicator

When Live View is active:

- **Toolbar Button**: Changes to "Stop" (⏸️ icon)
- **Status Bar**: Shows "LIVE" indicator
- **FPS Counter**: Displays current frame rate
- **Trigger Status**: Updates in real-time

### Display Updates

**Update Cycle:**

1. Oscilloscope captures waveform
2. Data transferred over network
3. GUI processes and displays data
4. Repeat continuously

**Frame Rate:**

- **With PyQtGraph**: 100-1000+ fps typical
- **With Matplotlib**: 10-30 fps typical
- Depends on: Network speed, timebase, enabled channels

## Performance Optimization

### High-Performance Mode (PyQtGraph)

When PyQtGraph is installed, the GUI automatically uses it for optimal performance:

```bash
# Install for high-performance Live View
pip install "SCPI-Instrument-Control[gui]"
```

**Benefits:**

- 10-100x faster rendering
- Smooth, fluid updates
- GPU acceleration (when available)
- Lower CPU usage
- Support for higher frame rates

**Verification:**

- Check console on startup
- Should see: "Using PyQtGraph for waveform display (high performance mode)"
- Status bar shows higher FPS values

### Standard Mode (Matplotlib)

If PyQtGraph is not available, the GUI falls back to matplotlib:

**Characteristics:**

- Lower frame rates (10-30 fps)
- Higher CPU usage
- Still fully functional
- All features available

**When to Use:**

- PyQtGraph incompatible with system
- Troubleshooting display issues
- Preference for matplotlib rendering

### Optimizing Performance

**1. Reduce Number of Channels**

Only enable channels you need:

```
Fewer channels = Higher frame rate
```

- 1 channel: Fastest
- 2 channels: Still fast
- 4 channels: Slower but usable

**2. Adjust Timebase**

Shorter timebase = less data = faster transfer:

- **Fast**: 1µs/div - 10µs/div
- **Medium**: 100µs/div - 1ms/div
- **Slower**: 10ms/div - 1s/div

**3. Network Connection**

- Use Gigabit Ethernet for best performance
- Minimize network hops
- Direct connection preferred
- Reduce network traffic

**4. Close Unnecessary Panels**

Hide panels you're not using:

- Terminal window
- VNC viewer
- Measurement panels (if not needed)

**5. Reduce Display Complexity**

- Disable grid if not needed
- Hide legend
- Minimize markers
- Simple display = faster rendering

## Live View Controls

### Start/Stop

**Start Live View:**

- Click "Live View" button
- Press `Ctrl+L`
- View menu → Live View

**Stop Live View:**

- Click "Stop" button
- Press `Ctrl+L` again
- Press `Esc`

### Auto-Scaling

**Enable Auto-Scale:**

- Tools → Auto Scale
- Right-click display → Auto Scale
- Automatically adjusts voltage scales to fit signal

**Behavior:**

- Monitors signal amplitude
- Adjusts voltage scale when needed
- Maintains optimal display
- Updates automatically during Live View

### Frame Rate Display

Located in status bar:

```
FPS: 45
```

**Interpretation:**

- **100+**: Excellent performance
- **30-100**: Good performance
- **10-30**: Adequate performance
- **<10**: Consider optimization

### Latency Display

Shows network delay:

```
Latency: 25 ms
```

**Typical Values:**

- **<50ms**: Excellent
- **50-100ms**: Good
- **100-200ms**: Acceptable
- **>200ms**: Check network

## Display Modes in Live View

### Normal Mode (Default)

All enabled channels displayed:

- Automatic vertical stacking
- Shared time axis
- Independent voltage scales
- Color-coded channels

### Overlay Mode

All channels overlaid on same axes:

- Easier comparison
- Shared voltage and time axes
- Good for phase relationships
- May be cluttered with many channels

**To Enable:**

- Right-click display → Overlay Mode
- Or View menu → Display Mode → Overlay

### Split View Mode

Separate subplot for each channel:

- Independent voltage and time axes
- More screen real estate per channel
- Easier to see individual details
- Good for unrelated signals

**To Enable:**

- Right-click display → Split View
- Or View menu → Display Mode → Split View

## Live View Features

### Real-Time Measurements

Measurements update continuously in Live View:

**To Use:**

1. Add measurements in Measurements tab
2. Enable statistics for tracking
3. Values update with each frame
4. Statistics accumulate over time

**Example:**

```
Frequency: 1.023 kHz → 1.025 kHz → 1.021 kHz
Vpp: 3.14 V → 3.15 V → 3.13 V
```

### Visual Markers

Add markers that track the live waveform:

**Voltage Markers:**

- Horizontal lines
- Show voltage value
- Follow waveform if snapped

**Time Markers:**

- Vertical lines
- Show time value
- Fixed to time axis

**To Add:**

- Click "Add Marker" button
- Or right-click display → Add Marker
- Drag to position

### Trigger Status

Trigger status updates in real-time:

- 🟢 **Triggered**: Signal triggered successfully
- 🟡 **Armed**: Waiting for trigger
- 🔴 **Stopped**: Trigger stopped

**Useful For:**

- Verifying trigger is working
- Adjusting trigger level
- Ensuring stable display

### Grid and Cursors

**Grid:**

- Toggle with `Ctrl+G`
- Matches oscilloscope divisions
- 14 horizontal × 10 vertical

**Cursors:**

- Toggle with `Ctrl+R`
- Measure specific points
- Delta calculations

## Capturing from Live View

### Quick Capture

While in Live View, press `Ctrl+C` to:

1. Freeze current waveform
2. Stop Live View
3. Allow analysis of captured data
4. Save if desired

### Continuous Capture

Keep Live View running while capturing to file:

**Using Batch Capture:**

1. Tools → Capture Batch
2. Set number of captures
3. Set interval
4. Specify save location
5. Live View continues during capture

**Example:**

- Capture 100 waveforms
- 1 second interval
- Auto-save as NPZ files
- Monitor Live View throughout

## Troubleshooting

### Low Frame Rate

**Symptoms:**

- FPS <10
- Jerky updates
- Slow response

**Solutions:**

1. **Install PyQtGraph**

   ```bash
   pip install pyqtgraph
   ```

2. **Reduce Channels**
   - Disable unused channels
   - Fewer channels = faster updates

3. **Reduce Timebase**
   - Use shorter time scale
   - Less data to transfer

4. **Check Network**
   - Use Gigabit Ethernet
   - Minimize network distance
   - Reduce other network traffic

5. **Close Other Apps**
   - Free up CPU/GPU resources
   - Close unnecessary GUI panels

### Display Freezing

**Symptoms:**

- Display stops updating
- FPS drops to 0
- GUI becomes unresponsive

**Solutions:**

1. **Stop and Restart Live View**
   - Press `Esc` to stop
   - Wait 2 seconds
   - Press `Ctrl+L` to restart

2. **Check Connection**
   - Verify oscilloscope still connected
   - Check network cable
   - Try disconnect/reconnect

3. **Restart Application**
   - Close GUI
   - Relaunch
   - Reconnect to oscilloscope

### High CPU Usage

**Symptoms:**

- CPU at 80-100%
- Fan noise
- System slowdown

**Solutions:**

1. **Verify PyQtGraph Installed**
   - Check console message on startup
   - Install if missing

2. **Reduce Frame Rate**
   - Close some channels
   - Increase timebase
   - Lower update frequency

3. **Disable Grid**
   - Grid rendering can be expensive
   - Toggle off with `Ctrl+G`

4. **Use Normal Mode**
   - Split view uses more resources
   - Switch to normal mode

### Choppy Display

**Symptoms:**

- Stuttering updates
- Inconsistent frame rate
- Visual jittering

**Solutions:**

1. **Check Network Latency**
   - View status bar latency
   - Should be <100ms
   - Reduce network hops

2. **Disable GPU Acceleration**
   - If GPU is causing issues
   - File → Preferences → Display
   - Uncheck "Use GPU acceleration"

3. **Update Graphics Drivers**
   - Outdated drivers can cause issues
   - Update to latest version

## Best Practices

### For Monitoring

!!! tip "Continuous Monitoring" - Use AUTO trigger mode - Enable auto-scaling - Add key measurements to table - Enable statistics for trending

### For Debugging

!!! tip "Debug Workflow" - Start with AUTO mode to see signal - Switch to NORMAL for stable trigger - Adjust trigger level in real-time - Use visual markers for reference points

### For Testing

!!! tip "Test Setup" - Use NORMAL mode for repeatable measurements - Enable all needed measurements - Set up cursors or markers - Capture when event occurs

### For Recording

!!! tip "Recording Data" - Use batch capture during Live View - Set appropriate interval - Monitor in Live View - Auto-save to files

## Keyboard Shortcuts for Live View

| Shortcut | Action                 |
| -------- | ---------------------- |
| `Ctrl+L` | Start/stop Live View   |
| `Ctrl+C` | Capture from Live View |
| `Esc`    | Stop Live View         |
| `Ctrl+G` | Toggle grid            |
| `Ctrl+R` | Toggle cursors         |
| `Ctrl+M` | Add marker             |
| `Ctrl+0` | Reset zoom             |
| `F5`     | Refresh display        |

## Advanced Live View

### With FFT Analysis

**Real-Time Frequency Analysis:**

1. Enable Live View
2. Open FFT tab
3. Select source channel
4. FFT updates in real-time
5. Peaks tracked automatically

**Useful For:**

- Monitoring frequency stability
- Detecting harmonics
- Tracking spectral changes

### With Protocol Decoding

**Live Protocol Decode:**

1. Configure protocol decoder
2. Enable Live View
3. Decoder processes each frame
4. Results update in table
5. Visual overlay on waveform

**Useful For:**

- Monitoring bus traffic
- Debugging communication
- Verifying data integrity

### With Reference Waveforms

**Live Comparison:**

1. Save current waveform as reference
2. Continue Live View
3. Reference overlaid on live data
4. See differences in real-time

**Useful For:**

- Comparing before/after
- Tracking signal degradation
- Quality control

## Performance Comparison

### PyQtGraph vs Matplotlib

| Feature          | PyQtGraph  | Matplotlib  |
| ---------------- | ---------- | ----------- |
| FPS (typical)    | 100-1000+  | 10-30       |
| CPU usage        | Low-Medium | Medium-High |
| GPU acceleration | Yes        | No          |
| Latency          | Lower      | Higher      |
| Installation     | Optional   | Fallback    |
| Platforms        | All        | All         |

### Network Impact

| Connection     | Latency   | FPS Impact |
| -------------- | --------- | ---------- |
| Direct Gigabit | <10ms     | Minimal    |
| LAN Gigabit    | 10-50ms   | Low        |
| LAN 100Mbps    | 20-100ms  | Medium     |
| WiFi           | 50-200ms  | High       |
| Remote/VPN     | 100-500ms | Very High  |

## Next Steps

- [Visual Measurements](visual-measurements.md) - Add interactive markers to live display
- [FFT Analysis](fft-analysis.md) - Real-time frequency analysis
- [Interface Guide](interface.md) - Learn all GUI controls
- [Protocol Decoding](protocol-decoding.md) - Decode protocols in real-time
