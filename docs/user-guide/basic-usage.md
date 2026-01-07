# Basic Usage

This guide covers the fundamental concepts and patterns for using the Siglent Oscilloscope Control library.

## Connecting to Your Oscilloscope

### Basic Connection

The simplest way to connect is by creating an `Oscilloscope` instance with the IP address:

```python
from scpi_control import Oscilloscope

# Create instance
scope = Oscilloscope('192.168.1.100')

# Connect
scope.connect()

# Get device information
print(scope.identify())

# When done
scope.disconnect()
```

### Context Manager (Recommended)

The recommended approach is using a context manager, which automatically handles connection and disconnection:

```python
from scpi_control import Oscilloscope

with Oscilloscope('192.168.1.100') as scope:
    # Connection happens automatically
    print(scope.identify())
    # Work with oscilloscope...
    # Disconnection happens automatically
```

!!! tip "Why Use Context Manager?" - Automatic connection/disconnection - Ensures cleanup even if errors occur - More concise and Pythonic - Prevents resource leaks

### Connection Parameters

You can customize the connection settings:

```python
scope = Oscilloscope(
    host='192.168.1.100',      # IP address or hostname
    port=5024,                  # TCP port (default: 5024)
    timeout=10.0                # Command timeout in seconds (default: 5.0)
)
```

## Device Information

### Getting Identification

```python
# Full identification string
idn = scope.identify()
print(idn)
# Output: Siglent Technologies,SDS824X HD,SDSMMDD1XXXXX,8.2.5.1.37R9

# Parsed device information
info = scope.device_info
print(f"Manufacturer: {info['manufacturer']}")
print(f"Model: {info['model']}")
print(f"Serial: {info['serial']}")
print(f"Firmware: {info['firmware']}")
```

### Model Capabilities

The library automatically detects your oscilloscope model and its capabilities:

```python
caps = scope.model_capability

print(f"Series: {caps.series}")
print(f"Model: {caps.model_name}")
print(f"Channels: {caps.num_channels}")
print(f"Bandwidth: {caps.bandwidth_mhz} MHz")
print(f"Sample Rate: {caps.max_sample_rate/1e9} GSa/s")
print(f"Memory Depth: {caps.max_memory_depth/1e6} Mpts")
```

!!! info "Supported Models" - SDS800X HD Series (e.g., SDS824X HD) - SDS1000X-E Series - SDS2000X Plus Series - SDS5000X Series

## Working with Channels

### Accessing Channels

Channels are accessed as properties of the oscilloscope:

```python
# Access specific channels
ch1 = scope.channel1
ch2 = scope.channel2
ch3 = scope.channel3
ch4 = scope.channel4

# Or dynamically
channel_num = 1
ch = getattr(scope, f'channel{channel_num}')
```

### Enabling/Disabling Channels

```python
# Enable channel
scope.channel1.enabled = True
# Or
scope.channel1.enable()

# Disable channel
scope.channel1.enabled = False
# Or
scope.channel1.disable()

# Check if enabled
if scope.channel1.enabled:
    print("Channel 1 is active")
```

### Basic Channel Configuration

```python
# Configure channel 1
scope.channel1.enabled = True
scope.channel1.voltage_scale = 1.0       # 1V per division
scope.channel1.voltage_offset = 0.0      # Center on 0V
scope.channel1.coupling = "DC"           # DC coupling
scope.channel1.probe_ratio = 10.0        # 10X probe
```

#### Coupling Modes

```python
# Available coupling modes
scope.channel1.coupling = "DC"    # DC coupling
scope.channel1.coupling = "AC"    # AC coupling (blocks DC)
scope.channel1.coupling = "GND"   # Ground (for offset calibration)
```

#### Voltage Scale

```python
# Set voltage scale (volts per division)
scope.channel1.voltage_scale = 1.0    # 1V/div
scope.channel1.voltage_scale = 0.5    # 500mV/div
scope.channel1.voltage_scale = 2.0    # 2V/div

# Common values: 0.001, 0.002, 0.005, 0.01, 0.02, 0.05,
#                0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0

# Read current scale
scale = scope.channel1.voltage_scale
print(f"Current scale: {scale} V/div")
```

#### Voltage Offset

