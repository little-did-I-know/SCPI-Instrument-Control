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
measurements, a 3-output walkthrough (CH3 is the SPD3303X's fixed
auxiliary rail -- see the comments in multi_output_demo() for what it does
and doesn't support), and a context-manager demo, all echoed to the
console. No files are written.
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
    args = parser.parse_args()

    print("=" * 60)
    print("Power Supply Control Example")
    print("=" * 60)
    basic_output_demo(args.host)

    print("\n" + "=" * 60)
    print("Multi-Output Example")
    print("=" * 60)
    multi_output_demo(args.host)

    print("\n" + "=" * 60)
    print("Context Manager Example")
    print("=" * 60)
    context_manager_demo(args.host)


if __name__ == "__main__":
    main()
