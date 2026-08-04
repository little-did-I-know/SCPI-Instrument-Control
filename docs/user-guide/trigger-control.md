# Trigger Control

This guide covers trigger configuration, modes, types, and advanced triggering techniques for stable waveform capture.

## Understanding Triggers

The trigger determines when the oscilloscope captures and displays a waveform. Proper trigger configuration is essential for stable, repeatable measurements.

### Basic Concept

The trigger monitors a signal and starts waveform capture when specific conditions are met:

1. Signal crosses a **threshold level** (voltage)
2. In a specific **direction** (rising/falling edge)
3. On a specific **source** (channel or external input)

## Trigger Modes

### AUTO Mode

Automatically triggers even without a valid trigger event:

```python
from scpi_control import Oscilloscope

with Oscilloscope('192.168.1.100') as scope:
    # Set to AUTO mode
    scope.trigger.mode = "AUTO"
    # Or
    scope.trigger.auto()
```

**Characteristics:**

- Triggers automatically if no valid trigger occurs within timeout (~100ms)
- Display continuously updates
- Best for: Quick signal viewing, unknown signals, initial setup

**Use when:**

- You want to see something on screen immediately
- Signal frequency is low or irregular
- You're just getting started

### NORMAL Mode

Triggers only when conditions are met:

```python
# Set to NORMAL mode
scope.trigger.mode = "NORMAL"
# Or
scope.trigger.normal()
```

**Characteristics:**

- Waits indefinitely for valid trigger
- No display update unless trigger occurs
- Display shows last triggered waveform
- Best for: Stable measurements, capturing specific events

**Use when:**

- You need repeatable, stable measurements
- Capturing sporadic events
- Measuring timing or frequency accurately

### SINGLE Mode

Captures one trigger event then stops:

```python
# Set to SINGLE mode
scope.trigger.mode = "SINGLE"
# Or
scope.trigger.single()

# Arm the trigger
scope.trigger_single()

# Wait for trigger (see example below)
```

**Characteristics:**

- Triggers once then stops
- Perfect for capturing one-time events
- Requires re-arming for next capture
- Best for: Single events, transients, glitches

**Use when:**

- Capturing power-on sequences
- Analyzing single events
- Capturing glitches or transients

### STOP Mode

Stops all triggering:

```python
# Stop triggering
scope.trigger.mode = "STOP"
# Or
scope.trigger.stop()
```

**Use when:**

- You want to freeze the display
- Analyzing a captured waveform

### Mode Comparison

| Mode   | When it Triggers              | Display Update | Best For                             |
| ------ | ----------------------------- | -------------- | ------------------------------------ |
| AUTO   | Automatically or on condition | Continuous     | Initial setup, unknown signals       |
| NORMAL | Only on condition             | When triggered | Stable measurements, specific events |
| SINGLE | Once on condition             | Once           | One-time events, transients          |
| STOP   | Never                         | Frozen         | Analysis of captured data            |

## Trigger Source

### Channel Sources

Trigger on any oscilloscope channel:

```python
# Trigger on channel 1
scope.trigger.source = "C1"
# Or using channel number
scope.trigger.source = 1

# Other channels
scope.trigger.source = "C2"
scope.trigger.source = "C3"
scope.trigger.source = "C4"

# Or use helper method
scope.trigger.set_source(1)
```

!!! warning "A channel must be switched on before it can be the trigger source"

    Selecting a channel that is currently off does **not** raise. On an
    SDS824X HD the scope accepts the write, queues no error, and silently
    triggers on `LINE` instead — so the acquisition is real but synchronized
    to mains rather than to your signal.

    ```python
    scope.channel2.enable()        # do this first
    scope.trigger.source = "C2"
    assert scope.trigger.source == "C2"   # read back when it matters
    ```

### External Trigger

Trigger from external BNC input:

```python
# External trigger input
scope.trigger.source = "EX"    # Main external input
scope.trigger.source = "EX5"   # 5V external input (if available)
```

