# Interface Guide

This guide provides a detailed tour of the GUI interface, explaining every component, control, and feature.

## Main Window Components

The GUI is organized into five main areas:

1. **Menu Bar** - Top menu with File, View, Tools, Help
2. **Toolbar** - Quick access buttons for common actions
3. **Control Panel** - Left sidebar with tabbed controls
4. **Display Area** - Main waveform display (right side)
5. **Status Bar** - Bottom status information

## Menu Bar

### File Menu

**Connect** (`Ctrl+O`)

- Opens connection dialog
- Enter oscilloscope IP address and settings
- Save multiple connection profiles

**Disconnect**

- Closes current oscilloscope connection
- Stops live view if active
- Clears current waveforms

**Save Waveform** (`Ctrl+S`)

- Save current waveform data
- Formats: CSV, NPZ, MAT, HDF5
- Includes metadata (sample rate, timebase, etc.)

**Export Image** (`Ctrl+E`)

- Export current display as image
- Formats: PNG, PDF, SVG
- High-resolution export options

**Recent Connections**

- Quick access to recently used oscilloscopes
- Automatically remembers last 10 connections
- Click to connect instantly

**Preferences**

- Application settings
- Display options
- Performance tuning
- Default values

**Exit** (`Ctrl+Q`)

- Close application
- Prompts to save unsaved data
- Disconnects from oscilloscope

### View Menu

**Live View** (`Ctrl+L`)

- Toggle real-time display
- Starts/stops continuous waveform updates
- Checkbox shows current state

**Fullscreen** (`F11`)

- Toggle fullscreen mode
- Press `Esc` or `F11` to exit
- Maximizes display area

**Zoom In** (`Ctrl++`)

- Zoom into waveform display
- Multiple zoom levels available
- Zooms around cursor position

**Zoom Out** (`Ctrl+-`)

- Zoom out of waveform display
- Reset with `Ctrl+0`

**Reset View** (`Ctrl+0`)

- Reset zoom and pan
- Center waveform
- Auto-scale axes

**Show Grid**

- Toggle display grid
- Checkbox shows current state
- Helps with visual measurements

**Show Cursors**

- Toggle measurement cursors
- Vertical and horizontal lines
- Displays cursor values

**Control Panel**

- Show/hide left control panel
- Gives more space for waveform display
- Automatically hidden in fullscreen

**Status Bar**

- Show/hide bottom status bar
- Displays connection info and stats

### Tools Menu

**Terminal** (`Ctrl+T`)

- Open SCPI terminal window
- Send raw commands
- View responses
- Command history

**VNC Viewer** (`Ctrl+V`)

- Open VNC window
- View oscilloscope screen remotely
- Interact with on-screen controls
- Requires PyQt6-WebEngine

**Capture Single**

- Capture one waveform
- Freezes display
- Save or analyze

**Capture Batch**

- Opens batch capture dialog
- Capture multiple waveforms
- Specify count and interval
- Auto-save options

**Screen Capture**

- Capture oscilloscope screen
- Save as image file
- Useful for documentation

**Auto Scale**

- Automatically adjust voltage scales
- Optimizes display for current signal
- Adjusts all enabled channels

**Clear All Measurements**

- Remove all measurements
- Clears measurement table
- Resets visual markers

### Help Menu

**Documentation**

- Open online documentation
- User guide and API reference
- Opens in web browser

**About**

- Application version information
- Library version
- Dependencies installed
- License information

**Check for Updates**

- Check for new versions
- Links to releases page

**Report Issue**

- Opens GitHub issues page
- Report bugs or request features

## Toolbar

The toolbar provides quick access to common actions:

| Button         | Action                  | Shortcut |
| -------------- | ----------------------- | -------- |
| **Connect**    | Open connection dialog  | `Ctrl+O` |
| **Disconnect** | Close connection        | -        |
| **Live View**  | Start/stop live view    | `Ctrl+L` |
| **Capture**    | Capture single waveform | `Ctrl+C` |
| **Save**       | Save waveform data      | `Ctrl+S` |
| **Auto Scale** | Auto-adjust scales      | -        |
| **Terminal**   | Open SCPI terminal      | `Ctrl+T` |
| **VNC**        | Open VNC viewer         | `Ctrl+V` |

**Connection Indicator:**

- 🟢 **Green**: Connected and ready
- 🟡 **Yellow**: Connecting...
- 🔴 **Red**: Disconnected
- 🟠 **Orange**: Error

## Control Panel

The left panel contains tabbed controls for all oscilloscope functions.

### Channels Tab

Controls for each channel (C1, C2, C3, C4):

**Enable Checkbox**

