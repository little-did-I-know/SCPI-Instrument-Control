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