!!! warning "Not every scope has an external trigger input"

    `scope.capabilities.trigger_sources` reports what the **driver** can send
    for the dialect — it is not a promise about the attached model's front
    panel, which SCPI gives no way to interrogate.

    Measured on an SDS824X HD (modern dialect) on 2026-08-04, with **no error
    queued** in any case: `EX` is silently coerced to `LINE` (that model has no
    external input), and `EX5` never takes at all — it is a no-op when the
    current source is a channel, and lands on the highest enabled channel when
    the current source is `LINE`. Other modern-dialect scopes, such as the
    SDS2000X+, do have a working external input.

    Read the value back if your measurement depends on it:

    ```python
    scope.trigger.source = "EX"
    if scope.trigger.source != "EX":
        raise RuntimeError("this scope has no usable external trigger input")
    ```

### Line Trigger

Trigger on AC line frequency (50/60 Hz):

```python
# Line trigger (useful for AC-powered signals)
scope.trigger.source = "LINE"
```

**Use when:**

- Debugging AC-powered equipment
- Viewing signals synchronized with mains frequency
- Eliminating jitter from line-powered sources

## Trigger Level and Slope

### Setting Trigger Level

The trigger level is the voltage threshold that must be crossed:

```python
# Set trigger level to 0V (zero crossing)
scope.trigger.level = 0.0

# Trigger at 1.5V
scope.trigger.level = 1.5

# Trigger at -0.5V
scope.trigger.level = -0.5

# Get current trigger level
level = scope.trigger.level
print(f"Current trigger level: {level}V")

# Set level for specific channel
scope.trigger.set_level(1, 1.0)  # Channel 1, 1V threshold
```

### Setting Trigger Slope

The slope determines which edge triggers:

```python
# Trigger on rising edge (positive slope)
scope.trigger.slope = "POS"

# Trigger on falling edge (negative slope)
scope.trigger.slope = "NEG"

# Trigger on either edge
scope.trigger.slope = "WINDOW"

# Or use helper method
scope.trigger.set_slope("POS")
```

**Slope Options:**

- **POS** (Positive): Rising edge, low-to-high transition
- **NEG** (Negative): Falling edge, high-to-low transition
- **WINDOW**: Either edge (model dependent)

### Complete Edge Trigger Setup

```python
# Configure edge trigger
scope.trigger.set_edge_trigger(source="C1", slope="POS")

# Or configure individually
scope.trigger.source = "C1"
scope.trigger.slope = "POS"
scope.trigger.level = 0.0
scope.trigger.mode = "NORMAL"
```

## Advanced Trigger Types

Beyond simple edge triggering, Siglent oscilloscopes support advanced trigger types:

### Edge Trigger (Default)

Standard rising/falling edge trigger:

```python
# Set trigger type to edge
scope.trigger.trigger_type = "EDGE"

# Configure edge trigger
scope.trigger.source = "C1"
scope.trigger.slope = "POS"
scope.trigger.level = 1.0
```

### Slew Rate Trigger

Triggers on edges that are too fast or too slow:

```python
# Set to slew rate trigger
scope.trigger.trigger_type = "SLEW"

# Additional configuration via SCPI
# (specific parameters depend on model)
```

### Glitch Trigger

Captures narrow pulses (glitches):

```python
# Set to glitch trigger
scope.trigger.trigger_type = "GLIT"
```

**Use for:**

- Finding short pulses
- Detecting noise spikes
- Capturing intermittent problems

### Interval Trigger

Triggers based on pulse width or time intervals:

```python
# Set to interval trigger
scope.trigger.trigger_type = "INTV"
```

### Runt Trigger

Detects pulses that don't cross both thresholds:

```python
# Set to runt trigger
scope.trigger.trigger_type = "RUNT"
```

**Use for:**

- Finding malformed pulses
- Detecting signal integrity issues
- Protocol violations

### Pattern Trigger

Triggers on logic patterns across multiple channels:

```python
# Set to pattern trigger
scope.trigger.trigger_type = "PATTERN"
```

**Use for:**

- Multi-channel logic analysis
- Bus state detection
- Complex trigger conditions

### Available Trigger Types

