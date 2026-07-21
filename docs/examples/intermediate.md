# Intermediate Examples

Intermediate examples showing automation patterns, real-time data capture, and batch operations for more advanced use cases.

## Quick Reference

| Example | Description |
|---------|-------------|
| [Batch capture with different configurations](#batch-capture-with-different-configurations) | Batch capture with different configurations. |
| [Continuous time-series data collection](#continuous-time-series-data-collection) | Continuous time-series data collection. |
| [Drive the web gateway's REST API from Python — no browser needed](#drive-the-web-gateways-rest-api-from-python-no-browser-needed) | Drive the web gateway's REST API from Python — no browser needed. |
| [Live plotting example for Siglent oscilloscope](#live-plotting-example-for-siglent-oscilloscope) | Live plotting example for Siglent oscilloscope. |
| [Advanced PSU features demonstration](#advanced-psu-features-demonstration) | Advanced PSU features demonstration. |
| [Power supply control via USB connection](#power-supply-control-via-usb-connection) | Power supply control via USB connection. |
| [Synthetic signal generation: parameterized test waveforms, and the mock](#synthetic-signal-generation-parameterized-test-waveforms-and-the-mock) | Synthetic signal generation: parameterized test waveforms, and the mock
oscilloscope's state-coupled synthesis. |
| [Record measurement trends in-process and export them as CSV](#record-measurement-trends-in-process-and-export-them-as-csv) | Record measurement trends in-process and export them as CSV. |
| [Trigger-based event capture](#trigger-based-event-capture) | Trigger-based event capture. |
| [Acquisition provenance and the load_waveform() / scpi-extract workflow](#acquisition-provenance-and-the-load_waveform-scpi-extract-workflow) | Acquisition provenance and the load_waveform() / scpi-extract workflow. |

---

## Batch capture with different configurations

Batch capture with different configurations.

### Requirements

- scpi_control - Core library
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

Requirements: an oscilloscope reachable on the network -- edit SCOPE_IP below
to match its LAN address.

Expected output: progress lines for each capture, a summary of the first
five results, and the batch saved to a 'batch_output/' directory (waveform
files plus metadata.txt) in the current directory.
"""

from scpi_control.automation import DataCollector

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

- scpi_control - Core library
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

Requirements: an oscilloscope reachable on the network -- edit SCOPE_IP below
to match its LAN address.

Expected output: a 10-second in-memory capture run with Vpp statistics
printed to the console, followed by a 30-second run that saves waveform
files to a 'continuous_data/' directory in the current directory.
"""

from scpi_control.automation import DataCollector

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

## Drive the web gateway's REST API from Python — no browser needed

Drive the web gateway's REST API from Python — no browser needed.

### Requirements

- scpi_control - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/gateway_rest_client.py
```

### Source Code

```python
"""Drive the web gateway's REST API from Python — no browser needed.

Start the gateway first (in another terminal):

    pip install "SCPI-Instrument-Control[web]"
    scpi-web

Then run this script. It creates a hardware-free mock session, configures a
channel, fetches full-resolution waveform data as JSON, and downloads a
screenshot PNG — the same API the browser UI uses.

Requirements:
    - SCPI-Instrument-Control[web] (for the gateway itself)
    - Python standard library only for this client (urllib)
"""

import json
import urllib.request
from typing import Optional, Union

BASE = "http://127.0.0.1:8765/api"

Body = Optional[Union[dict, list]]  # examples run on the package floor, Python 3.9


def call(method: str, path: str, body: Body = None) -> bytes:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request) as response:
        return response.read()


def call_json(method: str, path: str, body: Body = None):
    return json.loads(call(method, path, body))


def main() -> None:
    # 1. Create a mock oscilloscope session (no hardware required)
    session = call_json("POST", "/sessions", {"mock": True, "label": "REST demo"})
    session_id = session["id"]
    print(f"Session {session_id}: {session['model']} ({session['dialect']} dialect)")

    scope = f"/sessions/{session_id}/scope"
    try:
        # 2. Configure channel 1 and read the full state snapshot back
        state = call_json("PATCH", f"{scope}/channels/1", {"enabled": True, "voltage_scale": 0.5})
        print(f"Timebase: {state['timebase']} s/div, C1 scale: {state['channels']['1']['voltage_scale']} V/div")

        # 3. Fetch full-resolution waveform data as JSON
        waveform = call_json("GET", f"{scope}/waveform?channels=1&max_points=16")
        channel = waveform["channels"][0]
        print(f"Waveform C{channel['channel']}: {len(channel['points'])} points, dt={channel['dt']:.2e} s")

        # 4. Download the instrument screenshot
        png = call("GET", f"{scope}/screenshot.png")
        with open("gateway_screenshot.png", "wb") as f:
            f.write(png)
        print(f"Saved gateway_screenshot.png ({len(png)} bytes)")

        # 5. Send a raw SCPI query through the terminal endpoint
        reply = call_json("POST", f"{scope}/command", {"command": "*IDN?"})
        print(f"*IDN? -> {reply['response']}")
    finally:
        call("DELETE", f"/sessions/{session_id}")
        print("Session closed.")


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

Requirements: an oscilloscope reachable on the network -- edit SCOPE_IP below
to match its LAN address. matplotlib is a core dependency, no extra install
needed.

Expected output: an interactive plot window that updates every 200ms with
the live Channel 1 waveform, until the window is closed. No files are
written.
"""

import time

import matplotlib.animation as animation
import matplotlib.pyplot as plt

from scpi_control import Oscilloscope

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

## Advanced PSU features demonstration

Advanced PSU features demonstration.

### Requirements

- scpi_control - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/psu_advanced_features.py
```

### Source Code

```python
"""Advanced PSU features demonstration.

Demonstrates:
- Data logging (CSV)
- Tracking modes (series/parallel)
- Timer functionality
- Waveform generation
- OVP/OCP protection

Requirements: SCPI-Instrument-Control (core install) -- runs entirely against
a mock connection, no hardware needed.

Expected output: console narration of each demo, plus CSV logs
('psu_manual_log.csv', 'psu_timed_log.csv', 'psu_output1_log.csv',
'characterization_log.csv') saved to the current directory.
"""

import time

from scpi_control import PowerSupply, PSUDataLogger, TimedPSULogger
from scpi_control.connection.mock import MockConnection


def demo_data_logging():
    """Demonstrate CSV data logging."""
    print("\n" + "=" * 60)
    print("Data Logging Demo")
    print("=" * 60)

    # Create mock PSU
    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")
    psu = PowerSupply("mock", connection=mock_conn)
    psu.connect()

    print(f"Connected to: {psu.model_capability.model_name}")

    # Configure outputs
    psu.output1.voltage = 5.0
    psu.output1.current = 1.0
    psu.output1.enabled = True

    psu.output2.voltage = 12.0
    psu.output2.current = 0.5
    psu.output2.enabled = True

    # Manual logging
    print("\n1. Manual logging:")
    logger = PSUDataLogger(psu, "psu_manual_log.csv")
    logger.start()

    for i in range(5):
        print(f"   Logging measurement {i+1}/5...")
        logger.log_measurement()
        time.sleep(0.5)

    logger.stop()
    print(f"   Log saved to: {logger.filepath}")

    # Timed logging with context manager
    print("\n2. Timed logging (1 second interval):")
    with TimedPSULogger(psu, "psu_timed_log.csv", interval=1.0) as timed_logger:
        print("   Logging started (will run for 5 seconds)...")
        time.sleep(5)
    print(f"   Log saved to: {timed_logger.logger.filepath}")

    # Selective output logging
    print("\n3. Selective output logging (output 1 only):")
    with PSUDataLogger(psu, "psu_output1_log.csv", outputs=[1]) as selective_logger:
        for i in range(3):
            print(f"   Logging output 1 measurement {i+1}/3...")
            selective_logger.log_measurement()
            time.sleep(0.5)
    print(f"   Log saved to: {selective_logger.filepath}")

    psu.all_outputs_off()
    psu.disconnect()
    print("\nData logging demo complete!")


def demo_tracking_modes():
    """Demonstrate tracking modes (series/parallel)."""
    print("\n" + "=" * 60)
    print("Tracking Modes Demo")
    print("=" * 60)

    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")
    psu = PowerSupply("mock", connection=mock_conn)
    psu.connect()

    if not psu.model_capability.has_tracking:
        print("Tracking not supported on this model")
        return

    print(f"Connected to: {psu.model_capability.model_name}")

    # Independent mode (default)
    print("\n1. Independent Mode:")
    psu.set_independent_mode()
    psu.output1.voltage = 5.0
    psu.output2.voltage = 12.0
    print(f"   Tracking mode: {psu.tracking_mode}")
    print(f"   Output 1: {psu.output1.voltage}V")
    print(f"   Output 2: {psu.output2.voltage}V")

    # Series mode
    print("\n2. Series Mode:")
    print("   In series mode, voltages add (V_total = V1 + V2)")
    psu.set_series_mode()
    psu.output1.voltage = 10.0
    psu.output2.voltage = 15.0
    print(f"   Tracking mode: {psu.tracking_mode}")
    print(f"   Output 1: {psu.output1.voltage}V")
    print(f"   Output 2: {psu.output2.voltage}V")
    print(f"   Total voltage: {psu.output1.voltage + psu.output2.voltage}V")

    # Parallel mode
    print("\n3. Parallel Mode:")
    print("   In parallel mode, currents add (I_total = I1 + I2)")
    psu.set_parallel_mode()
    psu.output1.current = 1.0
    psu.output2.current = 1.5
    print(f"   Tracking mode: {psu.tracking_mode}")
    print(f"   Output 1: {psu.output1.current}A")
    print(f"   Output 2: {psu.output2.current}A")
    print(f"   Total current: {psu.output1.current + psu.output2.current}A")

    # Back to independent
    psu.set_independent_mode()
    psu.all_outputs_off()
    psu.disconnect()
    print("\nTracking modes demo complete!")


def demo_timer_functionality():
    """Demonstrate timer functionality (Siglent-specific)."""
    print("\n" + "=" * 60)
    print("Timer Functionality Demo")
    print("=" * 60)

    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")
    psu = PowerSupply("mock", connection=mock_conn)
    psu.connect()

    if not psu.model_capability.has_timer:
        print("Timer not supported on this model")
        return

    print(f"Connected to: {psu.model_capability.model_name}")

    # Enable timer on output 1
    print("\n1. Enabling timer on output 1:")
    output = psu.output1
    output.voltage = 5.0
    output.current = 1.0

    print(f"   Timer enabled: {output.timer_enabled}")
    output.timer_enabled = True
    print(f"   Timer enabled: {output.timer_enabled}")
    print("   Timer can be configured for scheduled voltage/current changes")

    # Disable timer
    output.timer_enabled = False
    print(f"   Timer disabled: {not output.timer_enabled}")

    psu.disconnect()
    print("\nTimer functionality demo complete!")


def demo_waveform_generation():
    """Demonstrate waveform generation (SPD3303X-specific)."""
    print("\n" + "=" * 60)
    print("Waveform Generation Demo")
    print("=" * 60)

    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")
    psu = PowerSupply("mock", connection=mock_conn)
    psu.connect()

    if not psu.model_capability.has_waveform:
        print("Waveform generation not supported on this model")
        return

    print(f"Connected to: {psu.model_capability.model_name}")

    # Enable waveform on output 1
    print("\n1. Enabling waveform generation on output 1:")
    output = psu.output1
    output.voltage = 5.0

    print(f"   Waveform enabled: {output.waveform_enabled}")
    output.waveform_enabled = True
    print(f"   Waveform enabled: {output.waveform_enabled}")
    print("   Can generate sine, square, ramp, pulse, and noise waveforms")
    print("   Useful for ripple testing, dynamic load simulation, etc.")

    # Disable waveform
    output.waveform_enabled = False
    print(f"   Waveform disabled: {not output.waveform_enabled}")

    psu.disconnect()
    print("\nWaveform generation demo complete!")


def demo_ovp_ocp_protection():
    """Demonstrate OVP/OCP protection limits."""
    print("\n" + "=" * 60)
    print("OVP/OCP Protection Demo")
    print("=" * 60)

    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")
    psu = PowerSupply("mock", connection=mock_conn)
    psu.connect()

    print(f"Connected to: {psu.model_capability.model_name}")

    output = psu.output1

    # OVP (Over-Voltage Protection)
    if psu.model_capability.has_ovp:
        print("\n1. Over-Voltage Protection (OVP):")
        print(f"   Output 1 max voltage: {output._spec.max_voltage}V")
        ovp_limit = 25.0
        output.ovp_level = ovp_limit
        print(f"   OVP set to: {output.ovp_level}V")
        print(f"   PSU will shut down if voltage exceeds {ovp_limit}V")
    else:
        print("\n1. OVP not supported on this model")

    # OCP (Over-Current Protection)
    if psu.model_capability.has_ocp:
        print("\n2. Over-Current Protection (OCP):")
        print(f"   Output 1 max current: {output._spec.max_current}A")
        ocp_limit = 2.5
        output.ocp_level = ocp_limit
        print(f"   OCP set to: {output.ocp_level}A")
        print(f"   PSU will shut down if current exceeds {ocp_limit}A")
    else:
        print("\n2. OCP not supported on this model")

    psu.disconnect()
    print("\nOVP/OCP protection demo complete!")


def demo_real_world_scenario():
    """Demonstrate a real-world testing scenario."""
    print("\n" + "=" * 60)
    print("Real-World Scenario: Automated Device Characterization")
    print("=" * 60)

    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")
    psu = PowerSupply("mock", connection=mock_conn)
    psu.connect()

    print(f"Connected to: {psu.model_capability.model_name}")
    print("\nScenario: Testing a device at different voltage levels")
    print("Logging power consumption at each voltage step")

    # Set up protection
    psu.output1.ovp_level = 15.0
    psu.output1.ocp_level = 2.0
    print(f"\nSafety limits: OVP={psu.output1.ovp_level}V, OCP={psu.output1.ocp_level}A")

    # Start data logging
    with PSUDataLogger(psu, "characterization_log.csv", outputs=[1]) as logger:
        print("\nStarting characterization sweep:")

        # Test at different voltages
        test_voltages = [3.3, 5.0, 9.0, 12.0]

        for voltage in test_voltages:
            print(f"\n  Testing at {voltage}V:")
            psu.output1.voltage = voltage
            psu.output1.current = 2.0  # 2A current limit
            psu.output1.enabled = True

            # Wait for settling
            time.sleep(0.5)

            # Log measurements
            for i in range(3):
                logger.log_measurement()
                v_actual = psu.output1.measure_voltage()
                i_actual = psu.output1.measure_current()
                p_actual = psu.output1.measure_power()
                mode = psu.output1.get_mode()

                print(f"    Sample {i+1}: {v_actual:.3f}V, {i_actual:.3f}A, {p_actual:.3f}W [{mode}]")
                time.sleep(0.5)

        psu.output1.enabled = False

    print(f"\nCharacterization complete! Data saved to: characterization_log.csv")
    psu.disconnect()


if __name__ == "__main__":
    print("=" * 60)
    print("Siglent PSU Advanced Features Demonstration")
    print("=" * 60)
    print("\nThis demo shows advanced PSU capabilities:")
    print("- Data logging (CSV)")
    print("- Tracking modes (series/parallel)")
    print("- Timer functionality")
    print("- Waveform generation")
    print("- OVP/OCP protection")
    print("\nUsing mock connection (no hardware required)")

    try:
        # Run all demos
        demo_data_logging()
        demo_tracking_modes()
        demo_timer_functionality()
        demo_waveform_generation()
        demo_ovp_ocp_protection()
        demo_real_world_scenario()

        print("\n" + "=" * 60)
        print("All demos completed successfully!")
        print("=" * 60)
        print("\nCheck the generated CSV files:")
        print("- psu_manual_log.csv")
        print("- psu_timed_log.csv")
        print("- psu_output1_log.csv")
        print("- characterization_log.csv")

    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback

        traceback.print_exc()
```

---

## Power supply control via USB connection

Power supply control via USB connection.

### Requirements

- scpi_control - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/psu_usb_connection.py
```

### Source Code

```python
"""Power supply control via USB connection.

This example demonstrates how to connect to a Siglent power supply via USB
using the VISAConnection class.

Requirements:
    pip install "SCPI-Instrument-Control[usb]"

Supports:
    - USB (USB-TMC protocol)
    - GPIB (IEEE-488)
    - Serial (RS-232)
    - TCP/IP (VXI-11 or raw socket)
"""

from scpi_control import PowerSupply
from scpi_control.connection import VISAConnection, find_siglent_devices, list_visa_resources


def discover_devices():
    """Discover all available VISA devices."""
    print("=" * 60)
    print("Discovering VISA Devices")
    print("=" * 60)

    # List all VISA resources
    print("\nAll VISA resources:")
    try:
        resources = list_visa_resources()
        if resources:
            for i, resource in enumerate(resources, 1):
                print(f"  {i}. {resource}")
        else:
            print("  No VISA resources found")
            print("\nTroubleshooting:")
            print("  - Ensure device is connected via USB")
            print("  - Install pyvisa-py: pip install pyvisa-py")
            print("  - For Windows: Ensure USB drivers are installed")
    except ImportError as e:
        print(f"  Error: {e}")
        print("\nInstall USB support with:")
        print("  pip install 'SCPI-Instrument-Control[usb]'")
        return None

    # Find Siglent devices specifically
    print("\nSiglent devices:")
    siglent_devices = find_siglent_devices()
    if siglent_devices:
        for i, (resource, idn) in enumerate(siglent_devices, 1):
            print(f"  {i}. {resource}")
            print(f"     {idn}")
    else:
        print("  No Siglent devices found")

    return siglent_devices


def usb_connection_example(resource_string: str):
    """Example: Connect to power supply via USB.

    Args:
        resource_string: VISA resource identifier
            Example: "USB0::0xF4EC::0xEE38::SPD3XXXXXXXXXXX::INSTR"
    """
    print("\n" + "=" * 60)
    print("USB Connection Example")
    print("=" * 60)

    # Create VISA connection for USB
    conn = VISAConnection(resource_string)

    # Create PowerSupply with USB connection
    psu = PowerSupply(host="", connection=conn)

    try:
        # Connect to device
        print(f"\nConnecting to: {resource_string}")
        psu.connect()
        print("Connected successfully!")

        # Display device information
        print(f"\nDevice: {psu.device_info['manufacturer']} {psu.device_info['model']}")
        print(f"Serial: {psu.device_info['serial']}")
        print(f"Firmware: {psu.device_info['firmware']}")
        print(f"Outputs: {psu.model_capability.num_outputs}")

        # Configure output 1
        print("\n--- Configuring Output 1 via USB ---")
        psu.output1.voltage = 5.0
        psu.output1.current = 1.0
        print(f"Set voltage: {psu.output1.voltage}V")
        print(f"Set current limit: {psu.output1.current}A")

        # Enable output
        print("\nEnabling output 1...")
        psu.output1.enable()
        print(f"Output enabled: {psu.output1.enabled}")

        # Read measurements
        print("\n--- Measurements ---")
        measured_v = psu.output1.measure_voltage()
        measured_i = psu.output1.measure_current()
        measured_p = psu.output1.measure_power()

        print(f"Measured voltage: {measured_v:.3f}V")
        print(f"Measured current: {measured_i:.3f}A")
        print(f"Measured power: {measured_p:.3f}W")

        # Disable output (safety)
        print("\nDisabling output 1...")
        psu.output1.disable()

    finally:
        # Always disconnect
        psu.disconnect()
        print("\nDisconnected")


def gpib_connection_example():
    """Example: Connect to power supply via GPIB.

    GPIB address must be configured on the instrument (e.g., address 12).
    """
    print("\n" + "=" * 60)
    print("GPIB Connection Example")
    print("=" * 60)

    # GPIB address 12 (configure on instrument: Utility -> I/O -> GPIB)
    gpib_resource = "GPIB0::12::INSTR"

    conn = VISAConnection(gpib_resource)
    psu = PowerSupply(host="", connection=conn)

    try:
        print(f"\nConnecting to: {gpib_resource}")
        psu.connect()

        print(f"Connected to: {psu.device_info['model']}")

        # Simple voltage setting
        psu.output1.voltage = 3.3
        psu.output1.current = 0.5
        psu.output1.enable()

        v = psu.output1.measure_voltage()
        print(f"Output voltage: {v:.3f}V")

        psu.output1.disable()

    finally:
        psu.disconnect()


def serial_connection_example():
    """Example: Connect to power supply via Serial (RS-232).

    Serial port must be configured on the instrument.
    Default settings: 9600 baud, 8N1, no flow control
    """
    print("\n" + "=" * 60)
    print("Serial Connection Example")
    print("=" * 60)

    # Windows: "ASRL3::INSTR" or "COM3"
    # Linux: "ASRL/dev/ttyUSB0::INSTR"
    serial_resource = "ASRL3::INSTR"  # Change to your COM port

    conn = VISAConnection(serial_resource)
    psu = PowerSupply(host="", connection=conn)

    try:
        print(f"\nConnecting to: {serial_resource}")
        psu.connect()

        print(f"Connected to: {psu.device_info['model']}")

        # Control via serial
        psu.output1.voltage = 12.0
        psu.output1.enable()

        print(f"Output voltage: {psu.output1.voltage}V")

        psu.output1.disable()

    finally:
        psu.disconnect()


def context_manager_example(resource_string: str):
    """Example: Using context manager with USB connection."""
    print("\n" + "=" * 60)
    print("Context Manager Example (USB)")
    print("=" * 60)

    # Create connection
    conn = VISAConnection(resource_string)

    # Using context manager for automatic connection management
    with PowerSupply(host="", connection=conn) as psu:
        print(f"Connected to: {psu.model_capability.model_name}")

        psu.output1.voltage = 5.0
        psu.output1.current = 1.0
        psu.output1.enable()

        v = psu.output1.measure_voltage()
        print(f"Output voltage: {v:.3f}V")

        psu.output1.disable()

    # Automatically disconnected here
    print("Automatically disconnected")


def main():
    """Main example runner."""
    print("=" * 60)
    print("Power Supply USB Connection Examples")
    print("=" * 60)

    # Step 1: Discover devices
    devices = discover_devices()

    if not devices:
        print("\nWARNING: No Siglent devices found")
        print("\nMake sure:")
        print("  1. Device is connected via USB")
        print("  2. USB drivers are installed")
        print("  3. PyVISA is installed: pip install 'SCPI-Instrument-Control[usb]'")
        print("\nFor testing without hardware:")
        print("  - See examples below (commented out)")
        return

    # Step 2: Use the first discovered device
    resource_string, idn = devices[0]
    print(f"\n[OK] Using device: {resource_string}")

    # Run USB example
    usb_connection_example(resource_string)

    # Context manager example
    context_manager_example(resource_string)

    print("\n" + "=" * 60)
    print("Other Connection Types (Uncomment to try)")
    print("=" * 60)
    print("# GPIB: gpib_connection_example()")
    print("# Serial: serial_connection_example()")


if __name__ == "__main__":
    # Check if PyVISA is available
    try:
        from scpi_control.connection import VISAConnection

        main()
    except ImportError:
        print("=" * 60)
        print("PyVISA Not Installed")
        print("=" * 60)
        print("\nUSB support requires PyVISA.")
        print("\nInstall with:")
        print("  pip install 'SCPI-Instrument-Control[usb]'")
        print("\nThis includes:")
        print("  - pyvisa: VISA library interface")
        print("  - pyvisa-py: Pure Python backend (no NI-VISA needed)")
        print("\nAfter installation, run this example again.")
```

---

## Synthetic signal generation: parameterized test waveforms, and the mock

Synthetic signal generation: parameterized test waveforms, and the mock
oscilloscope's state-coupled synthesis.

### Requirements

- scpi_control - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/synthetic_signals.py
```

### Source Code

```python
"""Synthetic signal generation: parameterized test waveforms, and the mock
oscilloscope's state-coupled synthesis.

scpi_control.signal_synth.SignalSpec describes a waveform (kind, frequency,
amplitude, offset, phase, duty, additive noise, and an optional seed for
reproducibility); synthesize()/make_waveform() turn a spec into a numpy array
or a full WaveformData ready for analysis, saving, or the report generator.
The same engine powers MockConnection: channels without an explicit
waveform_payloads entry synthesize live from the mock's current state, so
SCPI commands that change the timebase or voltage scale visibly change the
next capture -- exactly like a real scope.

This example (1) generates a few signal kinds directly and prints basic
stats, (2) opens a mock oscilloscope session, acquires, then changes TDIV and
VDIV over SCPI to show the capture's length and clipping respond, and (3)
saves one synthesized capture and reloads it with load_waveform() to show the
chain composes.

Requirements: SCPI-Instrument-Control (core install) -- runs entirely against
a mock connection, no instrument needed.
"""

from pathlib import Path

from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.signal_synth import SignalSpec, make_waveform
from scpi_control.waveform_io import load_waveform

OUTPUT_DIR = Path.cwd()
NPZ_PATH = OUTPUT_DIR / "synthetic_demo.npz"

# 8-bit code path constants the mock synthesizer uses internally
# (scpi_control/connection/mock/synth.py) -- reused here only to predict the
# voltage ceiling a given V/div setting clips at.
CODES_PER_DIV = 25
CODE_LIMIT = 127


def _print_stats(label: str, voltage) -> None:
    vpp = float(voltage.max() - voltage.min())
    print(f"{label:12s}: Vpp={vpp:.4f} V  mean={voltage.mean():.4f} V  std={voltage.std():.4f} V  n={len(voltage)}")


def demo_make_waveform() -> None:
    """Generate a few signal kinds directly and print basic stats."""
    print("=== Part 1: make_waveform() -- basic stats per kind ===")
    kinds = [
        ("square", SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0, duty=0.5)),
        ("sine", SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0)),
        ("noisy sine", SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.05, seed=7)),
    ]
    for label, spec in kinds:
        waveform = make_waveform(spec, sample_rate=100_000.0, n_points=1_000)
        _print_stats(label, waveform.voltage)


def demo_mock_session() -> None:
    """Open a mock scope session and show SCPI writes change the next capture."""
    print()
    print("=== Part 2: mock oscilloscope session -- state-coupled synthesis ===")
    conn = MockConnection(
        "mock",
        idn="Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0",
        channel_states={1: True, 2: False, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=1_000_000.0,
        timebase=1e-3,
        signals={1: SignalSpec(kind="sine", frequency=2_000.0, amplitude=0.8, noise_rms=0.02, seed=42)},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    try:
        waveform = scope.get_waveform(1, provenance=False)
        print(f"Initial capture (TDIV=1e-3, C1:VDIV=1.0): {len(waveform.voltage)} points, " f"Vpp={float(waveform.voltage.max() - waveform.voltage.min()):.3f} V")

        # Shrinking the timebase shrinks the acquisition window (14 divisions
        # x timebase), so fewer points come back at the same sample rate.
        scope.write("TDIV 1e-4")
        shorter = scope.get_waveform(1, provenance=False)
        print(f"After TDIV 1e-4: {len(shorter.voltage)} points (window shrank from 14 ms to 1.4 ms)")

        # Tightening the voltage scale below the signal's amplitude clips the
        # capture, just like an 8-bit scope's ADC would over-range.
        scope.write("C1:VDIV 0.1")
        clipped = scope.get_waveform(1, provenance=False)
        clip_ceiling = CODE_LIMIT * 0.1 / CODES_PER_DIV
        peak = float(max(abs(clipped.voltage.max()), abs(clipped.voltage.min())))
        print(f"After C1:VDIV 0.1: peak |V| = {peak:.3f} V (signal amplitude is 0.8 V, " f"but the 8-bit code path ceilings at ~{clip_ceiling:.3f} V for this V/div)")

        print()
        print("=== Part 3: save + load_waveform() -- the chain composes ===")
        final = scope.get_waveform(1, provenance=True)
        scope.waveform.save_waveform(final, str(NPZ_PATH))
        print(f"Saved {NPZ_PATH.name} ({len(final.voltage)} points)")
    finally:
        scope.disconnect()


def demo_reload() -> None:
    """Reload the saved capture and show the raw data survives the round trip."""
    loaded = load_waveform(NPZ_PATH)
    print(f"Reloaded {NPZ_PATH.name} ({loaded.source_format}): {len(loaded.voltage)} points, " f"channel {loaded.channel}, sample_rate {loaded.sample_rate}")
    print(f"First 5 samples (V): {loaded.voltage[:5].tolist()}")


def main() -> None:
    demo_make_waveform()
    demo_mock_session()
    demo_reload()


if __name__ == "__main__":
    main()
```

---

## Record measurement trends in-process and export them as CSV

Record measurement trends in-process and export them as CSV.

### Requirements

- scpi_control - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/trend_logging_walkthrough.py
```

### Source Code

```python
"""Record measurement trends in-process and export them as CSV.

Uses the gateway's session layer directly (no server or browser needed):
a mock oscilloscope session polls measurements ~1x/second while a
subscriber is attached, records them into the session's trend recorder,
and the rows are exported to CSV at the end.

The same recorder powers the browser UI's Log tab and the
/api/sessions/{id}/scope/log.csv endpoint when running scpi-web.

Requirements: SCPI-Instrument-Control (core install; the session layer is
FastAPI-free)
"""

import csv
import time
from datetime import datetime

from scpi_control.server.sessions import InstrumentSession

RECORD_SECONDS = 5


def main() -> None:
    session = InstrumentSession.open("trend demo", mock=True)
    try:
        # The poll loop only runs while someone is listening (a browser tab,
        # or here: a trivial subscriber).
        unsubscribe = session.subscribe(lambda message: None)

        session.set_measurements([(1, "PKPK"), (1, "FREQ")])
        session.start_recording()
        print(f"Recording C1 PKPK + FREQ for {RECORD_SECONDS} s...")
        time.sleep(RECORD_SECONDS)
        status = session.stop_recording()
        unsubscribe()
        print(f"Recorded {status['row_count']} rows")

        rows = session.recorder.rows_since()
        columns = [f"C{c['channel']} {c['mtype']}" for c in status["columns"]]
        with open("trend_log.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", *columns])
            for row in rows:
                writer.writerow([datetime.fromtimestamp(row[0]).isoformat(), *row[1:]])
        print(f"Saved trend_log.csv ({len(rows)} rows x {len(columns)} measurements)")
    finally:
        session.close()


if __name__ == "__main__":
    main()
```

---

## Trigger-based event capture

Trigger-based event capture.

### Requirements

- scpi_control - Core library
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

Requirements: an oscilloscope reachable on the network -- edit SCOPE_IP below
to match its LAN address.

Expected output: a single trigger wait (up to 30s) that saves to
'trigger_captures/' if it fires, followed by up to 10 polled trigger events
saved to 'multi_trigger_captures/' in the current directory.
"""

from scpi_control.automation import DataCollector, TriggerWaitCollector

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

## Acquisition provenance and the load_waveform() / scpi-extract workflow

Acquisition provenance and the load_waveform() / scpi-extract workflow.

### Requirements

- scpi_control - Core library
- Oscilloscope connected to network

### Configuration

Update `SCOPE_IP` to match your oscilloscope's IP address (default: `192.168.1.100`).

### Usage

```bash
python examples/waveform_provenance_and_extract.py
```

### Source Code

```python
"""Acquisition provenance and the load_waveform() / scpi-extract workflow.

Every saved waveform now embeds a snapshot of the instrument state that
produced it: instrument IDN, per-channel settings (scale, coupling, probe
ratio), trigger configuration, timebase, sample rate, and a UTC timestamp.
This example acquires from a mock oscilloscope (no hardware required), saves
NPZ and CSV, then reads both back with scpi_control.waveform_io.load_waveform()
and prints the instrument model, channel scale, and first few samples --
exactly what scpi-extract does from the command line.

To inspect the saved files yourself:
    scpi-extract provenance_demo.npz
    scpi-extract provenance_demo.csv --json

Requirements: SCPI-Instrument-Control (core install) -- runs entirely against
a mock connection, no instrument needed.
"""

from pathlib import Path

from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.waveform_io import load_waveform

OUTPUT_DIR = Path.cwd()
NPZ_PATH = OUTPUT_DIR / "provenance_demo.npz"
CSV_PATH = OUTPUT_DIR / "provenance_demo.csv"


def acquire_and_save() -> None:
    """Connect to a mock scope, acquire channel 1 with provenance, and save it."""
    conn = MockConnection(
        "mock",
        idn="Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0",
        channel_states={1: True, 2: False, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=1_000.0,
        timebase=1e-3,
        waveform_payloads={1: bytes(range(256))},
        # The base mock doesn't answer every legacy-dialect query (e.g. probe
        # ratio); fill in the ones the provenance snapshot reads so channel 1
        # comes back fully populated instead of silently falling back to None.
        custom_responses={"C1:ATTN?": "10", "C1:BWL?": "OFF", "C1:UNIT?": "V"},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    try:
        # provenance=True is the default; shown here for clarity.
        waveform = scope.get_waveform(1, provenance=True)
        scope.waveform.save_waveform(waveform, str(NPZ_PATH), format="NPY")
        scope.waveform.save_waveform(waveform, str(CSV_PATH), format="CSV")
        print(f"Saved {NPZ_PATH.name} and {CSV_PATH.name}")
    finally:
        scope.disconnect()


def inspect(path: Path) -> None:
    """Reload a saved waveform and print what its provenance records."""
    loaded = load_waveform(path)
    print(f"\n--- {path.name} ({loaded.source_format}) ---")

    prov = loaded.provenance
    if prov is None:
        print("No provenance recorded (file predates this feature).")
        return

    if prov.instrument is not None:
        print(f"Instrument model: {prov.instrument.model}")

    channel_settings = prov.channels.get(loaded.channel) or prov.channels.get(1)
    if channel_settings is not None:
        print(f"Channel {channel_settings.channel} scale: {channel_settings.voltage_scale} V/div (probe {channel_settings.probe_ratio}x)")

    print(f"Acquired (UTC): {prov.acquired_at}")
    print(f"First 5 samples (V): {loaded.voltage[:5].tolist()}")


def main() -> None:
    acquire_and_save()
    inspect(NPZ_PATH)
    inspect(CSV_PATH)


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
