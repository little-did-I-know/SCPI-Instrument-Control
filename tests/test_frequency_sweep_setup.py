"""Sweep setup: what it rejects, what it drives, what it puts back."""

import importlib

import pytest

from scpi_control import exceptions
from scpi_control.connection import MockConnection
from scpi_control.frequency_response.sweep import log_spaced_frequencies, sweep
from scpi_control.function_generator import FunctionGenerator
from scpi_control.oscilloscope import Oscilloscope


@pytest.fixture
def rig():
    awg = FunctionGenerator("mock", connection=MockConnection("mock", awg_mode=True))
    awg.connect()
    scope = Oscilloscope("mock", connection=MockConnection("mock", channel_states={1: True, 2: True}, trigger_status=["Stop"], sample_rate=1e6, timebase=1e-3))
    scope.connect()
    yield scope, awg
    scope.disconnect()
    awg.disconnect()


def test_log_spacing_is_inclusive_and_logarithmic():
    frequencies = log_spaced_frequencies(100.0, 10000.0, points_per_decade=2)
    assert frequencies == pytest.approx([100.0, 316.227766, 1000.0, 3162.27766, 10000.0], rel=1e-6)


def test_a_narrow_range_clamps_to_the_endpoints_instead_of_dividing_by_zero():
    # decades = log10(101/100) ~= 0.00432; at 1 point/decade,
    # round(0.00432) == 0, which used to divide by a count of zero and raise
    # ZeroDivisionError instead of returning a legitimate narrow-range answer.
    frequencies = log_spaced_frequencies(100.0, 101.0, points_per_decade=1)
    assert frequencies == pytest.approx([100.0, 101.0])


def test_the_narrow_range_clamp_does_not_disturb_normal_spacing():
    frequencies = log_spaced_frequencies(100.0, 10000.0, points_per_decade=2)
    assert frequencies == pytest.approx([100.0, 316.227766, 1000.0, 3162.27766, 10000.0], rel=1e-6)


@pytest.mark.parametrize(
    "kwargs,message",
    [
        (dict(start_hz=100.0, stop_hz=1000.0, frequencies=[100.0]), "not both"),
        (dict(), "start_hz"),
        (dict(start_hz=1000.0, stop_hz=100.0), "below"),
        (dict(start_hz=0.0, stop_hz=100.0), "positive"),
        (dict(start_hz=100.0, stop_hz=1000.0, amplitude_vpp=0.0), "positive"),
        (dict(start_hz=100.0, stop_hz=1000.0, response_channel=1), "distinct"),
    ],
)
def test_invalid_arguments_are_refused_before_any_wire_traffic(rig, kwargs, message):
    scope, awg = rig
    call = dict(reference_channel=1, response_channel=2)
    call.update(kwargs)
    with pytest.raises(exceptions.InvalidParameterError, match=message):
        sweep(scope, awg, **call)


def test_an_invalid_scope_channel_is_reported_as_an_argument_error_not_a_sweep_failure(rig):
    """InvalidParameterError is a SiglentError; the sweep() try/except that

    re-wraps mid-sweep failures as FrequencySweepError must not catch this
    one. A bad channel number is an argument mistake, not a sweep that
    started and then failed on the wire.
    """
    scope, awg = rig
    with pytest.raises(exceptions.InvalidParameterError, match="no channel 99"):
        sweep(scope, awg, reference_channel=99, response_channel=2, frequencies=[1000.0], settle_s=0.0)


def test_the_awg_is_driven_and_then_restored(rig):
    scope, awg = rig
    output = awg.get_channel(1)
    output.function = "SQUARE"
    output.frequency = 5000.0
    output.amplitude = 0.5
    output.enabled = False

    sweep(scope, awg, reference_channel=1, response_channel=2, frequencies=[1000.0, 2000.0], amplitude_vpp=2.0, settle_s=0.0)

    assert output.function == "SQUARE"
    assert output.frequency == pytest.approx(5000.0)
    assert output.amplitude == pytest.approx(0.5)
    assert output.enabled is False


def test_the_awg_is_restored_even_when_the_sweep_raises(rig, monkeypatch):
    scope, awg = rig
    output = awg.get_channel(1)
    output.enabled = False

    def explode(*args, **kwargs):
        raise exceptions.SiglentTimeoutError("acquisition never completed")

    # A plain string target ("scpi_control.frequency_response.sweep._measure_point")
    # resolves ambiguously as of Task 10: the package's __init__ re-exports the
    # sweep() FUNCTION under the same name as the sweep submodule, so pytest's
    # dotted-path resolution finds that function via getattr on the package
    # before it ever falls back to importing the submodule, and setattr on a
    # function object silently does nothing useful here. importlib.import_module
    # always returns the actual submodule from sys.modules, sidestepping the
    # shadowed package attribute entirely.
    sweep_module = importlib.import_module("scpi_control.frequency_response.sweep")
    monkeypatch.setattr(sweep_module, "_measure_point", explode)

    with pytest.raises(exceptions.FrequencySweepError):
        sweep(scope, awg, reference_channel=1, response_channel=2, frequencies=[1000.0], settle_s=0.0)

    assert output.enabled is False


def test_the_settings_record_what_was_asked_for(rig):
    scope, awg = rig
    result = sweep(scope, awg, reference_channel=1, response_channel=2, frequencies=[1000.0, 2000.0], amplitude_vpp=1.5, settle_s=0.0, autorange=False)
    assert result.settings.frequencies == (1000.0, 2000.0)
    assert result.settings.amplitude_vpp == 1.5
    assert result.settings.autorange is False
