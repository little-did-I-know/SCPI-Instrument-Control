"""Basic usage example for Siglent oscilloscope control.

This script demonstrates how to connect to an oscilloscope,
configure channels and trigger, and perform basic operations.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Expected output: connection/device info, channel and trigger configuration
echoed to the console, frequency/Vpp measurements on Channel 1, and a summary
of each enabled channel's configuration. No files are written.

Mock limitation: the built-in mock's legacy dialect doesn't implement the
C1:UNIT? query that get_configuration() uses internally, so the final
"Channel Configurations" summary prints nothing when run against the mock
(the per-channel lookup raises and is silently skipped, same as it would be
against real hardware missing that query) -- against a real oscilloscope
this section lists each enabled channel's scale/coupling/offset.
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

    except Exception as e:
        print(f"\nError: {e}")

    finally:
        # Disconnect
        print("\nDisconnecting...")
        scope.disconnect()
        print("Done!")


if __name__ == "__main__":
    main()