- Turn channel on/off
- Disabled channels not captured
- Color-coded for each channel

**Voltage Scale**

- Dropdown or slider control
- Common values: 10mV to 10V per division
- Custom value input available

**Voltage Offset**

- Slider or numeric input
- Shifts waveform vertically
- Range: ±5 divisions

**Coupling**

- Radio buttons: DC, AC, GND
- **DC**: Pass all frequencies
- **AC**: Block DC component
- **GND**: Ground (for calibration)

**Probe Ratio**

- Dropdown: 1X, 10X, 100X, 1000X
- Must match physical probe
- Affects voltage readings

**Bandwidth Limit**

- Checkbox: On/Off
- Enables 20 MHz low-pass filter
- Reduces high-frequency noise

**Color Picker**

- Choose display color for channel
- Click to open color dialog
- Defaults: C1=Yellow, C2=Cyan, C3=Magenta, C4=Green

**Channel Info Display**

- Shows current configuration
- Impedance: 1MΩ typical
- Attenuation calculated from probe ratio

### Trigger Tab

Trigger configuration controls:

**Trigger Mode**

- Radio buttons or dropdown
- **AUTO**: Automatic triggering
- **NORMAL**: Wait for trigger
- **SINGLE**: One-shot capture
- **STOP**: Stopped

**Trigger Source**

- Dropdown menu
- Channels: C1, C2, C3, C4
- External: EXT, EX5
- LINE: AC line trigger

**Trigger Level**

- Slider with numeric display
- Range: Based on voltage scale
- Visual indicator on waveform display

**Trigger Slope**

- Radio buttons
- **Rising** (POS): Low-to-high transition
- **Falling** (NEG): High-to-low transition
- **Either**: Both edges

**Trigger Type**

- Advanced trigger modes
- Edge (default)
- Slew rate
- Glitch
- Pulse width
- Runt
- Pattern

**Force Trigger Button**

- Manually trigger immediately
- Ignores trigger conditions
- Useful for testing

**Trigger Status Indicator**

- 🟢 Triggered
- 🟡 Armed (waiting)
- 🔴 Stopped
- Updates in real-time

### Measurements Tab

Automated measurement panel:

**Quick Measurements**

- Buttons for common measurements
- **Frequency**: Signal frequency
- **Period**: Signal period
- **Vpp**: Peak-to-peak voltage
- **Vrms**: RMS voltage
- **Rise Time**: 10%-90% rise
- **Fall Time**: 90%-10% fall
- **Duty Cycle**: Positive pulse width percentage

**Measurement Table**

- Displays active measurements
- Columns: Parameter, Value, Unit, Channel
- Real-time updates
- Click to remove measurement

**Add Measurement**

- Dropdown to select measurement type
- Choose channel
- Add to table
- Up to 8 simultaneous measurements

**Statistics**

- Enable checkbox
- Shows: Current, Min, Max, Mean, Std Dev
- Accumulates over time
- Reset button clears statistics

**Export Measurements**

- Save measurement data to CSV
- Includes timestamps
- Statistics if enabled

### Timebase Tab

Time scale and position control:

**Timebase (Time/Div)**

- Dropdown or slider
- Range: 1ns to 1000s per division
- 14 horizontal divisions total

**Horizontal Position**

- Slider control
- Adjusts trigger position
- Range: ±7 divisions from center

**Delay**

- Numeric input for precise positioning
- Useful for zooming into specific events

**Sample Rate Display**

- Shows current sample rate
- Automatically calculated
- Updates based on timebase

**Memory Depth Display**

- Shows current record length
- Number of samples captured

### Math Tab

Math channel operations:

**Math Channel Selection**

- Math1 or Math2
- Enable checkbox

**Operation Type**

- Dropdown menu:
  - **Add**: C1 + C2
  - **Subtract**: C1 - C2
  - **Multiply**: C1 × C2
  - **Divide**: C1 ÷ C2
  - **FFT**: Frequency transform
  - **Integrate**: Integral
  - **Differentiate**: Derivative

**Source Channels**

- Select input channels
- For binary operations, choose two channels
- For unary, choose one

**Scale and Offset**

- Adjust math result display
- Vertical scale
- Vertical offset

**Color**

- Display color for math channel
- Default: White

### FFT Tab

See [FFT Analysis](fft-analysis.md) for detailed documentation.

**Source Channel**

- Select channel for FFT
- C1, C2, C3, C4, or Math

**Window Function**

- Dropdown: Hanning, Hamming, Blackman, etc.
- Affects spectral leakage

**Display Options**

- Linear or Log scale
- Magnitude in dB or linear
- Phase display toggle

