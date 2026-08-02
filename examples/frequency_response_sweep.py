"""Measure a frequency response: mock AWG -> RC low-pass -> mock scope.

Channel 1 is patched straight to the generator (the reference); channel 2 sees
the same signal through an RCLowPass device model with a 1 kHz corner. The sweep
steps the generator across two decades, autoranges the response channel at every
point, and compares the measured corner against the analytic one.

Everything here runs against mock connections -- no instrument required, and no
claim in the output has been validated against real hardware, because there is
no function generator on the development bench.

Requirements: SCPI-Instrument-Control (core install).
"""

import math

from scpi_control.connection import MockConnection
from scpi_control.connection.mock.loopback import AwgLoopback
from scpi_control.dut import RCLowPass
from scpi_control.frequency_response import sweep
from scpi_control.function_generator import FunctionGenerator
from scpi_control.oscilloscope import Oscilloscope

CUTOFF_HZ = 1000.0


def main() -> None:
    awg_connection = MockConnection("mock", awg_mode=True)
    awg = FunctionGenerator("mock", connection=awg_connection)
    awg.connect()

    scope = Oscilloscope(
        "mock",
        connection=MockConnection(
            "mock",
            channel_states={1: True, 2: True, 3: False, 4: False},
            trigger_status=["Stop"],
            sample_rate=1e6,
            timebase=1e-3,
            signals={
                1: AwgLoopback(awg_connection, awg_channel=1),
                2: AwgLoopback(awg_connection, awg_channel=1, dut=RCLowPass(CUTOFF_HZ)),
            },
        ),
    )
    scope.connect()

    try:
        print(f"Sweeping 100 Hz to 10 kHz through an RC low-pass with a {CUTOFF_HZ:.0f} Hz corner\n")
        print(f"{'frequency':>12} {'gain':>10} {'phase':>10} {'V/div':>8}")

        def show(point):
            if point.gain_db is None:
                print(f"{point.frequency_hz:>10.1f} Hz {'--':>10} {'--':>10}   ({point.excluded_reason})")
            else:
                print(f"{point.frequency_hz:>10.1f} Hz {point.gain_db:>9.2f} dB {point.phase_deg:>8.1f} deg {point.volts_per_div:>7.3f}")

        result = sweep(scope, awg, reference_channel=1, response_channel=2, start_hz=100.0, stop_hz=10000.0, points_per_decade=5, amplitude_vpp=2.0, settle_s=0.0, on_point=show)
    finally:
        scope.disconnect()
        awg.disconnect()

    measured = result.cutoff_hz()
    print(f"\nMeasured -3 dB corner: {measured:.1f} Hz (model: {CUTOFF_HZ:.1f} Hz)")
    print(f"Error: {100 * (measured - CUTOFF_HZ) / CUTOFF_HZ:+.1f}% -- interpolated between points, so it cannot beat the point spacing")

    at_cutoff = min(result.usable(), key=lambda point: abs(point.frequency_hz - CUTOFF_HZ))
    ratio = at_cutoff.frequency_hz / CUTOFF_HZ
    print(f"\nAt {at_cutoff.frequency_hz:.1f} Hz: measured {at_cutoff.gain_db:.3f} dB / {at_cutoff.phase_deg:.2f} deg")
    print(f"{'':>{len(f'At {at_cutoff.frequency_hz:.1f} Hz:')}} analytic {-10 * math.log10(1 + ratio**2):.3f} dB / {-math.degrees(math.atan(ratio)):.2f} deg")

    result.to_csv("frequency_response.csv")
    print("\nWrote frequency_response.csv (metadata header + one row per point)")

    figure = result.plot(title=f"RC low-pass, {CUTOFF_HZ:.0f} Hz corner")
    figure.savefig("frequency_response.png")
    print("Wrote frequency_response.png (Bode plot; excluded points would show as gaps, none here)")


if __name__ == "__main__":
    main()
