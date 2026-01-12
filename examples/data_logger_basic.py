"""Basic Data Logger / DAQ example.

This example demonstrates basic usage of the DataLogger class for
data acquisition systems like the Keysight 34970A/DAQ970A.

Requirements:
    - A SCPI-compatible DAQ system (Keysight 34970A, DAQ970A, or similar)
    - Network connection to the instrument
"""

from scpi_control import DataLogger

# Replace with your DAQ's IP address
DAQ_IP = "192.168.1.100"


def basic_measurements():
    """Demonstrate basic voltage measurements."""
    print("=== Basic Voltage Measurements ===\n")

    with DataLogger(DAQ_IP) as daq:
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


def scan_multiple_channels():
    """Demonstrate scanning multiple channels."""
    print("\n=== Multi-Channel Scan ===\n")

    with DataLogger(DAQ_IP) as daq:
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


def continuous_logging():
    """Demonstrate continuous data logging."""
    print("\n=== Continuous Logging (5 seconds) ===\n")

    with DataLogger(DAQ_IP) as daq:
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


def alarm_monitoring():
    """Demonstrate alarm/limit checking."""
    print("\n=== Alarm Monitoring ===\n")

    with DataLogger(DAQ_IP) as daq:
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


def scaling_example():
    """Demonstrate mx+b scaling."""
    print("\n=== Scaling (mx+b) Example ===\n")

    with DataLogger(DAQ_IP) as daq:
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


if __name__ == "__main__":
    print("Data Logger / DAQ Basic Examples")
    print("================================\n")

    try:
        basic_measurements()
        # scan_multiple_channels()
        # continuous_logging()
        # alarm_monitoring()
        # scaling_example()
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure:")
        print(f"  1. Your DAQ is connected at {DAQ_IP}")
        print("  2. The IP address is correct")
        print("  3. No other software is using the connection")
