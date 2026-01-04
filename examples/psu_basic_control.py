"""Basic power supply control example.

This example demonstrates how to control a SCPI power supply using the Siglent package.
Works with both Siglent SPD series and generic SCPI-99 compliant power supplies.

Connection Methods:
    - Ethernet/LAN (this example): PowerSupply('192.168.1.200')
    - USB: See psu_usb_connection.py

For USB support:
    pip install "Siglent-Oscilloscope[usb]"
"""

from siglent import PowerSupply


def main():
    # Connect to power supply (use your PSU's IP address)
    psu = PowerSupply("192.168.1.200")

    print("Connecting to power supply...")
    psu.connect()

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

    # Disconnect
    psu.disconnect()
    print("\nDisconnected from power supply")


def multi_output_example():
    """Example for multi-output power supplies (e.g., SPD3303X)."""

    psu = PowerSupply("192.168.1.200")
    psu.connect()

    if psu.model_capability.num_outputs < 3:
        print("This example requires a 3-output power supply")
        psu.disconnect()
        return

    print(f"Configuring {psu.model_capability.num_outputs} outputs...")

    # Configure different voltages on each output
    psu.output1.voltage = 5.0
    psu.output1.current = 2.0
    psu.output1.enable()

    psu.output2.voltage = 12.0
    psu.output2.current = 1.5
    psu.output2.enable()

    psu.output3.voltage = 3.3
    psu.output3.current = 3.0
    psu.output3.enable()

    # Read all measurements
    for output_num in [1, 2, 3]:
        output = getattr(psu, f"output{output_num}")
        v = output.measure_voltage()
        i = output.measure_current()
        p = output.measure_power()
        print(f"Output {output_num}: {v:.2f}V, {i:.3f}A, {p:.2f}W")

    # Safety: Turn off all outputs
    print("\nTurning off all outputs (safety)...")
    psu.all_outputs_off()

    psu.disconnect()


def context_manager_example():
    """Example using context manager for automatic connection management."""

    # Using 'with' ensures proper connection/disconnection
    with PowerSupply("192.168.1.200") as psu:
        print(f"Connected to {psu.model_capability.model_name}")

        psu.output1.voltage = 3.3
        psu.output1.current = 1.0
        psu.output1.enable()

        v = psu.output1.measure_voltage()
        print(f"Output voltage: {v:.3f}V")

        psu.output1.disable()

    # PSU is automatically disconnected here
    print("Automatically disconnected")


if __name__ == "__main__":
    print("=" * 60)
    print("Power Supply Control Example")
    print("=" * 60)

    # Run basic example
    main()

    print("\n" + "=" * 60)
    print("For multi-output example, uncomment the following line:")
    print("=" * 60)
    # multi_output_example()

    print("\n" + "=" * 60)
    print("Context Manager Example")
    print("=" * 60)
    # context_manager_example()