```python
# Set vertical offset
scope.channel1.voltage_offset = 0.0     # Center on screen
scope.channel1.voltage_offset = 2.0     # Shift up by 2V
scope.channel1.voltage_offset = -1.5    # Shift down by 1.5V

# Read current offset
offset = scope.channel1.voltage_offset
print(f"Current offset: {offset} V")
```

#### Probe Ratio

```python
# Common probe ratios
scope.channel1.probe_ratio = 1.0      # 1X probe (direct)
scope.channel1.probe_ratio = 10.0     # 10X probe (most common)
scope.channel1.probe_ratio = 100.0    # 100X probe (high voltage)

# Read current probe ratio
ratio = scope.channel1.probe_ratio
print(f"Probe ratio: {ratio}X")
```

### Bandwidth Limiting

```python
# Enable 20 MHz bandwidth limit (reduces noise)
scope.channel1.bandwidth_limit = "ON"

# Disable bandwidth limit (full bandwidth)
scope.channel1.bandwidth_limit = "OFF"

# Check current setting
bwl = scope.channel1.bandwidth_limit
```

### Getting Channel Configuration

```python
# Get all channel settings at once
config = scope.channel1.get_configuration()

print(f"Enabled: {config['enabled']}")
print(f"Coupling: {config['coupling']}")
print(f"Scale: {config['voltage_scale']} V/div")
print(f"Offset: {config['voltage_offset']} V")
print(f"Probe: {config['probe_ratio']}X")
print(f"BWL: {config['bandwidth_limit']}")
```

## Trigger Configuration

### Basic Trigger Setup

```python
# Configure trigger
scope.trigger.mode = "AUTO"        # Auto, Normal, Single, or Stop
scope.trigger.source = "C1"        # Trigger source (C1, C2, C3, C4, EXT, LINE)
scope.trigger.level = 0.0          # Trigger level in volts
scope.trigger.slope = "POS"        # Rising edge (POS) or falling edge (NEG)
```

### Trigger Modes

```python
# AUTO mode - triggers automatically even without signal
scope.trigger.mode = "AUTO"

# NORMAL mode - only triggers when condition is met
scope.trigger.mode = "NORMAL"

# SINGLE mode - triggers once then stops
scope.trigger.mode = "SINGLE"

# STOP mode - stops triggering
scope.trigger.mode = "STOP"
```

### Trigger Sources

```python
# Trigger on channels
scope.trigger.source = "C1"    # Channel 1
scope.trigger.source = "C2"    # Channel 2
scope.trigger.source = "C3"    # Channel 3
scope.trigger.source = "C4"    # Channel 4

# External trigger
scope.trigger.source = "EXT"   # External trigger input

# Line trigger
scope.trigger.source = "LINE"  # AC line frequency
```

### Trigger Level

```python
# Set trigger level (in volts)
scope.trigger.level = 0.0      # Trigger at 0V
scope.trigger.level = 1.5      # Trigger at 1.5V
scope.trigger.level = -0.5     # Trigger at -0.5V

# Read current level
level = scope.trigger.level
print(f"Trigger level: {level} V")
```

## Acquisition Control

### Run/Stop Control

```python
# Start acquisition
scope.run()

# Stop acquisition
scope.stop()

# Check acquisition state
if scope.is_running:
    print("Acquisition running")
else:
    print("Acquisition stopped")
```

### Single Trigger

```python
# Trigger single acquisition (useful in NORMAL mode)
scope.trigger_single()

# Wait for trigger to complete
import time
timeout = 5.0
start = time.time()
while (time.time() - start) < timeout:
    status = scope.query(":TRIG:STAT?").strip()
    if status == "Stop":
        print("Trigger captured!")
        break
    time.sleep(0.1)
else:
    print("Trigger timeout")
```

### Timebase Configuration

```python
# Set timebase (seconds per division)
scope.timebase = 1e-3          # 1 ms/div
scope.timebase = 100e-6        # 100 µs/div
scope.timebase = 1e-6          # 1 µs/div

# Read current timebase
tb = scope.timebase
print(f"Timebase: {tb*1e6} µs/div")
```

## Basic Waveform Acquisition

### Single Channel Capture

