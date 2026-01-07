# GUI Overview

The Siglent Oscilloscope Control GUI provides a powerful, user-friendly interface for controlling your oscilloscope, viewing waveforms in real-time, and performing advanced analysis.

## Introduction

The GUI application offers an alternative to programmatic control with:

- **Real-time Live View** - High-performance waveform display at 1000+ fps
- **Visual Measurements** - Click-and-drag measurement markers
- **FFT Analysis** - Interactive frequency domain analysis
- **Protocol Decoding** - Decode I2C, SPI, and UART protocols
- **VNC Integration** - Remote access to oscilloscope screen
- **Vector Graphics** - Draw shapes and animations in XY mode
- **Export Options** - Save waveforms in multiple formats

## Installation

### Basic GUI Installation

```bash
# Install with GUI support
pip install "SCPI-Instrument-Control[gui]"
```

This installs:

- PyQt6 (GUI framework)
- PyQtGraph (high-performance plotting)
- PyQt6-WebEngine (for VNC display)
- All other GUI dependencies

### Minimal Installation

If you want to try the GUI with minimal dependencies:

```bash
# Basic installation (no GUI extras)
pip install SCPI-Instrument-Control

# GUI will work but with warnings about missing optional features
```

The GUI will automatically detect and warn about missing optional dependencies while remaining functional.

### Full Installation

For all features including vector graphics:

```bash
# Everything
pip install "SCPI-Instrument-Control[all]"
```

## Launching the GUI

### From Command Line

```bash
siglent-gui
```

### From Python

```python
from scpi_control.gui.app import main
main()
```

### With Specific IP Address

```bash
# Set default IP address via environment variable
export SIGLENT_SCOPE_IP=192.168.1.100
siglent-gui
```

## First Launch

When you first launch the GUI, you'll see the connection dialog:

1. **Enter Connection Details**
   - IP Address: Your oscilloscope's IP address (e.g., 192.168.1.100)
   - Port: TCP port (default: 5024)
   - Timeout: Connection timeout in seconds (default: 5.0)

2. **Click Connect**
   - The GUI will attempt to connect
   - On success, the main window opens
   - On failure, an error dialog appears with troubleshooting tips

3. **Save Connection**
   - Check "Remember this connection" to save settings
   - Automatically connects on next launch

## Main Window Layout

The GUI features a clean, intuitive layout:

```
┌─────────────────────────────────────────────────────────────┐
│ File  View  Tools  Help                    [VNC] [Terminal] │ Menu Bar
├─────────────────────────────────────────────────────────────┤
│ [Connect] [Live] [Capture] [Save]  Status: Connected        │ Toolbar
├────────────┬────────────────────────────────────────────────┤
│            │                                                 │
│  Controls  │           Waveform Display                      │
│   Panel    │                                                 │
│            │                                                 │
│ ┌────────┐ │                                                 │
│ │Channel │ │                                                 │
│ │Control │ │                                                 │
│ └────────┘ │                                                 │
│ ┌────────┐ │                                                 │
│ │Trigger │ │                                                 │
│ │Control │ │                                                 │
│ └────────┘ │                                                 │
│ ┌────────┐ │                                                 │
│ │Measure │ │                                                 │
│ │Panel   │ │                                                 │
│ └────────┘ │                                                 │
│ ... tabs   │                                                 │
│            │                                                 │
├────────────┴────────────────────────────────────────────────┤
│ Connected to: SDS824X HD | IP: 192.168.1.100 | FPS: 45      │ Status Bar
└─────────────────────────────────────────────────────────────┘
```

### Layout Components

**Left Panel (Control Panel):**

- Resizable, typically 25% of window width
- Tabbed interface for different control groups
- Channel controls
- Trigger settings
- Measurement panel
- FFT display
- Math functions
- Reference waveforms
- Protocol decoding
- Visual measurements

**Right Panel (Display Panel):**

- Waveform display area (75% of window width)
- High-performance real-time plotting
- Multi-channel display
- Grid and cursors
- Zoom and pan capabilities

**Splitter:**

- Draggable divider between panels
- Resize to your preference
- Settings are remembered

## Key Features

### 1. Connection Management

- **Quick Connect**: One-click connection to saved oscilloscopes
- **Multiple Connections**: Save multiple oscilloscope profiles
- **Auto-Reconnect**: Automatically reconnect after connection loss
- **Status Indicators**: Clear visual feedback on connection state

