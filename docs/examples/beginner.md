# Beginner Examples

Complete examples for getting started with the Siglent Oscilloscope library. These examples demonstrate core functionality and common use cases.

## Quick Reference

| Example | Description |
|---------|-------------|
| [Basic usage example for Siglent oscilloscope control](#basic-usage-example-for-siglent-oscilloscope-control) | Basic usage example for Siglent oscilloscope control. |
| [Basic Data Logger / DAQ example](#basic-data-logger-daq-example) | Basic Data Logger / DAQ example. |
| [SCPI dialect auto-detection and manual override](#scpi-dialect-auto-detection-and-manual-override) | SCPI dialect auto-detection and manual override. |
| [Basic Function Generator / AWG Usage Example](#basic-function-generator-awg-usage-example) | Basic Function Generator / AWG Usage Example. |
| [Measurement example for Siglent oscilloscope](#measurement-example-for-siglent-oscilloscope) | Measurement example for Siglent oscilloscope. |
| [Discover SCPI instruments on the local network](#discover-scpi-instruments-on-the-local-network) | Discover SCPI instruments on the local network. |
| [Basic power supply control example](#basic-power-supply-control-example) | Basic power supply control example. |
| [Pulling a screenshot off the instrument's display](#pulling-a-screenshot-off-the-instruments-display) | Pulling a screenshot off the instrument's display. |
| [Simple single capture example](#simple-single-capture-example) | Simple single capture example. |
| [Waveform capture example for Siglent oscilloscope](#waveform-capture-example-for-siglent-oscilloscope) | Waveform capture example for Siglent oscilloscope. |

---

## Basic usage example for Siglent oscilloscope control

Basic usage example for Siglent oscilloscope control.

### Requirements

- scpi_control - Core library
- None -- runs on the built-in mock; `--host <ip>` for real hardware

### Configuration

None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.

### Usage

```bash
python examples/basic_usage.py
```

### Source Code

```python
"""Basic usage example for Siglent oscilloscope control.

This script demonstrates how to connect to an oscilloscope,
configure channels and trigger, and perform basic operations.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Expected output: connection/device info, channel and trigger configuration
echoed to the console, frequency/Vpp measurements on Channel 1, and a summary
of each enabled channel's configuration. No files are written.
"""

import argparse

from scpi_control import Coupling, Oscilloscope, TriggerMode, TriggerSlope
from scpi_control.connection import MockConnection
from scpi_control.signal_synth import SignalSpec


def _connect(host):
    """Return a mock connection for --host mock, or None to use a real socket."""
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True},
        signals={1: SignalSpec(kind="square", frequency=1000.0, amplitude=1.65, offset=1.65)},
        sample_rate=20e6,
        timebase=500e-6,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' for the built-in mock scope (default: mock)")
    args = parser.parse_args()

    scope = Oscilloscope(args.host, connection=_connect(args.host))

    try:
        # Connect to oscilloscope
        print(f"Connecting to oscilloscope at {args.host}...")
        scope.connect()

        # Get device information
        print(f"\nConnected to: {scope.identify()}")
        if scope.device_info:
            print(f"Model: {scope.device_info['model']}")
            print(f"Serial: {scope.device_info['serial']}")
            print(f"Firmware: {scope.device_info['firmware']}")

        # Ask before calling: what can this scope's dialect express?
        caps = scope.capabilities
        print(f"Trigger types on this scope: {sorted(caps.trigger_types)}")
        print(f"Channel couplings: {sorted(caps.channel_couplings)}")

        # Configure channel 1
        print("\nConfiguring Channel 1...")
        scope.channel1.enable()
        scope.channel1.coupling = Coupling.DC
        scope.channel1.voltage_scale = 1.0  # 1V/div
        scope.channel1.voltage_offset = 0.0
        scope.channel1.probe_ratio = 10.0  # 10X probe
        print(f"Channel 1 configured: {scope.channel1}")

        # Configure trigger
        print("\nConfiguring Trigger...")
        scope.trigger.mode = TriggerMode.AUTO
        scope.trigger.source = "C1"  # Plain strings work too -- enums are optional sugar
        scope.trigger.level = 0.0  # Trigger at 0V
        scope.trigger.slope = TriggerSlope.POS  # Rising edge
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

    finally:
        # Disconnect
        print("\nDisconnecting...")
        scope.disconnect()
        print("Done!")


if __name__ == "__main__":
    main()
```

---

## Basic Data Logger / DAQ example

Basic Data Logger / DAQ example.

### Requirements

- scpi_control - Core library
- None -- runs on the built-in mock; `--host <ip>` for real hardware

### Configuration

None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.

### Usage

```bash
python examples/data_logger_basic.py
```

### Source Code

```python
"""Basic Data Logger / DAQ example.

This example demonstrates basic usage of the DataLogger class for
data acquisition systems like the Keysight 34970A/DAQ970A.

Requirements: none by default -- runs against the built-in mock DAQ (a
Keysight 34970A). Pass --host <ip> to drive a real DAQ/switch unit on the
network.

Expected output: basic voltage measurements, all narrated on the console.
No files are written.

Against --host mock (the default) or with --all-demos, four more demos also
run: a multi-channel scan, ~5 seconds of continuous logging, and
alarm-limit / mx+b scaling demos. These write channel, scan-list, alarm,
and scaling configuration to the instrument, so against a real DAQ
(--host <ip>) they are opt-in only -- pass --all-demos to run them there.

Mock fidelity note: the mock DAQ's readings are a fixed, static CSV string
(three values by default) returned for every measurement/scan/fetch query,
regardless of how many channels are in the scan list or what channels were
configured. Against --host mock, scan_multiple_channels() below will report
3 scanned channels even though 5 were configured, and continuous_logging()
will report the same three readings on every scan -- neither tracks real
channel count or varies over time. This is a mock limitation, not a bug in
this example.
"""

import argparse

from scpi_control import DataLogger
from scpi_control.connection import MockConnection


def _connect(host):
    """Return a mock connection for --host mock, or None to use a real socket."""
    if host != "mock":
        return None
    return MockConnection("mock", daq_mode=True)


def basic_measurements(host):
    """Demonstrate basic voltage measurements."""
    print("=== Basic Voltage Measurements ===\n")

    with DataLogger(host, connection=_connect(host)) as daq:
        print(f"Connected to: {daq.identify()}")
        print(f"Model: {daq.model_capability.model_name}")
        print(f"Channels available: {daq.model_capability.get_all_channels()}\n")

        # Configure channels 101-103 for DC voltage measurement
        channels = [101, 102, 103]
        daq.configure_voltage_dc(channels, range="AUTO", resolution="AUTO")
        print(f"Configured channels {channels} for DC voltage\n")

        # Take immediate measurements
        readings = daq.measure_voltage_dc(channels)
        print("Measurement results:")
        for reading in readings:
            print(f"  Channel {reading.channel}: {reading.value:.6f} {reading.unit}")


def scan_multiple_channels(host):
    """Demonstrate scanning multiple channels."""
    print("\n=== Multi-Channel Scan ===\n")

    with DataLogger(host, connection=_connect(host)) as daq:
        # Configure different measurement types on different channels
        daq.configure_voltage_dc([101, 102], range="10")  # 10V range
        daq.configure_temperature([103, 104], sensor_type="TC", sensor_subtype="K")
        daq.configure_resistance([105], four_wire=False)

        # Set up scan list
        scan_channels = [101, 102, 103, 104, 105]
        daq.set_scan_list(scan_channels)
        print(f"Scan list: {daq.get_scan_list()}")

        # Configure trigger for immediate single scan
        daq.set_trigger_source("IMM")
        daq.set_trigger_count(1)

        # Initiate and read
        readings = daq.read()
        print(f"\nScanned {len(readings)} channels:")
        for i, reading in enumerate(readings):
            ch = scan_channels[i] if i < len(scan_channels) else "?"
            print(f"  Channel {ch}: {reading.value:.6f}")


def continuous_logging(host):
    """Demonstrate continuous data logging."""
    print("\n=== Continuous Logging (5 seconds) ===\n")

    with DataLogger(host, connection=_connect(host)) as daq:
        # Configure for voltage monitoring
        channels = [101, 102]
        daq.configure_voltage_dc(channels)

        # Log at 1 second intervals for 5 seconds
        print("Logging for 5 seconds...")
        all_readings = daq.start_logging(
            channels=channels,
            interval=1.0,
            duration=5.0,
            callback=lambda r: print(f"  Got {len(r)} readings"),
        )

        print(f"\nTotal scans collected: {len(all_readings)}")
        print(f"Total readings: {sum(len(r) for r in all_readings)}")


def alarm_monitoring(host):
    """Demonstrate alarm/limit checking."""
    print("\n=== Alarm Monitoring ===\n")

    with DataLogger(host, connection=_connect(host)) as daq:
        if not daq.model_capability.has_alarm:
            print("This model does not support alarm limits")
            return

        # Configure voltage measurement with limits
        channel = 101
        daq.configure_voltage_dc(channel)

        # Set alarm limits: warn if voltage goes outside 0-5V
        daq.set_alarm_limits(channel, high=5.0, low=0.0)
        daq.enable_alarm(channel, enable=True)
        print(f"Alarm limits set on channel {channel}: 0V to 5V")

        # Take a measurement
        readings = daq.measure_voltage_dc(channel)
        print(f"Current reading: {readings[0].value:.3f} V")


def scaling_example(host):
    """Demonstrate mx+b scaling."""
    print("\n=== Scaling (mx+b) Example ===\n")

    with DataLogger(host, connection=_connect(host)) as daq:
        if not daq.model_capability.has_math:
            print("This model does not support scaling")
            return

        channel = 101
        daq.configure_voltage_dc(channel)

        # Apply scaling: convert 0-10V input to 0-100% display
        # Scaled value = (reading * 10) + 0 = percentage
        daq.set_scaling(channel, gain=10.0, offset=0.0, enable=True)
        print("Scaling configured: 0-10V input -> 0-100% output")

        readings = daq.measure_voltage_dc(channel)
        print(f"Raw voltage: {readings[0].value:.3f} V")
        # Note: scaled value would be returned if DAQ returns scaled data


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="DAQ hostname/IP, or 'mock' for the built-in mock DAQ (default: mock)")
    parser.add_argument(
        "--all-demos",
        action="store_true",
        help="Also run the multi-channel scan, continuous logging, alarm-limit, and mx+b scaling demos "
        "against a real --host. These write channel/scan-list/alarm/scaling configuration to the "
        "instrument -- opt in deliberately. Always on against --host mock.",
    )
    args = parser.parse_args()

    print("Data Logger / DAQ Basic Examples")
    print("================================\n")

    basic_measurements(args.host)

    # Writing scan/alarm/scaling configuration is opt-in on real hardware:
    # the original gated these behind manual uncommenting.
    if args.host == "mock" or args.all_demos:
        scan_multiple_channels(args.host)
        continuous_logging(args.host)
        alarm_monitoring(args.host)
        scaling_example(args.host)
    else:
        print("\nSkipping scan/logging/alarm/scaling demos (they write configuration to the instrument). " "Pass --all-demos to run them against real hardware.")


if __name__ == "__main__":
    main()
```

---

## SCPI dialect auto-detection and manual override

SCPI dialect auto-detection and manual override.

### Requirements

- scpi_control - Core library
- No hardware required

### Configuration

No hardware required.

### Usage

```bash
python examples/dialect_override_example.py
```

### Source Code

```python
"""SCPI dialect auto-detection and manual override.

The library speaks two Siglent command sets: "legacy" (SDS1000X-E era,
e.g. C1:VDIV 500mV) and "modern" (SDS800X HD era, e.g. :CHANnel1:SCALe 0.5).
The dialect is auto-detected from *IDN? at connect; pass dialect= to force
one when detection guesses wrong. This example uses mock connections so it
runs without hardware.

Requirements: SCPI-Instrument-Control (core install)
"""

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection
from scpi_control.exceptions import SiglentTimeoutError

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
MODERN_IDN = "Siglent Technologies,SDS824X HD,MOCK0002,3.8.12"


def show(scope: Oscilloscope, label: str) -> None:
    scope.connect()
    try:
        print(f"{label}: model={scope.device_info.get('model')}, detected dialect={scope.dialect}")
        scope.timebase = 1e-3  # same API call regardless of dialect
        print(f"  timebase set to {scope.timebase} s/div via the {scope.dialect} command set")
    finally:
        scope.disconnect()


def main() -> None:
    # Auto-detection from *IDN?
    show(Oscilloscope("mock", connection=MockConnection("mock", idn=LEGACY_IDN)), "Legacy scope (auto)")
    show(Oscilloscope("mock", connection=MockConnection("mock", idn=MODERN_IDN)), "Modern scope (auto)")

    # Manual override: dialect= exists for the case where the model registry
    # misidentifies real hardware from *IDN? and you need to force the wire
    # protocol the instrument *actually* speaks. Forcing a dialect the
    # instrument does NOT speak is a misuse - and our mock is faithful enough
    # to prove it: it answers only the real protocol for its *IDN?, so
    # forcing "modern" onto a legacy-speaking instrument here fails exactly
    # like it would on real mismatched hardware (a timeout, not a crash).
    forced = Oscilloscope("mock", connection=MockConnection("mock", idn=LEGACY_IDN), dialect="modern")
    forced.connect()
    try:
        print(f"Legacy IDN, dialect forced to modern: model={forced.device_info.get('model')}, dialect={forced.dialect}")
        try:
            forced.timebase = 1e-3
            print(f"  timebase set to {forced.timebase} s/div via the {forced.dialect} command set")
        except SiglentTimeoutError:
            print("  (expected) a modern-dialect query against a legacy-speaking instrument timed out")
            print("  -- only override dialect to match what the real instrument speaks")
    finally:
        forced.disconnect()
    # On real hardware, override with the dialect the instrument actually
    # speaks: Oscilloscope("192.168.1.100", dialect="modern")


if __name__ == "__main__":
    main()
```

---

## Basic Function Generator / AWG Usage Example

Basic Function Generator / AWG Usage Example.

### Requirements

- scpi_control - Core library
- None -- runs on the built-in mock; `--host <ip>` for real hardware

### Configuration

None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.

### Usage

```bash
python examples/function_generator_basic.py
```

### Source Code

```python
"""Basic Function Generator / AWG Usage Example.

This example demonstrates basic control of Siglent SDG series function generators
using SCPI commands over Ethernet/LAN.

Supported models:
- SDG1000X series (SDG1020, SDG1025, SDG1032X, etc.)
- SDG2000X series (SDG2042X, SDG2082X, SDG2122X, etc.)
- Generic SCPI-compliant arbitrary waveform generators

Requirements: none by default -- runs against the built-in mock AWG. Pass
--host <ip> to drive a real function generator on the network (default
SCPI port: 5025).

Expected output: log lines narrating each waveform demo (sine, square,
pulse, ramp, channel synchronization, manual configuration) and the final
"all outputs off" safety step. No files are written.

Usage:
    python function_generator_basic.py --host 192.168.1.100
"""

import argparse
import logging
import time

from scpi_control import FunctionGenerator
from scpi_control.connection import MockConnection

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _connect(host):
    """Return a mock connection for --host mock, or None to use a real socket."""
    if host != "mock":
        return None
    return MockConnection("mock", awg_mode=True)


def main():
    """Main function to demonstrate AWG control."""
    parser = argparse.ArgumentParser(description="Control Siglent Function Generator")
    parser.add_argument("--host", type=str, default="mock", help="Function generator hostname/IP, or 'mock' for the built-in mock AWG (default: mock)")
    parser.add_argument("--port", type=int, default=5025, help="SCPI port (default: 5025)")
    args = parser.parse_args()

    logger.info(f"Connecting to function generator at {args.host}:{args.port}")

    # Using context manager for automatic connection/disconnection
    with FunctionGenerator(args.host, port=args.port, connection=_connect(args.host)) as awg:
        # Get device info
        logger.info(f"Connected to: {awg.identify()}")
        logger.info(f"Model: {awg.model_capability.model_name}")
        logger.info(f"Manufacturer: {awg.model_capability.manufacturer}")
        logger.info(f"Channels: {awg.model_capability.num_channels}")
        logger.info(f"SCPI variant: {awg.model_capability.scpi_variant}")

        # Example 1: Generate a simple sine wave
        logger.info("\n=== Example 1: Sine Wave ===")
        awg.channel1.configure_sine(frequency=1000.0, amplitude=5.0, offset=0.0)
        awg.channel1.enable()
        logger.info("Channel 1: 1kHz sine wave, 5Vpp, 0V offset")
        logger.info(f"Configuration: {awg.channel1.get_configuration()}")

        time.sleep(2)

        # Example 2: Generate a square wave on channel 2
        if awg.model_capability.num_channels >= 2:
            logger.info("\n=== Example 2: Square Wave ===")
            awg.channel2.configure_square(frequency=500.0, amplitude=3.3)
            awg.channel2.enable()
            logger.info("Channel 2: 500Hz square wave, 3.3Vpp")

            time.sleep(2)

        # Example 3: Pulse wave with duty cycle control
        logger.info("\n=== Example 3: Pulse Wave ===")
        awg.channel1.configure_pulse(
            frequency=10e3,  # 10 kHz
            amplitude=2.0,
            duty_cycle=25.0,  # 25% duty cycle
            offset=0.5,
        )
        logger.info("Channel 1: 10kHz pulse, 2Vpp, 25% duty cycle, 0.5V offset")

        time.sleep(2)

        # Example 4: Ramp/Triangle wave with symmetry control
        logger.info("\n=== Example 4: Ramp Wave ===")
        awg.channel1.configure_ramp(
            frequency=1000.0,
            amplitude=4.0,
            symmetry=50.0,  # 50% = triangle wave
        )
        logger.info("Channel 1: 1kHz triangle wave (50% symmetry), 4Vpp")

        time.sleep(2)

        # Example 5: Channel synchronization (phase offset)
        if awg.model_capability.num_channels >= 2:
            logger.info("\n=== Example 5: Channel Synchronization ===")
            awg.channel1.configure_sine(frequency=1000.0, amplitude=5.0)
            awg.channel2.configure_sine(frequency=1000.0, amplitude=5.0)
            awg.sync_channels(phase_offset=90.0)  # 90 degrees phase shift
            awg.channel1.enable()
            awg.channel2.enable()
            logger.info("Channels 1 and 2: synchronized with 90° phase offset")

            time.sleep(2)

        # Example 6: Manual waveform configuration
        logger.info("\n=== Example 6: Manual Configuration ===")
        awg.channel1.function = "SINE"
        awg.channel1.frequency = 2500.0  # 2.5 kHz
        awg.channel1.amplitude = 3.0  # 3 Vpp
        awg.channel1.offset = 1.5  # 1.5V DC offset
        awg.channel1.phase = 0.0
        awg.channel1.enable()
        logger.info(f"Channel 1 configured manually: {awg.channel1.function}, " f"{awg.channel1.frequency}Hz, {awg.channel1.amplitude}Vpp")

        time.sleep(2)

        # Turn off all outputs (safety)
        logger.info("\n=== Turning off all outputs ===")
        awg.all_outputs_off()
        logger.info("All outputs disabled")

    logger.info("\nDisconnected from function generator")


if __name__ == "__main__":
    main()
```

---

## Measurement example for Siglent oscilloscope

Measurement example for Siglent oscilloscope.

### Requirements

- scpi_control - Core library
- None -- runs on the built-in mock; `--host <ip>` for real hardware

### Configuration

None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.

### Usage

```bash
python examples/measurements.py
```

### Source Code

```python
"""Measurement example for Siglent oscilloscope.

This script demonstrates how to perform automated measurements
on oscilloscope channels.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Expected output: individual measurements (frequency, period, Vpp, amplitude,
max/min, RMS, mean) on Channel 1 printed to the console, followed by the
combined result of measure_all(). No files are written.

Note: against --host mock, the instrument-side :MEASure values are fixed
constants and do not track the synthesized waveform. See advanced_analysis.py
for numbers computed from captured samples, which do track it. This is a mock
fidelity limit, not a measurement error.
"""

import argparse
import time

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection
from scpi_control.signal_synth import SignalSpec


def _connect(host):
    """Return a mock connection for --host mock, or None to use a real socket."""
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True},
        signals={1: SignalSpec(kind="square", frequency=1000.0, amplitude=1.65, offset=1.65)},
        sample_rate=20e6,
        timebase=500e-6,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' for the built-in mock scope (default: mock)")
    args = parser.parse_args()

    scope = Oscilloscope(args.host, connection=_connect(args.host))
    scope.connect()

    try:
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
            print(f"Period:       {period*1e6:.6f} us")
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
                    print(f"{name:12s}: {value*1e6:.6f} us")
                else:
                    print(f"{name:12s}: {value:.6f} V")
            else:
                print(f"{name:12s}: N/A")

        print("\nDone!")

    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()
```

---

## Discover SCPI instruments on the local network

Discover SCPI instruments on the local network.

### Requirements

- scpi_control - Core library
- No hardware required

### Configuration

No hardware required.

### Usage

```bash
python examples/network_discovery.py
```

### Source Code

```python
"""Discover SCPI instruments on the local network.

Scans a range of addresses, probes each for a SCPI *IDN? response, and prints
what it finds. This example scans a documentation-only TEST-NET range so it
returns quickly with no results in most environments; change `cidr` (or pass
cidr=None to auto-scan your local /24) to find real instruments.

Requirements: SCPI-Instrument-Control (core install, no hardware)
"""

from scpi_control.server.discovery import discover


def main():
    print("=" * 60)
    print("Network instrument discovery")
    print("=" * 60)

    # A small TEST-NET-1 range (RFC 5737): fast and hostless, for a safe demo.
    # For real use: discover(cidr=None) auto-scans your local subnet, or pass a
    # CIDR like discover(cidr="192.168.1.0/24").
    cidr = "192.0.2.0/30"
    print(f"Scanning {cidr} ...")
    found = discover(cidr=cidr, connect_timeout=0.3, probe_timeout=0.5)

    if not found:
        print("No instruments found in this range.")
    else:
        print(f"Found {len(found)} instrument(s):")
        for entry in found:
            print(f"  {entry}")

    print("=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

---

## Basic power supply control example

Basic power supply control example.

### Requirements

- scpi_control - Core library
- None -- runs on the built-in mock; `--host <ip>` for real hardware

### Configuration

None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.

### Usage

```bash
python examples/psu_basic_control.py
```

### Source Code

```python
"""Basic power supply control example.

This example demonstrates how to control a SCPI power supply using the
scpi_control package. Works with both Siglent SPD series and generic
SCPI-99 compliant power supplies.

Connection Methods:
    - Ethernet/LAN (this example): PowerSupply('192.168.1.200')
    - USB: See psu_usb_connection.py

For USB support:
    pip install "SCPI-Instrument-Control[usb]"

Requirements: none by default -- runs against the built-in mock PSU (a
3-output Siglent SPD3303X). Pass --host <ip> to drive a real power supply
on the network.

Expected output: connection/device info, output 1 setpoints and
measurements, all echoed to the console. No files are written.

Against --host mock (the default) or with --all-demos, two more demos also
run: a 3-output walkthrough (CH3 is the SPD3303X's fixed auxiliary rail --
see the comments in multi_output_demo() for what it does and doesn't
support) and a context-manager demo. These drive outputs 2 and 3 to fixed
setpoints, so against a real power supply (--host <ip>) they are opt-in
only -- pass --all-demos to run them there.
"""

import argparse

from scpi_control import PowerSupply
from scpi_control.connection import MockConnection


def _connect(host):
    """Return a mock connection for --host mock, or None to use a real socket."""
    if host != "mock":
        return None
    return MockConnection("mock", psu_mode=True)


def basic_output_demo(host):
    """Connect, configure output 1, measure, and disconnect."""
    psu = PowerSupply(host, connection=_connect(host))

    print("Connecting to power supply...")
    psu.connect()
    try:
        # Display device information
        print(f"\nConnected to: {psu.device_info['manufacturer']} {psu.device_info['model']}")
        print(f"Firmware: {psu.device_info['firmware']}")
        print(f"Serial: {psu.device_info['serial']}")
        print(f"Number of outputs: {psu.model_capability.num_outputs}")
        print(f"SCPI variant: {psu.model_capability.scpi_variant}")

        # Configure output 1
        print("\n--- Configuring Output 1 ---")
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

        # get_mode() is not supported on every model (e.g. plain SCPI-99
        # supplies); a narrow catch here for a genuinely optional query, not
        # a safety net for unexpected failures.
        try:
            mode = psu.output1.get_mode()
            print(f"Operating mode: {mode}")
        except Exception as e:
            print(f"Mode query not supported: {e}")

        # Get full configuration
        print("\n--- Output 1 Configuration ---")
        config = psu.output1.get_configuration()
        for key, value in config.items():
            print(f"{key}: {value}")

        # Disable output (safety)
        print("\nDisabling output 1...")
        psu.output1.disable()
        print(f"Output enabled: {psu.output1.enabled}")
    finally:
        psu.disconnect()
        print("\nDisconnected from power supply")


def multi_output_demo(host):
    """Example for multi-output power supplies (e.g., SPD3303X)."""
    psu = PowerSupply(host, connection=_connect(host))
    psu.connect()

    try:
        if psu.model_capability.num_outputs < 3:
            print("This example requires a 3-output power supply -- skipping")
            return

        print(f"\nConfiguring {psu.model_capability.num_outputs} outputs...")

        # Configure different voltages on each output
        psu.output1.voltage = 5.0
        psu.output1.current = 2.0
        psu.output1.enable()

        psu.output2.voltage = 12.0
        psu.output2.current = 1.5
        psu.output2.enable()

        # CH3 is the fixed auxiliary rail. Its voltage is selected by the DIP
        # switch on the front panel (2.5V / 3.3V / 5V -- QS0503X-E01B p.21), and
        # the SPD3303X command set has no way to set or measure it: VOLTage and
        # CURRent are [{CH1|CH2}:] only (p.39) and MEASure is [{CH1|CH2}] (p.38).
        # Setting output3.voltage now raises FeatureNotSupportedError rather than
        # sending a command the firmware discards. Switching it on IS documented
        # (OUTPut {CH1|CH2|CH3},{ON|OFF}, p.40):
        psu.output3.enable()

        # Read all measurements. CH3 has no MEASure form (QS0503X-E01B p.38), so
        # skip it rather than let measure_voltage() raise FeatureNotSupportedError.
        for output_num in [1, 2, 3]:
            spec = psu.model_capability.output_specs[output_num - 1]
            if not spec.measurable:
                print(f"Output {output_num}: measurement not supported (fixed rail)")
                continue
            output = getattr(psu, f"output{output_num}")
            v = output.measure_voltage()
            i = output.measure_current()
            p = output.measure_power()
            print(f"Output {output_num}: {v:.2f}V, {i:.3f}A, {p:.2f}W")

        # Safety: Turn off all outputs
        print("\nTurning off all outputs (safety)...")
        psu.all_outputs_off()
    finally:
        psu.disconnect()


def context_manager_demo(host):
    """Example using a context manager for automatic connection management."""
    with PowerSupply(host, connection=_connect(host)) as psu:
        print(f"Connected to {psu.model_capability.model_name}")

        psu.output1.voltage = 3.3
        psu.output1.current = 1.0
        psu.output1.enable()

        v = psu.output1.measure_voltage()
        print(f"Output voltage: {v:.3f}V")

        psu.output1.disable()

    # PSU is automatically disconnected here
    print("Automatically disconnected")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Power supply hostname/IP, or 'mock' for the built-in mock PSU (default: mock)")
    parser.add_argument(
        "--all-demos",
        action="store_true",
        help="Also run the multi-output and context-manager demos against a real --host. "
        "These drive output 2 to 12V/1.5A and enable output 3 -- opt in deliberately. "
        "Always on against --host mock.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Power Supply Control Example")
    print("=" * 60)
    basic_output_demo(args.host)

    # Driving outputs 2/3 is opt-in on real hardware: the original gated
    # this behind manual uncommenting.
    if args.host == "mock" or args.all_demos:
        print("\n" + "=" * 60)
        print("Multi-Output Example")
        print("=" * 60)
        multi_output_demo(args.host)

        print("\n" + "=" * 60)
        print("Context Manager Example")
        print("=" * 60)
        context_manager_demo(args.host)
    else:
        print("\nSkipping multi-output and context-manager demos (they drive outputs 2/3). " "Pass --all-demos to run them against real hardware.")


if __name__ == "__main__":
    main()
```

---

## Pulling a screenshot off the instrument's display

Pulling a screenshot off the instrument's display.

### Requirements

- scpi_control - Core library
- None -- runs on the built-in mock; `--host <ip>` for real hardware

### Configuration

None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.

### Usage

```bash
python examples/screen_capture_example.py
```

### Source Code

```python
"""Pulling a screenshot off the instrument's display.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Note: the mock answers SCDP? with a minimal but valid 1x1-pixel BMP (58
bytes), not the instrument's actual framebuffer, so a mock run demonstrates
the transfer and the file write, not a picture worth looking at. It decodes
as a real (if tiny) image -- it is not a fake/placeholder byte string.
Against real hardware the same call returns the scope's actual screen
contents.

Expected output: the byte count printed to the console and 'screenshot.bmp'
written to the current directory. The scope returns BMP, not PNG -- use
ScreenCapture.get_screenshot_pil() (requires Pillow) if you want PNG.
"""

import argparse
import sys

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection
from scpi_control.screen_capture import ScreenCapture
from scpi_control.signal_synth import SignalSpec


def _connect(host):
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True},
        signals={1: SignalSpec(kind="sine", frequency=1000.0, amplitude=1.0)},
        sample_rate=1e6,
        timebase=1e-3,
    )


def main():
    parser = argparse.ArgumentParser(description="Capture the instrument's screen")
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' (default: mock)")
    parser.add_argument("--output", default="screenshot.bmp", help="Where to write the BMP screenshot (default: screenshot.bmp)")
    args = parser.parse_args()

    scope = Oscilloscope(args.host, connection=_connect(args.host))
    scope.connect()
    try:
        camera = ScreenCapture(scope)
        data = camera.capture_screenshot()
        if not data:
            print("No screenshot returned by the instrument.", file=sys.stderr)
            raise SystemExit(1)
        with open(args.output, "wb") as handle:
            handle.write(data)
        print(f"Wrote {len(data)} bytes to {args.output}")
    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()
```

---

## Simple single capture example

Simple single capture example.

### Requirements

- scpi_control - Core library
- None -- runs on the built-in mock; `--host <ip>` for real hardware

### Configuration

None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.

### Usage

```bash
python examples/simple_capture.py
```

### Source Code

```python
"""Simple single capture example.

This example shows how to capture a single waveform from one or more channels
and save it to a file.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Expected output: per-channel capture stats and basic analysis (Vpp, mean,
RMS, frequency) printed to the console, and 'simple_capture.npz' saved to
the current directory.
"""

import argparse

from scpi_control.automation import DataCollector
from scpi_control.connection import MockConnection
from scpi_control.signal_synth import SignalSpec


def _connect(host):
    """Return a mock connection for --host mock, or None to use a real socket."""
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True},
        signals={1: SignalSpec(kind="square", frequency=1000.0, amplitude=1.65, offset=1.65)},
        sample_rate=20e6,
        timebase=500e-6,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' for the built-in mock scope (default: mock)")
    args = parser.parse_args()

    # Create data collector and connect
    collector = DataCollector(args.host, connection=_connect(args.host))
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
            print(f"  Time interval: {(1.0 / waveform.sample_rate) * 1e9:.2f} ns")
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
- None -- runs on the built-in mock; `--host <ip>` for real hardware

### Configuration

None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.

### Usage

```bash
python examples/waveform_capture.py
```

### Source Code

```python
"""Waveform capture example for Siglent oscilloscope.

This script demonstrates how to capture waveform data from
the oscilloscope and save it to a file.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network. matplotlib is a
core dependency, no extra install needed.

Expected output: captures Channel 1, saves 'waveform.csv' and 'waveform.png'
to the current directory, and opens a plot window (a no-op under a
non-interactive matplotlib backend, e.g. in tests).
"""

import argparse

import matplotlib.pyplot as plt

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection
from scpi_control.signal_synth import SignalSpec


def _connect(host):
    """Return a mock connection for --host mock, or None to use a real socket."""
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True},
        signals={1: SignalSpec(kind="square", frequency=1000.0, amplitude=1.65, offset=1.65)},
        sample_rate=20e6,
        timebase=500e-6,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' for the built-in mock scope (default: mock)")
    args = parser.parse_args()

    scope = Oscilloscope(args.host, connection=_connect(args.host))

    try:
        print(f"Connecting to oscilloscope at {args.host}...")
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
        print(f"Timebase: {waveform.timebase*1e6:.3f} us/div")

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