```python
# Valid trigger types:
# "EDGE"    - Edge trigger (rising/falling)
# "SLEW"    - Slew rate trigger
# "GLIT"    - Glitch trigger
# "INTV"    - Interval/width trigger
# "RUNT"    - Runt pulse trigger
# "PATTERN" - Pattern trigger
```

## Force Trigger

Manually force a trigger event immediately:

```python
# Force trigger now (ignores conditions)
scope.trigger.force()
```

**Use for:**

- Testing without signal
- Capturing current screen
- Manual control

## Trigger Status and Waiting

### Check Trigger Status

```python
# Query trigger status
status = scope.query(":TRIG:STAT?").strip()

if status == "Auto":
    print("Auto triggering")
elif status == "Trig'd":
    print("Triggered")
elif status == "Ready":
    print("Armed and waiting")
elif status == "Stop":
    print("Stopped")
```

### Wait for Trigger (SINGLE Mode)

```python
import time

# Configure single trigger
scope.trigger.mode = "SINGLE"
scope.trigger.source = "C1"
scope.trigger.level = 1.0
scope.trigger.slope = "POS"

# Arm the trigger
scope.trigger_single()

# Wait for trigger with timeout
timeout = 10.0
start = time.time()
triggered = False

while (time.time() - start) < timeout:
    status = scope.query(":TRIG:STAT?").strip()
    if status == "Stop":  # Triggered and captured
        triggered = True
        print("Trigger captured!")
        break
    time.sleep(0.05)  # Poll every 50ms

if not triggered:
    print("Trigger timeout - no event detected")
else:
    # Capture the triggered waveform
    waveform = scope.get_waveform(1)
    print(f"Captured {len(waveform)} samples")
```

## Practical Triggering Examples

### Example 1: Stable Frequency Measurement

```python
from scpi_control import Oscilloscope

with Oscilloscope('192.168.1.100') as scope:
    # Configure for stable triggering
    scope.channel1.enabled = True
    scope.channel1.voltage_scale = 1.0

    # NORMAL mode for stable display
    scope.trigger.mode = "NORMAL"
    scope.trigger.source = "C1"
    scope.trigger.slope = "POS"
    scope.trigger.level = 0.0

    # Set timebase to show 2-3 periods
    scope.timebase = 1e-3  # 1ms/div

    # Measure frequency
    freq = scope.measurement.measure_frequency(1)
    print(f"Frequency: {freq/1e3:.2f} kHz")
```

### Example 2: Capture Power-On Event

```python
# Capture what happens when device powers on
scope.trigger.mode = "SINGLE"
scope.trigger.source = "C1"
scope.trigger.level = 2.5  # 2.5V threshold
scope.trigger.slope = "POS"

# Set timebase to capture full sequence
scope.timebase = 10e-3  # 10ms/div = 140ms total

# Arm trigger
scope.trigger_single()

print("Trigger armed. Power on your device now...")

# Wait for trigger
import time
timeout = 60.0  # Wait up to 60 seconds
start = time.time()

while (time.time() - start) < timeout:
    status = scope.query(":TRIG:STAT?").strip()
    if status == "Stop":
        print("Event captured!")
        waveform = scope.get_waveform(1)
        waveform.save_csv("power_on_sequence.csv")
        print("Saved to power_on_sequence.csv")
        break
    time.sleep(0.1)
else:
    print("Timeout - no event detected")
```

### Example 3: Compare Rising and Falling Edges

```python
# Capture rising edge
scope.trigger.slope = "POS"
scope.trigger.level = 0.0
rising_waveform = scope.get_waveform(1)

# Capture falling edge
scope.trigger.slope = "NEG"
scope.trigger.level = 0.0
falling_waveform = scope.get_waveform(1)

# Measure rise and fall times
rise_time = scope.measurement.measure_rise_time(1)
scope.trigger.slope = "NEG"
fall_time = scope.measurement.measure_fall_time(1)

print(f"Rise time: {rise_time*1e9:.2f} ns")
print(f"Fall time: {fall_time*1e9:.2f} ns")
```

### Example 4: Trigger on Low Voltage Signal