### 2. Live View Mode

- **Real-Time Display**: Continuous waveform updates
- **High Frame Rate**: 1000+ fps with PyQtGraph
- **Auto-Scaling**: Automatic adjustment to signal amplitude
- **Multi-Channel**: Display up to 4 channels simultaneously
- **Performance**: Optimized for smooth, responsive display

### 3. Waveform Capture

- **Single Capture**: Capture and freeze current waveform
- **Batch Capture**: Capture multiple waveforms sequentially
- **Save Options**: Export to CSV, NPZ, MAT, HDF5
- **Image Export**: Save plots as PNG, PDF, SVG

### 4. Channel Control

- **Per-Channel Settings**: Independent control for each channel
- **Voltage Scale**: Quick voltage/division adjustment
- **Coupling**: DC, AC, or GND coupling selection
- **Probe Ratio**: 1X, 10X, 100X probe compensation
- **Bandwidth Limit**: Toggle 20 MHz bandwidth limiting
- **Enable/Disable**: Quick channel on/off toggle

### 5. Trigger Control

- **Mode Selection**: AUTO, NORMAL, SINGLE, STOP
- **Source Selection**: Channel or external trigger source
- **Level Adjustment**: Visual trigger level indicator
- **Edge Selection**: Rising or falling edge
- **Force Trigger**: Manual trigger override

### 6. Automated Measurements

- **Quick Measurements**: One-click common measurements
- **Measurement Table**: Display multiple measurements
- **Statistics**: Min, max, mean, std dev tracking
- **Continuous Update**: Real-time measurement updates
- **Export**: Save measurement data to CSV

### 7. Visual Measurements

- **Interactive Markers**: Click-and-drag measurement cursors
- **Voltage Markers**: Horizontal lines for voltage measurement
- **Time Markers**: Vertical lines for time measurement
- **Frequency Markers**: Measure periods and frequencies
- **Delta Readouts**: Automatic difference calculations

### 8. FFT Analysis

- **Frequency Domain**: Real-time FFT display
- **Window Functions**: Multiple window options
- **Peak Finding**: Automatic peak detection
- **Dual View**: Time and frequency domain side-by-side
- **Export**: Save FFT data and plots

### 9. Protocol Decoding

- **I2C Decoder**: Decode I2C bus traffic
- **SPI Decoder**: Decode SPI communications
- **UART Decoder**: Decode serial data
- **Visual Overlay**: Decoded data overlaid on waveform
- **Export Decode**: Save decoded data to file

### 10. Reference Waveforms

- **Save References**: Store waveforms as references
- **Compare**: Overlay reference on live waveforms
- **Multiple References**: Save up to 4 reference waveforms
- **Math Operations**: Subtract reference from current

### 11. Math Functions

- **Basic Math**: Add, subtract, multiply, divide channels
- **Advanced Functions**: Integration, differentiation
- **FFT**: Display FFT of any channel
- **Custom Expressions**: Create custom math channels

### 12. VNC Display

- **Remote Screen**: View oscilloscope screen remotely
- **Touch Control**: Interact with oscilloscope display
- **Full Access**: Access all on-screen functions
- **Separate Window**: Dedicated VNC viewer window

### 13. Terminal/SCPI Console

- **Direct Commands**: Send raw SCPI commands
- **Command History**: Recall previous commands
- **Response Display**: View oscilloscope responses
- **Debugging**: Troubleshoot communication issues

## Performance Features

### High-Performance Display

The GUI uses PyQtGraph for high-performance plotting:

- **1000+ FPS**: Smooth real-time display
- **GPU Acceleration**: OpenGL rendering when available
- **Low Latency**: Minimal delay between capture and display
- **Efficient Memory**: Optimized for continuous operation

### Fallback Mode

If PyQtGraph is not available, the GUI falls back to matplotlib:

- **Compatibility**: Works on all systems
- **Lower FPS**: ~10-30 fps typical
- **Same Features**: All functionality preserved
- **Easy Upgrade**: Install PyQtGraph anytime for better performance

## Keyboard Shortcuts

