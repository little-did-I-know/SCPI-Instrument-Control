"""Basic Function Generator / AWG Usage Example.

This example demonstrates basic control of Siglent SDG series function generators
using SCPI commands over Ethernet/LAN.

Supported models:
- SDG1000X series (SDG1020, SDG1025, SDG1032X, etc.)
- SDG2000X series (SDG2042X, SDG2082X, SDG2122X, etc.)
- Generic SCPI-compliant arbitrary waveform generators

Requirements:
- Function generator connected to network
- IP address configured on generator
- Default SCPI port: 5024

Usage:
    python function_generator_basic.py --ip 192.168.1.100
"""

import argparse
import logging
import time

from scpi_control import FunctionGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main function to demonstrate AWG control."""
    parser = argparse.ArgumentParser(description="Control Siglent Function Generator")
    parser.add_argument(
        "--ip", type=str, default="192.168.1.100", help="Function generator IP address"
    )
    parser.add_argument(
        "--port", type=int, default=5024, help="SCPI port (default: 5024)"
    )
    args = parser.parse_args()

    logger.info(f"Connecting to function generator at {args.ip}:{args.port}")

    # Using context manager for automatic connection/disconnection
    with FunctionGenerator(args.ip, port=args.port) as awg:
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
        logger.info(
            f"Channel 1 configured manually: {awg.channel1.function}, "
            f"{awg.channel1.frequency}Hz, {awg.channel1.amplitude}Vpp"
        )

        time.sleep(2)

        # Turn off all outputs (safety)
        logger.info("\n=== Turning off all outputs ===")
        awg.all_outputs_off()
        logger.info("All outputs disabled")

    logger.info("\nDisconnected from function generator")


if __name__ == "__main__":
    main()