**Peak Finding**

- Automatic peak detection
- Displays top 5 peaks
- Frequency and magnitude

**Export FFT**

- Save frequency domain data
- CSV or NPZ format

### Reference Tab

Reference waveform management:

**Save Reference**

- Button to save current waveform
- Choose reference slot (RefA-RefD)
- Stores in oscilloscope memory

**Load Reference**

- Select reference to display
- Overlays on current waveform
- Multiple references supported

**Reference List**

- Shows saved references
- Name, channel, timestamp
- Delete button for each

**Comparison Mode**

- Overlay: Show reference over current
- Subtract: Show difference
- Split view: Side-by-side

**Reference Display Settings**

- Color picker
- Line style (solid, dashed, dotted)
- Opacity/transparency

### Protocol Decode Tab

See [Protocol Decoding](protocol-decoding.md) for detailed documentation.

**Protocol Selection**

- Radio buttons: I2C, SPI, UART
- Each has specific settings

**Channel Assignment**

- I2C: SDA, SCL channels
- SPI: MOSI, MISO, CLK, CS channels
- UART: TX, RX channels

**Decode Settings**

- Baud rate (UART)
- Clock polarity (SPI)
- Address width (I2C)

**Decode Results**

- Table showing decoded data
- Timestamp, Type, Data, Error
- Export to CSV

### Visual Measurements Tab

See [Visual Measurements](visual-measurements.md) for detailed documentation.

**Add Marker**

- Buttons for marker types:
  - Voltage marker (horizontal)
  - Time marker (vertical)
  - Frequency marker (period)

**Marker List**

- Shows active markers
- Drag to reposition
- Delete button
- Show/hide toggle

**Marker Settings**

- Label text
- Color
- Line style
- Snap to waveform

**Delta Calculations**

- Automatic ΔV between voltage markers
- Automatic Δt between time markers
- Frequency from period markers

### Cursor Tab

Manual cursor control (alternative to visual markers):

**Cursor Mode**

- Off
- Horizontal (voltage)
- Vertical (time)
- Both (X-Y)

**Cursor 1 Position**

- Slider or numeric input
- Displays value (voltage or time)

**Cursor 2 Position**

- Second cursor for delta measurements
- Independent control

**Delta Display**

- Shows difference between cursors
- ΔV, Δt, or both
- Automatic frequency calculation

**Snap to Waveform**

- Checkbox
- Cursor follows waveform data points
- Makes precise measurements easier

### Terminal Tab

SCPI command terminal (can also be separate window):

**Command Input**

- Text box for SCPI commands
- Auto-complete suggestions
- Syntax highlighting

**Send Button**

- Execute command
- Or press Enter

**Response Display**

- Shows oscilloscope responses
- Scrollable history
- Copy/paste support

**Command History**

- Up/Down arrows to recall
- Saved between sessions
- Clear history button

**Common Commands**

- Quick buttons for frequent commands
- *IDN?, *RST, etc.
- Customizable

## Waveform Display Area

The main display shows captured waveforms with several features:

### Display Elements

**Grid**

- 14 horizontal × 10 vertical divisions
- Matches oscilloscope screen
- Toggle on/off in View menu

**Waveforms**

- Color-coded by channel
- Anti-aliased for smooth display
- Adjustable line width

**Trigger Indicator**

- Shows trigger point
- Arrow or vertical line
- Color matches trigger source

**Measurement Markers**

- Visual markers on waveform
- Draggable for interactive measurement
- Labels show values

**Cursor Lines**

- Dashed lines for cursors
- Crosshair at intersection
- Value labels

**Legend**

- Shows enabled channels
- Color and name
- Click to toggle visibility
- Shows voltage scale (V/div)

### Mouse Interactions

**Left Click + Drag**

- Pan waveform view
- Move display area
- Doesn't change oscilloscope settings

**Right Click**

- Context menu
- Quick actions:
  - Add marker at click position
  - Measure at point
  - Copy coordinates
  - Export image

**Mouse Wheel**

- Zoom in/out
- Zooms around mouse position
- Hold Ctrl for horizontal zoom only
- Hold Shift for vertical zoom only

**Double Click**

- Auto-scale view
- Centers waveform
- Optimal zoom level

### Toolbar (Display Specific)

Located above waveform display:

**Grid Toggle** - Show/hide grid
**Cursors Toggle** - Show/hide cursors
**Legend Toggle** - Show/hide legend
**Auto Scale** - Fit waveform to display
**Reset Zoom** - Return to default view

### Display Modes

**Normal Mode**

- Shows all enabled channels
- Stacked vertically
- Shared time axis

**Overlay Mode**

