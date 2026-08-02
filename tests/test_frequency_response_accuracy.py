"""Accuracy against an analytic first-order low-pass.

Expected values are DERIVED from the RC formula inside the test. Pasting numbers
from a run would pin current behaviour; deriving them pins physics.

Tolerances come from a prototype measured over 21 log-spaced points from 100 Hz
to 10 kHz against RCLowPass(1000) on a 1 MSa/s mock: worst error 0.020 dB and
1.798 degrees. The phase worst case is the top of the range, where the mock's
FIXED sample rate leaves only 100 samples per cycle -- a real scope raises its
sample rate as the timebase shrinks, so the mock is pessimistic here.
"""

import math

import pytest

from scpi_control.connection import MockConnection
from scpi_control.connection.mock.loopback import AwgLoopback
from scpi_control.dut import RCLowPass
from scpi_control.frequency_response.orchestrate import sweep
from scpi_control.function_generator import FunctionGenerator
from scpi_control.oscilloscope import Oscilloscope

CUTOFF_HZ = 1000.0
GAIN_TOLERANCE_DB = 0.1
PHASE_TOLERANCE_DEG = 2.5
TEST_FREQUENCIES = [100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0]


def _analytic(frequency):
    ratio = frequency / CUTOFF_HZ
    return -10 * math.log10(1 + ratio**2), -math.degrees(math.atan(ratio))


def _rig():
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
            signals={1: AwgLoopback(awg_connection, awg_channel=1), 2: AwgLoopback(awg_connection, awg_channel=1, dut=RCLowPass(CUTOFF_HZ))},
        ),
    )
    scope.connect()
    return scope, awg


def _sweep(**overrides):
    scope, awg = _rig()
    try:
        call = dict(reference_channel=1, response_channel=2, frequencies=TEST_FREQUENCIES, amplitude_vpp=2.0, settle_s=0.0)
        call.update(overrides)
        return sweep(scope, awg, **call)
    finally:
        scope.disconnect()
        awg.disconnect()


def test_every_point_matches_the_analytic_rc_response():
    result = _sweep()

    assert len(result.usable()) == len(TEST_FREQUENCIES)
    for point in result.usable():
        expected_gain, expected_phase = _analytic(point.frequency_hz)
        assert point.gain_db == pytest.approx(expected_gain, abs=GAIN_TOLERANCE_DB), f"gain at {point.frequency_hz} Hz"
        assert point.phase_deg == pytest.approx(expected_phase, abs=PHASE_TOLERANCE_DEG), f"phase at {point.frequency_hz} Hz"


def test_the_measured_cutoff_finds_the_rc_corner():
    result = _sweep()
    assert result.cutoff_hz() == pytest.approx(CUTOFF_HZ, rel=0.15)


def test_without_autoranging_the_high_end_is_wrong():
    """The mutation guard for autoranging, run as a real test.

    Held on a fixed 1 V/div scale, the 10 kHz response is a tenth of a division
    and the int8 grid eats it: the measured gain was 0.885 dB off in the
    prototype, far outside GAIN_TOLERANCE_DB. If this ever starts passing,
    autoranging has stopped mattering and the tolerances above are meaningless.
    """
    result = _sweep(frequencies=[10000.0], autorange=False)

    point = result.points[0]
    expected_gain, _ = _analytic(10000.0)
    if point.gain_db is None:
        return  # Excluded outright is also a correct refusal to guess.
    assert abs(point.gain_db - expected_gain) > GAIN_TOLERANCE_DB
