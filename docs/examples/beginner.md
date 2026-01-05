# Beginner Examples

Complete examples for getting started with the Siglent Oscilloscope library. These examples demonstrate core functionality and common use cases.

## Quick Reference

| Example                                                                                                       | Description                                           |
| ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| [Basic usage example for Siglent oscilloscope control](#basic-usage-example-for-siglent-oscilloscope-control) | Basic usage example for Siglent oscilloscope control. |
| [Measurement example for Siglent oscilloscope](#measurement-example-for-siglent-oscilloscope)                 | Measurement example for Siglent oscilloscope.         |
| [Simple single capture example](#simple-single-capture-example)                                               | Simple single capture example.                        |
| [Waveform capture example for Siglent oscilloscope](#waveform-capture-example-for-siglent-oscilloscope)       | Waveform capture example for Siglent oscilloscope.    |

---

## Basic usage example for Siglent oscilloscope control

Basic usage example for Siglent oscilloscope control.

### Requirements

- siglent - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/basic_usage.py
```

### Source Code

```python
"""Basic usage example for Siglent oscilloscope control.

This script demonstrates how to connect to an oscilloscope,
configure channels and trigger, and perform basic operations.
"""

from siglent import Oscilloscope

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def main():
    # Create oscilloscope instance
    scope = Oscilloscope(SCOPE_IP)

    try:
        # Connect to oscilloscope
        print(f"Connecting to oscilloscope at {SCOPE_IP}...")
        scope.connect()

        # Get device information
        print(f"\nConnected to: {scope.identify()}")
        if scope.device_info:
            print(f"Model: {scope.device_info['model']}")
            print(f"Serial: {scope.device_info['serial']}")
            print(f"Firmware: {scope.device_info['firmware']}")

        # Configure channel 1
        print("\nConfiguring Channel 1...")
        scope.channel1.enable()
        scope.channel1.coupling = "DC"
        scope.channel1.voltage_scale = 1.0  # 1V/div
        scope.channel1.voltage_offset = 0.0
        scope.channel1.probe_ratio = 10.0  # 10X probe
        print(f"Channel 1 configured: {scope.channel1}")

        # Configure trigger
        print("\nConfiguring Trigger...")
        scope.trigger.mode = "AUTO"
        scope.trigger.source = "C1"
        scope.trigger.level = 0.0  # Trigger at 0V
        scope.trigger.slope = "POS"  # Rising edge
        print(f"Trigger configured: {scope.trigger}")

        # Start acquisition
        print("\nStarting acquisition...")
        scope.run()

        # Perform some measurements
        print("\nPerforming measurements on Channel 1...")
        try:
            freq = scope.measurement.measure_frequency(1)
            print(f"Frequency: {freq/1e6:.3f} MHz")
        except Exception as e:
            print(f"Could not measure frequency: {e}")

        try:
            vpp = scope.measurement.measure_vpp(1)
            print(f"Vpp: {vpp:.3f} V")
        except Exception as e:
            print(f"Could not measure Vpp: {e}")

        # Get all channel configurations
        print("\nChannel Configurations:")
        for i in range(1, 5):
            ch = getattr(scope, f"channel{i}")
            try:
                config = ch.get_configuration()
                if config["enabled"]:
                    print(f"  Channel {i}: {config['voltage_scale']}V/div, " f"{config['coupling']}, offset={config['voltage_offset']}V")
            except Exception:
                pass

    except Exception as e:
        print(f"\nError: {e}")

    finally:
        # Disconnect
        print("\nDisconnecting...")
        scope.disconnect()
        print("Done!")


if __name__ == "__main__":
    main()
```

---

## Measurement example for Siglent oscilloscope

Measurement example for Siglent oscilloscope.

### Requirements

- siglent - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/measurements.py
```

### Source Code

```python
"""Measurement example for Siglent oscilloscope.

This script demonstrates how to perform automated measurements
on oscilloscope channels.
"""

import time

from siglent import Oscilloscope

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def main():
    # Create oscilloscope instance and connect
    with Oscilloscope(SCOPE_IP) as scope:
        print(f"Connected to: {scope.device_info['model']}")

        # Configure channel 1
        print("\nConfiguring Channel 1...")
        scope.channel1.enable()
        scope.channel1.coupling = "DC"
        scope.channel1.voltage_scale = 1.0

        # Start acquisition
        scope.run()
        print("Acquisition running...")

        # Wait a moment for stable signal
        time.sleep(0.5)

        # Perform individual measurements
        print("\n--- Individual Measurements on Channel 1 ---")

        try:
            freq = scope.measurement.measure_frequency(1)
            print(f"Frequency:    {freq/1e6:.6f} MHz ({freq:.2f} Hz)")
        except Exception as e:
            print(f"Frequency:    Error - {e}")

        try:
            period = scope.measurement.measure_period(1)
            print(f"Period:       {period*1e6:.6f} µs")
        except Exception as e:
            print(f"Period:       Error - {e}")

        try:
            vpp = scope.measurement.measure_vpp(1)
            print(f"Vpp:          {vpp:.6f} V")
        except Exception as e:
            print(f"Vpp:          Error - {e}")

        try:
            amplitude = scope.measurement.measure_amplitude(1)
            print(f"Amplitude:    {amplitude:.6f} V")
        except Exception as e:
            print(f"Amplitude:    Error - {e}")

        try:
            vmax = scope.measurement.measure_max(1)
            print(f"Max:          {vmax:.6f} V")
        except Exception as e:
            print(f"Max:          Error - {e}")

        try:
            vmin = scope.measurement.measure_min(1)
            print(f"Min:          {vmin:.6f} V")
        except Exception as e:
            print(f"Min:          Error - {e}")

        try:
            vrms = scope.measurement.measure_rms(1)
            print(f"RMS:          {vrms:.6f} V")
        except Exception as e:
            print(f"RMS:          Error - {e}")

        try:
            vmean = scope.measurement.measure_mean(1)
            print(f"Mean:         {vmean:.6f} V")
        except Exception as e:
            print(f"Mean:         Error - {e}")

        # Perform all measurements at once
        print("\n--- All Measurements ---")
        all_measurements = scope.measurement.measure_all(1)

        for name, value in all_measurements.items():
            if value is not None:
                if "freq" in name.lower():
                    print(f"{name:12s}: {value/1e6:.6f} MHz")
                elif "period" in name.lower():
                    print(f"{name:12s}: {value*1e6:.6f} µs")
                else:
                    print(f"{name:12s}: {value:.6f} V")
            else:
                print(f"{name:12s}: N/A")

        print("\nDone!")


if __name__ == "__main__":
    main()
```

---

## Simple single capture example

Simple single capture example.

### Requirements

- siglent - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/simple_capture.py
```

### Source Code

```python
"""Simple single capture example.

This example shows how to capture a single waveform from one or more channels
and save it to a file.
"""

from siglent.automation import DataCollector

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def main():
    # Create data collector and connect
    collector = DataCollector(SCOPE_IP)
    collector.connect()

    try:
        # Capture waveforms from channels 1 and 2
        print("Capturing waveforms from channels 1 and 2...")
        waveforms = collector.capture_single([1, 2])

        # Display basic information
        for ch, waveform in waveforms.items():
            print(f"\nChannel {ch}:")
            print(f"  Samples: {len(waveform.voltage)}")
            print(f"  Sample rate: {waveform.sample_rate / 1e6:.2f} MSa/s")
            print(f"  Time interval: {waveform.time_interval * 1e9:.2f} ns")
            print(f"  Voltage range: {waveform.voltage.min():.3f}V to {waveform.voltage.max():.3f}V")

        # Analyze waveforms
        for ch, waveform in waveforms.items():
            analysis = collector.analyze_waveform(waveform)
            print(f"\nChannel {ch} Analysis:")
            print(f"  Vpp: {analysis['vpp']:.3f}V")
            print(f"  Mean: {analysis['mean']:.3f}V")
            print(f"  RMS: {analysis['rms']:.3f}V")
            if analysis["frequency"] > 0:
                print(f"  Frequency: {analysis['frequency'] / 1e3:.2f} kHz")

        # Save waveforms to file
        print("\nSaving waveforms to 'simple_capture.npz'...")
        collector.save_data(waveforms, "simple_capture.npz", format="npz")
        print("Done!")

    finally:
        collector.disconnect()


if __name__ == "__main__":
    main()
```

---

## Waveform capture example for Siglent oscilloscope

Waveform capture example for Siglent oscilloscope.

### Requirements

- matplotlib - For plotting
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/waveform_capture.py
```

### Source Code

```python
"""Waveform capture example for Siglent oscilloscope.

This script demonstrates how to capture waveform data from
the oscilloscope and save it to a file.
"""

import matplotlib.pyplot as plt

from siglent import Oscilloscope

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def main():
    # Create oscilloscope instance and connect
    scope = Oscilloscope(SCOPE_IP)

    try:
        print(f"Connecting to oscilloscope at {SCOPE_IP}...")
        scope.connect()
        print(f"Connected to: {scope.device_info['model']}")

        # Configure channel 1
        print("\nConfiguring Channel 1...")
        scope.channel1.enable()
        scope.channel1.coupling = "DC"
        scope.channel1.voltage_scale = 1.0

        # Set trigger
        scope.trigger.mode = "NORMAL"
        scope.trigger.source = "C1"
        scope.trigger.level = 0.0

        # Capture waveform
        print("\nCapturing waveform from Channel 1...")
        waveform = scope.get_waveform(channel=1)

        print(f"Captured {len(waveform)} samples")
        print(f"Sample rate: {waveform.sample_rate/1e9:.3f} GSa/s")
        print(f"Timebase: {waveform.timebase*1e6:.3f} µs/div")

        # Save waveform to CSV
        print("\nSaving waveform data to 'waveform.csv'...")
        scope.waveform.save_waveform(waveform, "waveform.csv", format="CSV")

        # Plot waveform
        print("\nPlotting waveform...")
        plt.figure(figsize=(12, 6))
        plt.plot(waveform.time * 1e6, waveform.voltage, linewidth=0.5)
        plt.xlabel("Time (µs)")
        plt.ylabel("Voltage (V)")
        plt.title(f"Waveform from Channel {waveform.channel}")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        # Save plot
        plt.savefig("waveform.png", dpi=150)
        print("Waveform plot saved to 'waveform.png'")

        # Show plot
        plt.show()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()

    finally:
        print("\nDisconnecting...")
        scope.disconnect()
        print("Done!")


if __name__ == "__main__":
    main()
```

---

## Next Steps

Ready to learn more? Check out the [Intermediate Examples](intermediate.md) for automation and real-time capture patterns.

See also:

- [User Guide](../user-guide/basic-usage.md) - Conceptual documentation
- [API Reference](../api/oscilloscope.md) - Detailed API documentation
- [Getting Started](../getting-started/quickstart.md) - Quick start guide
