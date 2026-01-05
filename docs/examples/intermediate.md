# Intermediate Examples

Intermediate examples showing automation patterns, real-time data capture, and batch operations for more advanced use cases.

## Quick Reference

| Example                                                                                           | Description                                     |
| ------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| [Batch capture with different configurations](#batch-capture-with-different-configurations)       | Batch capture with different configurations.    |
| [Continuous time-series data collection](#continuous-time-series-data-collection)                 | Continuous time-series data collection.         |
| [Live plotting example for Siglent oscilloscope](#live-plotting-example-for-siglent-oscilloscope) | Live plotting example for Siglent oscilloscope. |
| [Trigger-based event capture](#trigger-based-event-capture)                                       | Trigger-based event capture.                    |

---

## Batch capture with different configurations

Batch capture with different configurations.

### Requirements

- siglent - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/batch_capture.py
```

### Source Code

```python
"""Batch capture with different configurations.

This example demonstrates how to capture multiple waveforms with different
timebase and voltage scale settings. This is useful for characterizing
signals at different time scales or for automated testing.
"""

from siglent.automation import DataCollector

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def progress_callback(current, total, status):
    """Display progress during batch capture."""
    percent = (current / total) * 100
    print(f"Progress: {current}/{total} ({percent:.1f}%) - {status}")


def main():
    # Create data collector with context manager
    with DataCollector(SCOPE_IP) as collector:
        print(f"Connected to {collector.scope.identify()}\n")

        # Configure batch capture parameters
        timebase_scales = ["1us", "10us", "100us", "1ms"]
        voltage_scales = {1: ["500mV", "1V", "2V"]}  # Different scales for channel 1
        triggers_per_config = 3

        print("Starting batch capture...")
        print(f"  Timebase scales: {timebase_scales}")
        print(f"  Voltage scales: {voltage_scales}")
        print(f"  Triggers per config: {triggers_per_config}")
        print(f"  Total captures: {len(timebase_scales) * len(voltage_scales[1]) * triggers_per_config}\n")

        # Perform batch capture
        results = collector.batch_capture(
            channels=[1],
            timebase_scales=timebase_scales,
            voltage_scales=voltage_scales,
            triggers_per_config=triggers_per_config,
            progress_callback=progress_callback,
        )

        print(f"\nBatch capture complete! Collected {len(results)} waveforms")

        # Display summary of first few captures
        print("\nFirst 5 captures:")
        for i, result in enumerate(results[:5]):
            config = result["config"]
            waveforms = result["waveforms"]
            print(f"  {i+1}. Config: {config}, Channels: {list(waveforms.keys())}")

        # Save batch results
        print("\nSaving batch results to 'batch_output' directory...")
        collector.save_batch(results, "batch_output", format="npz")
        print("Done! Results saved to 'batch_output/' with metadata.txt")


if __name__ == "__main__":
    main()
```

---

## Continuous time-series data collection

Continuous time-series data collection.

### Requirements

- siglent - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/continuous_capture.py
```

### Source Code

```python
"""Continuous time-series data collection.

This example demonstrates how to collect waveforms continuously over a
period of time. This is useful for monitoring signals, collecting statistics,
or capturing time-varying phenomena.
"""

from siglent.automation import DataCollector

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def progress_callback(captures_done, status):
    """Display progress during continuous capture."""
    print(f"[{captures_done}] {status}")


def main():
    with DataCollector(SCOPE_IP) as collector:
        print(f"Connected to {collector.scope.identify()}\n")

        # Example 1: Collect to memory (good for short durations)
        print("Example 1: Collecting to memory for 10 seconds...")
        results = collector.start_continuous_capture(channels=[1, 2], duration=10, interval=0.5, progress_callback=progress_callback)  # 10 seconds  # Capture every 0.5 seconds

        print(f"\nCollected {len(results)} captures to memory")
        print(f"First capture timestamp: {results[0]['timestamp']}")
        print(f"Last capture timestamp: {results[-1]['timestamp']}")

        # Analyze the captured data
        print("\nAnalyzing captured data...")
        ch1_vpps = []
        for result in results:
            if 1 in result["waveforms"]:
                analysis = collector.analyze_waveform(result["waveforms"][1])
                ch1_vpps.append(analysis["vpp"])

        if ch1_vpps:
            import numpy as np

            print(f"Channel 1 Vpp statistics:")
            print(f"  Mean: {np.mean(ch1_vpps):.3f}V")
            print(f"  Std Dev: {np.std(ch1_vpps):.3f}V")
            print(f"  Min: {np.min(ch1_vpps):.3f}V")
            print(f"  Max: {np.max(ch1_vpps):.3f}V")

        # Example 2: Collect to files (good for long durations)
        print("\n" + "=" * 60)
        print("Example 2: Collecting to files for 30 seconds...")
        print("Files will be saved to 'continuous_data/' directory")
        print("Press Ctrl+C to stop early\n")

        collector.start_continuous_capture(
            channels=[1, 2],
            duration=30,
            interval=1.0,
            output_dir="continuous_data",
            file_format="npz",
            progress_callback=progress_callback,
        )  # 30 seconds  # Capture every 1 second

        print("\nContinuous capture complete! Files saved to 'continuous_data/'")


if __name__ == "__main__":
    main()
```

---

## Live plotting example for Siglent oscilloscope

Live plotting example for Siglent oscilloscope.

### Requirements

- matplotlib - For plotting
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/live_plot.py
```

### Source Code

```python
"""Live plotting example for Siglent oscilloscope.

This script demonstrates real-time waveform acquisition and plotting
using matplotlib animation.
"""

import time

import matplotlib.animation as animation
import matplotlib.pyplot as plt

from siglent import Oscilloscope

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"

# Channel colors (matching oscilloscope theme)
CHANNEL_COLORS = {
    1: "#FFD700",  # Yellow
    2: "#00CED1",  # Cyan
    3: "#FF1493",  # Magenta
    4: "#00FF00",  # Green
}


class LivePlotter:
    """Live waveform plotter."""

    def __init__(self, scope, channels=[1]):
        """Initialize live plotter.

        Args:
            scope: Connected Oscilloscope instance
            channels: List of channel numbers to plot (default: [1])
        """
        self.scope = scope
        self.channels = channels

        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.ax.set_xlabel("Time (µs)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.set_title("Live Waveform Display")
        self.ax.grid(True, alpha=0.3)

        # Store line objects
        self.lines = {}
        for ch in channels:
            color = CHANNEL_COLORS.get(ch, "white")
            (line,) = self.ax.plot([], [], color=color, linewidth=1.0, label=f"CH{ch}")
            self.lines[ch] = line

        self.ax.legend(loc="upper right")

    def update(self, frame):
        """Animation update function.

        Args:
            frame: Frame number (not used)

        Returns:
            List of line objects
        """
        for ch in self.channels:
            try:
                # Acquire waveform
                waveform = self.scope.get_waveform(ch)

                # Update line data
                self.lines[ch].set_data(waveform.time * 1e6, waveform.voltage)

            except Exception as e:
                print(f"Error acquiring channel {ch}: {e}")

        # Autoscale
        self.ax.relim()
        self.ax.autoscale_view()

        return list(self.lines.values())

    def start(self, interval=200):
        """Start live plotting.

        Args:
            interval: Update interval in milliseconds (default: 200)
        """
        anim = animation.FuncAnimation(self.fig, self.update, interval=interval, blit=False, cache_frame_data=False)
        plt.show()


def main():
    # Connect to oscilloscope
    print(f"Connecting to oscilloscope at {SCOPE_IP}...")
    scope = Oscilloscope(SCOPE_IP)

    try:
        scope.connect()
        print(f"Connected to: {scope.device_info['model']}")

        # Configure channel 1
        print("\nConfiguring Channel 1...")
        scope.channel1.enable()
        scope.channel1.coupling = "DC"
        scope.channel1.voltage_scale = 1.0

        # Set trigger
        scope.trigger.mode = "AUTO"
        scope.trigger.source = "C1"
        scope.trigger.level = 0.0

        # Start acquisition
        scope.run()
        print("Acquisition running...")

        # Wait a moment for signal to stabilize
        time.sleep(0.5)

        # Start live plotting
        print("\nStarting live plot...")
        print("Close the plot window to stop.")

        plotter = LivePlotter(scope, channels=[1])
        plotter.start(interval=200)  # Update every 200ms

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

## Trigger-based event capture

Trigger-based event capture.

### Requirements

- siglent - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/trigger_based_capture.py
```

### Source Code

```python
"""Trigger-based event capture.

This example demonstrates how to wait for specific trigger conditions
and capture waveforms when they occur. This is useful for capturing
sporadic events or signals that meet specific criteria.
"""

from siglent.automation import DataCollector, TriggerWaitCollector

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def main():
    # Example 1: Wait for a single trigger event
    print("Example 1: Waiting for trigger event...")
    with TriggerWaitCollector(SCOPE_IP) as tc:
        # Configure trigger: Channel 1, Rising edge, 1V threshold
        tc.collector.scope.trigger.set_source(1)
        tc.collector.scope.trigger.set_slope("POS")  # Rising edge
        tc.collector.scope.trigger.set_level(1, 1.0)  # 1V threshold

        print("Trigger configured:")
        print("  Source: Channel 1")
        print("  Edge: Rising")
        print("  Level: 1.0V")
        print("\nWaiting for trigger (max 30 seconds)...")

        # Wait for trigger
        waveforms = tc.wait_for_trigger(channels=[1, 2], max_wait=30.0, save_on_trigger=True, output_dir="trigger_captures")

        if waveforms:
            print("\nTrigger captured successfully!")
            for ch, waveform in waveforms.items():
                print(f"Channel {ch}: {len(waveform.voltage)} samples")
        else:
            print("\nNo trigger detected within timeout period")

    # Example 2: Capture multiple trigger events
    print("\n" + "=" * 60)
    print("Example 2: Capturing 10 trigger events...")

    with DataCollector(SCOPE_IP) as collector:
        # Configure trigger
        collector.scope.trigger.set_source(1)
        collector.scope.trigger.set_slope("POS")
        collector.scope.trigger.set_level(1, 2.0)  # 2V threshold
        collector.scope.trigger.set_mode("NORM")  # Normal trigger mode

        print("Trigger configured:")
        print("  Source: Channel 1")
        print("  Edge: Rising")
        print("  Level: 2.0V")
        print("\nCapturing 10 trigger events...")

        captures = []
        for i in range(10):
            # Trigger single acquisition
            collector.scope.trigger_single()

            # Wait for trigger (simple polling)
            import time

            timeout = 5.0
            start = time.time()
            while (time.time() - start) < timeout:
                status = collector.scope.query(":TRIG:STAT?").strip()
                if status == "Stop":
                    # Capture waveform
                    waveforms = collector.capture_single([1, 2])
                    captures.append(waveforms)
                    print(f"  Captured event {i+1}/10")
                    break
                time.sleep(0.05)
            else:
                print(f"  Event {i+1} timed out")

        if captures:
            print(f"\nCaptured {len(captures)} events")

            # Save all captures
            print("Saving captures to 'multi_trigger_captures/'...")
            for i, waveforms in enumerate(captures):
                collector.save_data(waveforms, f"multi_trigger_captures/event_{i+1:03d}", format="npz")

            print("Done!")


if __name__ == "__main__":
    main()
```

---

## Next Steps

Explore [Advanced Examples](advanced.md) for signal analysis and specialized features, or review [Beginner Examples](beginner.md) for fundamentals.

See also:

- [User Guide](../user-guide/basic-usage.md) - Conceptual documentation
- [API Reference](../api/oscilloscope.md) - Detailed API documentation
- [Getting Started](../getting-started/quickstart.md) - Quick start guide
