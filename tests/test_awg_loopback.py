"""Mapping a mock AWG's live channel state onto a SignalSpec.

The AWG and the scope are separate MockConnection instances; this object is the
patch cable between them. Everything here is a pure mapping -- the end-to-end
behaviour through a scope session is covered in tests/test_loopback_capture.py.
"""

import math

import pytest

from scpi_control.connection import MockConnection
from scpi_control.connection.mock.loopback import AwgLoopback


def _awg(**overrides):
    conn = MockConnection(awg_mode=True, awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1")
    conn.awg_channels[1].update({"enabled": True})
    conn.awg_channels[1].update(overrides)
    return conn


def test_amplitude_is_halved_because_the_awg_reports_peak_to_peak():
    """The single most likely thing to get silently wrong: SDG `AMP` is Vpp
    (PG02-E05B p.29) while SignalSpec.amplitude is peak, so a missed conversion
    yields a perfectly plausible trace at exactly double amplitude."""
    spec = AwgLoopback(_awg(amplitude=2.0))()
    assert spec.amplitude == pytest.approx(1.0)


def test_phase_is_converted_from_degrees_to_radians():
    spec = AwgLoopback(_awg(phase=90.0))()
    assert spec.phase == pytest.approx(math.pi / 2)


@pytest.mark.parametrize(
    "function,expected_kind",
    [("SINE", "sine"), ("SQUARE", "square"), ("NOISE", "noise"), ("DC", "dc"), ("PULSE", "pulse")],
)
def test_the_function_maps_to_a_kind(function, expected_kind):
    assert AwgLoopback(_awg(function=function))().kind == expected_kind


def test_a_symmetric_ramp_is_a_triangle():
    """A ramp at 50% symmetry IS a triangle; the synth engine models them as
    separate kinds, so the mapping has to choose."""
    assert AwgLoopback(_awg(function="RAMP", ramp_symmetry=50.0))().kind == "triangle"


def test_an_asymmetric_ramp_is_a_sawtooth():
    assert AwgLoopback(_awg(function="RAMP", ramp_symmetry=10.0))().kind == "ramp"


def test_arb_falls_back_to_a_sine_and_says_so(caplog):
    """The mock stores no arbitrary sample data, so ARB cannot be honoured. It
    must degrade visibly rather than silently."""
    import logging

    with caplog.at_level(logging.WARNING, logger="scpi_control.connection.mock.loopback"):
        spec = AwgLoopback(_awg(function="ARB"))()
    assert spec.kind == "sine"
    assert any("ARB" in record.message for record in caplog.records)


def test_a_disabled_output_reads_flat():
    """An output that is off is a disconnected input, not a signal of zero
    amplitude at some frequency."""
    conn = _awg()
    conn.awg_channels[1]["enabled"] = False
    spec = AwgLoopback(conn)()
    assert spec.kind == "dc"
    assert spec.offset == 0.0


def test_frequency_and_offset_pass_through():
    spec = AwgLoopback(_awg(frequency=2_500.0, offset=0.25))()
    assert spec.frequency == pytest.approx(2_500.0)
    assert spec.offset == pytest.approx(0.25)


def test_the_state_is_read_live_not_captured_at_construction():
    """The loopback must see writes that happen after it is wired up."""
    conn = _awg(function="SINE")
    loop = AwgLoopback(conn)
    assert loop().kind == "sine"
    conn.awg_channels[1]["function"] = "SQUARE"
    assert loop().kind == "square"


@pytest.mark.parametrize("duty", [0.0, 100.0])
def test_an_extreme_duty_is_clamped_rather_than_raising(duty):
    """An AWG accepts DUTY,0 and DUTY,100; SignalSpec requires 0 < duty < 1. A
    mock instrument must not explode because a duty was set to an edge value --
    a real one would output something."""
    from scpi_control.signal_synth import synthesize

    spec = AwgLoopback(_awg(function="SQUARE", pulse_duty=duty))()
    synthesize(spec, 1_000_000.0, 1_000)  # must not raise


@pytest.mark.parametrize("duty", [0.0, 100.0])
def test_an_extreme_pulse_duty_is_clamped_rather_than_raising(duty):
    from scpi_control.signal_synth import synthesize

    spec = AwgLoopback(_awg(function="PULSE", pulse_duty=duty))()
    synthesize(spec, 1_000_000.0, 1_000)  # must not raise


def test_a_high_frequency_pulse_still_produces_a_legal_spec():
    """At 1 MHz the period is 1 us, shorter than SignalSpec's default 10 us
    edge_time, so the edge has to shrink with the period or no legal pulse
    width exists."""
    from scpi_control.signal_synth import synthesize

    spec = AwgLoopback(_awg(function="PULSE", frequency=1_000_000.0))()
    synthesize(spec, 100_000_000.0, 1_000)  # must not raise


def test_the_dut_is_carried_but_not_applied_here():
    """The loopback holds the DUT; raw_volts applies it, because only that layer
    knows the sample rate and can render the filter's lead-in."""
    sentinel = object()
    loop = AwgLoopback(_awg(), dut=sentinel)
    assert loop.dut is sentinel


def test_an_unknown_awg_channel_reads_flat():
    assert AwgLoopback(_awg(), awg_channel=99)().kind == "dc"