```python
# For small signals, adjust scale and trigger level
scope.channel1.voltage_scale = 0.1  # 100mV/div
scope.channel1.coupling = "AC"      # Remove DC offset

# Center trigger around 0V
scope.trigger.level = 0.0
scope.trigger.slope = "POS"
scope.trigger.mode = "NORMAL"

# Verify trigger is working
time.sleep(1)
status = scope.query(":TRIG:STAT?").strip()
if status == "Ready":
    print("Warning: No trigger detected - check signal and level")
elif status == "Trig'd":
    print("Triggering successfully")
```

### Example 5: Multi-Event Capture

```python
from scpi_control.automation import TriggerWaitCollector

# Capture 10 trigger events
with TriggerWaitCollector('192.168.1.100') as tc:
    # Configure trigger
    tc.collector.scope.trigger.source = "C1"
    tc.collector.scope.trigger.slope = "POS"
    tc.collector.scope.trigger.level = 2.0

    print("Capturing 10 events...")

    for i in range(10):
        # Wait for trigger
        waveforms = tc.wait_for_trigger(
            channels=[1],
            max_wait=10.0,
            save_on_trigger=True,
            output_dir=f"event_captures"
        )

        if waveforms:
            print(f"Event {i+1}/10 captured")
        else:
            print(f"Event {i+1}/10 timeout")

    print("Capture complete!")
```

## Trigger Coupling

Trigger coupling filters the trigger signal (not available on all models),
via the `scope.trigger.coupling` property:

```python
# DC coupling - pass all frequencies
scope.trigger.coupling = "DC"

# AC coupling - block DC component
scope.trigger.coupling = "AC"

# High frequency reject
scope.trigger.coupling = "HFREJ"

# Low frequency reject
scope.trigger.coupling = "LFREJ"
```

Allowed values are `DC`, `AC`, `HFREJ`, and `LFREJ` — also available as the
`TriggerCoupling` enum (`from scpi_control import TriggerCoupling`); plain
strings work too. The property is dialect-aware — it works identically
whether the connected scope speaks the legacy, modern, or LeCroy command set.
**Tektronix does not support `AC` trigger coupling** (neither the TBS1000C
nor the 2/4/5/6 Series MSO command set has an AC trigger-coupling token);
setting it on a Tektronix-dialect scope raises `FeatureNotSupportedError`.
Check `scope.capabilities.trigger_couplings` before setting it if you need to
support multiple dialects. See [SCPI Dialects](scpi-dialects.md) for how
that translation works.

## Trigger Holdoff

Programmatic trigger holdoff is **not currently supported**. Older releases
of this library exposed a `scope.trigger.holdoff` property, but it was
built on the legacy `TRIG_DELAY` command, which actually controls trigger
*delay* (the time from trigger event to the sample point), not holdoff (the
dead time after a trigger before the scope will trigger again) — the
underlying instrument exposes true holdoff through different commands. A
corrected implementation is on the roadmap; until then, do not rely on that
property, and don't expect a `scope.trigger.holdoff` example on this page.

For now, set trigger holdoff from the instrument's front panel, or through
its vendor-supplied UI. If you need to script it in the meantime, the
gateway's SCPI terminal (or `scope.write()`/`scope.query()`) lets you send
whatever raw command your instrument actually uses — see
[SCPI Dialects](scpi-dialects.md) for the difference between the legacy and
modern command sets.

## Tips for Stable Triggering

!!! tip "Choosing Trigger Level" - Set trigger level near middle of signal amplitude - For digital signals, use 50% of logic level (e.g., 2.5V for 5V logic) - For AC signals, trigger at zero crossing (level = 0) - Avoid triggering in noisy regions

!!! tip "Trigger Mode Selection" - **AUTO**: Good for continuous monitoring and unknown signals - **NORMAL**: Best for stable, repeatable measurements - **SINGLE**: Perfect for one-time events or slow phenomena - Use NORMAL mode for accurate frequency measurements

