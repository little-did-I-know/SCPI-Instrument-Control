"""Power supply control via USB connection.

This example demonstrates how to connect to a Siglent power supply via USB
using the VISAConnection class.

Requirements:
    pip install "Siglent-Oscilloscope[usb]"

Supports:
    - USB (USB-TMC protocol)
    - GPIB (IEEE-488)
    - Serial (RS-232)
    - TCP/IP (VXI-11 or raw socket)
"""

from siglent import PowerSupply
from siglent.connection import VISAConnection, find_siglent_devices, list_visa_resources


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
        print("  pip install 'Siglent-Oscilloscope[usb]'")
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
        print("\n⚠️  No Siglent devices found")
        print("\nMake sure:")
        print("  1. Device is connected via USB")
        print("  2. USB drivers are installed")
        print("  3. PyVISA is installed: pip install 'Siglent-Oscilloscope[usb]'")
        print("\nFor testing without hardware:")
        print("  - See examples below (commented out)")
        return

    # Step 2: Use the first discovered device
    resource_string, idn = devices[0]
    print(f"\n✓ Using device: {resource_string}")

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
        from siglent.connection import VISAConnection

        main()
    except ImportError:
        print("=" * 60)
        print("PyVISA Not Installed")
        print("=" * 60)
        print("\nUSB support requires PyVISA.")
        print("\nInstall with:")
        print("  pip install 'Siglent-Oscilloscope[usb]'")
        print("\nThis includes:")
        print("  - pyvisa: VISA library interface")
        print("  - pyvisa-py: Pure Python backend (no NI-VISA needed)")
        print("\nAfter installation, run this example again.")