```python
# Capture waveform from channel 1
waveform = scope.get_waveform(channel=1)

# Access waveform data
print(f"Channel: {waveform.channel}")
print(f"Samples: {len(waveform.voltage)}")
print(f"Sample rate: {waveform.sample_rate/1e9} GSa/s")
print(f"Time range: {waveform.time[0]} to {waveform.time[-1]} s")

# Waveform data as numpy arrays
times = waveform.time          # Time values (seconds)
voltages = waveform.voltage    # Voltage values (volts)
```

### Multi-Channel Capture

```python
# Enable multiple channels
scope.channel1.enabled = True
scope.channel2.enabled = True

# Capture all enabled channels
waveforms = scope.get_waveforms()

# Process each waveform
for wf in waveforms:
    print(f"Channel {wf.channel}: {len(wf.voltage)} samples")
```

## Direct SCPI Commands

For advanced control, you can send raw SCPI commands:

```python
# Write a command
scope.write("*RST")  # Reset oscilloscope

# Query a value
response = scope.query("*IDN?")
print(response)

# Query a numeric value
value = scope.query_float("C1:VDIV?")
print(f"Channel 1 scale: {value} V/div")
```

!!! warning "Use High-Level API When Possible"
The library provides high-level methods for most operations. Only use direct SCPI commands when the functionality isn't available through the API.

## Error Handling

### Common Exceptions

```python
from scpi_control import (
    SiglentConnectionError,
    SiglentTimeoutError,
    InvalidParameterError,
    CommandError
)

try:
    scope = Oscilloscope('192.168.1.100')
    scope.connect()

    # Operations...

except SiglentConnectionError as e:
    print(f"Connection failed: {e}")
except SiglentTimeoutError as e:
    print(f"Command timeout: {e}")
except InvalidParameterError as e:
    print(f"Invalid parameter: {e}")
except CommandError as e:
    print(f"Command error: {e}")
finally:
    scope.disconnect()
```

### Recommended Pattern

```python
from scpi_control import Oscilloscope

try:
    with Oscilloscope('192.168.1.100') as scope:
        # Your code here
        waveform = scope.get_waveform(1)

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
```

## Complete Example

Here's a complete example putting it all together:

```python
from scpi_control import Oscilloscope

# Configuration
SCOPE_IP = '192.168.1.100'

with Oscilloscope(SCOPE_IP) as scope:
    # Get device info
    print(f"Connected to: {scope.device_info['model']}")

    # Configure channel 1
    scope.channel1.enabled = True
    scope.channel1.voltage_scale = 1.0
    scope.channel1.voltage_offset = 0.0
    scope.channel1.coupling = "DC"
    scope.channel1.probe_ratio = 10.0

    # Configure trigger
    scope.trigger.mode = "AUTO"
    scope.trigger.source = "C1"
    scope.trigger.level = 0.0
    scope.trigger.slope = "POS"

    # Set timebase
    scope.timebase = 1e-3  # 1 ms/div

    # Start acquisition
    scope.run()

    # Capture waveform
    waveform = scope.get_waveform(1)
    print(f"Captured {len(waveform.voltage)} samples")
    print(f"Time range: {waveform.time[0]*1e3:.3f} to {waveform.time[-1]*1e3:.3f} ms")
    print(f"Voltage range: {waveform.voltage.min():.3f} to {waveform.voltage.max():.3f} V")
```

## Best Practices

!!! tip "Connection Management" - Always use context managers (`with` statement) when possible - Ensure `disconnect()` is called in `finally` blocks if not using context manager - Set appropriate timeouts based on your network and operation type

!!! tip "Channel Configuration" - Set probe ratio to match your actual probe (usually 10X) - Use appropriate coupling: DC for DC-coupled signals, AC to remove DC offset - Enable bandwidth limiting to reduce high-frequency noise when not needed

!!! tip "Performance" - Only enable channels you need to capture - Use appropriate timebase and memory depth for your application - Consider using `get_waveforms()` for multi-channel capture instead of multiple `get_waveform()` calls

!!! tip "Error Handling" - Always wrap oscilloscope operations in try/except blocks - Handle network timeouts appropriately - Log errors for debugging

## Next Steps

- [Waveform Capture](waveform-capture.md) - Advanced capture techniques and data formats
- [Measurements](measurements.md) - Automated measurements and statistics
- [Trigger Control](trigger-control.md) - Advanced trigger modes and conditions
- [Advanced Features](advanced-features.md) - FFT, math channels, and automation