!!! tip "Signal Conditioning" - Use AC coupling to remove DC offset - Enable bandwidth limiting to reduce high-frequency noise - Adjust voltage scale so signal fills 50-80% of screen - Ensure trigger source channel is enabled

!!! tip "Troubleshooting" - If no trigger: Check trigger level is within signal range - If unstable: Increase trigger level or adjust timebase - If too many triggers: Use trigger holdoff - If missing events: Use AUTO mode temporarily to see signal

## Common Triggering Issues

### No Trigger Detected

```python
# Check if channel is enabled
if not scope.channel1.enabled:
    scope.channel1.enabled = True

# Verify signal is present
scope.trigger.mode = "AUTO"  # Force display
waveform = scope.get_waveform(1)
vpp = np.ptp(waveform.voltage)

if vpp < 0.01:
    print("Warning: Signal too small (< 10mV)")

# Adjust trigger level to middle of signal
vmid = (np.max(waveform.voltage) + np.min(waveform.voltage)) / 2
scope.trigger.level = vmid
scope.trigger.mode = "NORMAL"
```

### Unstable Trigger

```python
# Use NORMAL mode instead of AUTO
scope.trigger.mode = "NORMAL"

# Increase trigger level away from noise
# Add some hysteresis by moving level higher
current_level = scope.trigger.level
scope.trigger.level = current_level * 1.2

# Or use trigger coupling to filter noise
scope.trigger.coupling = "AC"      # Remove DC
# or
scope.trigger.coupling = "HFREJ"   # Remove HF noise
```

### Missing Intermittent Events

```python
# Use glitch trigger for narrow pulses
scope.trigger.trigger_type = "GLIT"

# Or use SINGLE mode with re-arming
scope.trigger.mode = "SINGLE"

while True:
    scope.trigger_single()

    # Wait for event
    timeout = 60
    start = time.time()
    while (time.time() - start) < timeout:
        status = scope.query(":TRIG:STAT?").strip()
        if status == "Stop":
            print(f"Event at {time.time()}")
            waveform = scope.get_waveform(1)
            # Process event
            break
        time.sleep(0.01)
```

## Complete Triggering Example

```python
from scpi_control import Oscilloscope
import time
import numpy as np

SCOPE_IP = '192.168.1.100'

with Oscilloscope(SCOPE_IP) as scope:
    print("Configuring oscilloscope...")

    # Configure channel
    scope.channel1.enabled = True
    scope.channel1.voltage_scale = 1.0
    scope.channel1.coupling = "DC"

    # Start with AUTO to see signal
    scope.trigger.mode = "AUTO"
    time.sleep(0.5)

    # Capture to analyze signal
    waveform = scope.get_waveform(1)
    vpp = np.ptp(waveform.voltage)
    vmid = (np.max(waveform.voltage) + np.min(waveform.voltage)) / 2

    print(f"Signal amplitude: {vpp:.3f} Vpp")
    print(f"Signal center: {vmid:.3f} V")

    # Configure optimal trigger
    scope.trigger.mode = "NORMAL"
    scope.trigger.source = "C1"
    scope.trigger.slope = "POS"
    scope.trigger.level = vmid  # Trigger at middle of signal

    print(f"Trigger level set to {vmid:.3f} V")

    # Verify trigger is working
    time.sleep(1)
    status = scope.query(":TRIG:STAT?").strip()
    print(f"Trigger status: {status}")

    if status == "Ready":
        print("WARNING: Not triggering - signal may be outside range")
    else:
        # Measure with stable trigger
        freq = scope.measurement.measure_frequency(1)
        vpp_meas = scope.measurement.measure_vpp(1)

        print(f"\nMeasurements:")
        print(f"  Frequency: {freq/1e3:.2f} kHz")
        print(f"  Vpp: {vpp_meas:.3f} V")
```

## Next Steps

- [SCPI Dialects](scpi-dialects.md) - How legacy and modern command sets differ, and how to send raw commands
- [Advanced Features](advanced-features.md) - FFT analysis, math channels, and automation
- [Measurements](measurements.md) - Use stable triggers for accurate measurements
- [Waveform Capture](waveform-capture.md) - Capture triggered waveforms