- All channels overlaid
- Shared axes
- Useful for comparison

**Split View Mode**

- Separate subplot for each channel
- Independent vertical scales
- Aligned time axes

## Status Bar

Bottom of window shows real-time information:

**Connection Status**

- "Connected to: [Model] | IP: [Address]"
- Updates when connection changes
- Shows "Disconnected" when not connected

**Oscilloscope Info**

- Model name
- Serial number (if available)
- Firmware version

**Performance Stats**

- **FPS**: Frames per second (live view)
- **Latency**: Network latency (ms)
- **Samples**: Number of samples in current waveform

**Trigger Status**

- Current trigger mode
- Trigger state (Armed, Triggered, Stopped)

**Memory Usage**

- Shows application memory usage
- Warning if memory gets high

**Progress Indicator**

- Progress bar for long operations
- Batch capture progress
- File save/load progress

## Dialogs and Popups

### Connection Dialog

**Fields:**

- IP Address (required)
- Port (default: 5024)
- Timeout (default: 5.0s)
- Name (optional, for saving)

**Buttons:**

- Connect - Attempt connection
- Cancel - Close dialog
- Test - Test connection without connecting
- Save - Save connection profile
- Delete - Remove saved connection

**Recent Connections List**

- Quick select from saved connections
- Double-click to connect

### Batch Capture Dialog

**Settings:**

- Number of captures (1-1000)
- Interval between captures (ms)
- Channels to capture
- Auto-save path
- File format

**Progress:**

- Shows current capture number
- Estimated time remaining
- Cancel button

**Results:**

- Summary of captures
- Failed captures (if any)
- Open folder button

### Export Dialog

**Waveform Export:**

- Format selection (CSV, NPZ, MAT, HDF5)
- File path
- Include metadata checkbox
- Compression options (for NPZ, HDF5)

**Image Export:**

- Format (PNG, PDF, SVG)
- Resolution/DPI
- Transparent background checkbox
- Include legend checkbox

### Error Dialog

**Detailed Error Information:**

- Error message
- Error type
- Timestamp
- Stack trace (expandable)

**Actions:**

- Copy error details
- Report issue (opens GitHub)
- View log file
- Dismiss

**Common Errors:**

- Connection timeout
- Invalid parameter
- Command failed
- File I/O error

## Keyboard Shortcuts Reference

### Global Shortcuts

| Shortcut | Action                           |
| -------- | -------------------------------- |
| `Ctrl+O` | Connect                          |
| `Ctrl+Q` | Quit                             |
| `Ctrl+S` | Save waveform                    |
| `Ctrl+E` | Export image                     |
| `Ctrl+L` | Toggle live view                 |
| `Ctrl+C` | Capture waveform                 |
| `Ctrl+T` | Open terminal                    |
| `Ctrl+V` | Open VNC                         |
| `F5`     | Refresh display                  |
| `F11`    | Fullscreen                       |
| `Esc`    | Exit fullscreen / Stop live view |

### Display Shortcuts

| Shortcut | Action                 |
| -------- | ---------------------- |
| `Ctrl++` | Zoom in                |
| `Ctrl+-` | Zoom out               |
| `Ctrl+0` | Reset zoom             |
| `Ctrl+G` | Toggle grid            |
| `Ctrl+R` | Toggle cursors         |
| `Ctrl+M` | Add marker             |
| `Delete` | Remove selected marker |

### Navigation Shortcuts

| Shortcut    | Action                     |
| ----------- | -------------------------- |
| `Tab`       | Next control panel tab     |
| `Shift+Tab` | Previous control panel tab |
| `Ctrl+1-4`  | Jump to channel 1-4 tab    |
| `Ctrl+5`    | Jump to trigger tab        |
| `Ctrl+6`    | Jump to measurements tab   |

## Tips for Efficient Use

!!! tip "Quick Channel Setup"
Use number keys 1-4 to quickly enable/disable channels without clicking.

!!! tip "Fast Measurements"
Right-click on waveform to add measurement marker at that exact point.

!!! tip "Keyboard Navigation"
Use Tab and arrow keys to navigate controls without mouse.

!!! tip "Custom Layouts"
Resize the splitter and panels to your preference - settings are saved.

!!! tip "Batch Operations"
Hold Shift while clicking multiple measurements to enable them all at once.

## Next Steps

- [Live View Guide](live-view.md) - Learn about real-time display features
- [Visual Measurements](visual-measurements.md) - Use interactive markers effectively
- [FFT Analysis](fft-analysis.md) - Analyze signals in frequency domain
- [Protocol Decoding](protocol-decoding.md) - Decode digital protocols
