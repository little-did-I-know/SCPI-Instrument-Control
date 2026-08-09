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