| Shortcut | Action                 |
| -------- | ---------------------- |
| `Ctrl+O` | Open connection dialog |
| `Ctrl+L` | Toggle live view       |
| `Ctrl+C` | Capture waveform       |
| `Ctrl+S` | Save waveform          |
| `Ctrl+E` | Export waveform        |
| `Ctrl+T` | Open terminal          |
| `Ctrl+V` | Open VNC window        |
| `Ctrl+Q` | Quit application       |
| `F5`     | Refresh display        |
| `F11`    | Toggle fullscreen      |
| `Esc`    | Stop live view         |

## Getting Started Workflow

### Basic Measurement Workflow

1. **Launch GUI**

   ```bash
   siglent-gui
   ```

2. **Connect to Oscilloscope**
   - Enter IP address
   - Click "Connect"

3. **Configure Channels**
   - Enable desired channels
   - Set voltage scales
   - Adjust coupling

4. **Set Trigger**
   - Select trigger source
   - Set trigger level
   - Choose trigger mode

5. **Start Live View**
   - Click "Live View" button
   - Observe real-time waveforms

6. **Take Measurements**
   - Click measurement buttons
   - Or use visual markers
   - View results in panel

7. **Capture and Save**
   - Click "Capture" to freeze
   - Click "Save" to export
   - Choose format (CSV, NPZ, etc.)

### Advanced Analysis Workflow

1. **Capture Waveform**
   - Use "Capture" button
   - Waveform freezes on screen

2. **Perform FFT Analysis**
   - Open FFT tab
   - Select window function
   - View frequency spectrum
   - Find peaks

3. **Add Visual Measurements**
   - Click "Visual Measurements" tab
   - Add voltage or time markers
   - Drag to desired positions
   - Read delta values

4. **Compare with Reference**
   - Save current as reference
   - Capture new waveform
   - Overlay reference
   - View differences

5. **Export Results**
   - Save waveform data
   - Export FFT results
   - Save measurement data
   - Export plot images

## System Requirements

### Minimum Requirements

- **OS**: Windows 10+, macOS 10.15+, Linux (Ubuntu 20.04+)
- **Python**: 3.9 or later
- **RAM**: 4 GB
- **Network**: TCP/IP connection to oscilloscope
- **Display**: 1280x720 minimum resolution

### Recommended Requirements

- **RAM**: 8 GB or more
- **Display**: 1920x1080 or higher
- **GPU**: OpenGL 2.0+ support for best performance
- **Network**: Gigabit Ethernet for fastest data transfer

### Dependencies

**Required:**

- PyQt6 >= 6.6.0
- numpy >= 1.20.0
- scipy >= 1.7.0

**Optional (Recommended):**

- pyqtgraph >= 0.13.0 (high-performance plotting)
- PyQt6-WebEngine >= 6.6.0 (VNC display)
- matplotlib >= 3.5.0 (fallback plotting)
- h5py >= 3.0.0 (HDF5 export)

## Troubleshooting

### GUI Won't Launch

```bash
# Check dependencies
python -c "import PyQt6; print('PyQt6 OK')"

# Reinstall GUI extras
pip install --force-reinstall "SCPI-Instrument-Control[gui]"
```

### Poor Performance

```bash
# Install PyQtGraph for better performance
pip install pyqtgraph

# Or install full GUI package
pip install --upgrade "SCPI-Instrument-Control[gui]"
```

### Connection Issues

- Verify oscilloscope IP address
- Check network connectivity (`ping 192.168.1.100`)
- Ensure port 5024 is not blocked
- Try increasing timeout value
- Check oscilloscope network settings

### Display Issues

- Update graphics drivers
- Try disabling GPU acceleration (File → Preferences)
- Reduce display resolution
- Close other graphics-intensive applications

## Next Steps

Now that you understand the GUI overview, explore specific features:

- [Interface Guide](interface.md) - Detailed interface tour
- [Live View](live-view.md) - Real-time waveform display
- [Visual Measurements](visual-measurements.md) - Interactive measurement markers
- [FFT Analysis](fft-analysis.md) - Frequency domain analysis
- [Protocol Decoding](protocol-decoding.md) - Decode I2C/SPI/UART
- [Vector Graphics](vector-graphics.md) - XY mode and drawing

## Additional Resources

- [User Guide](../user-guide/basic-usage.md) - Programmatic API usage
- [Examples](../examples/beginner.md) - Code examples
- [API Reference](../api/oscilloscope.md) - Detailed API docs
- [GitHub Issues](https://github.com/little-did-I-know/SCPI-Instrument-Control/issues) - Report bugs or request features
