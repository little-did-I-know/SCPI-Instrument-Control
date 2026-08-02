"""The Bode plot: magnitude over phase, log frequency, excluded points shown as gaps."""

import math

import matplotlib

matplotlib.use("Agg")  # No display in CI; must precede any pyplot import.

import matplotlib.pyplot as plt
import pytest

from scpi_control.frequency_response.model import FrequencyResponse, ResponsePoint, SweepSettings


def _result(points):
    settings = SweepSettings(reference_channel=1, response_channel=2, awg_channel=1, frequencies=tuple(p.frequency_hz for p in points), amplitude_vpp=2.0, settle_s=0.0, autorange=True)
    return FrequencyResponse(settings=settings, points=points)


def _rc_point(frequency, cutoff=1000.0):
    ratio = frequency / cutoff
    return ResponsePoint(
        frequency_hz=frequency,
        gain_db=-10 * math.log10(1 + ratio**2),
        phase_deg=-math.degrees(math.atan(ratio)),
        reference_vpp=2.0,
        response_vpp=1.0,
        cycles_in_window=14.0,
        samples_per_cycle=1000.0,
        volts_per_div=0.5,
    )


def test_plot_draws_magnitude_and_phase_on_log_axes():
    result = _result([_rc_point(f) for f in (100.0, 1000.0, 10000.0)])

    figure = result.plot()
    try:
        magnitude, phase = figure.axes
        assert magnitude.get_xscale() == "log"
        assert phase.get_xscale() == "log"
        assert magnitude.lines[0].get_xdata().tolist() == [100.0, 1000.0, 10000.0]
        assert phase.lines[0].get_ydata()[1] == pytest.approx(-45.0, abs=0.1)
    finally:
        plt.close(figure)


def test_plot_shows_a_gap_at_excluded_points():
    # Excluded points must be a real gap in the trace (a NaN, breaking the
    # line and skipping the marker), not silently omitted: omitting the
    # frequency lets semilogx draw one continuous line straight through the
    # excluded region, which is an interpolated claim where no measurement
    # exists.
    points = [_rc_point(100.0), ResponsePoint(frequency_hz=1000.0, gain_db=None, phase_deg=None, excluded_reason="response clipped"), _rc_point(10000.0)]

    figure = _result(points).plot()
    try:
        magnitude, phase = figure.axes
        assert magnitude.lines[0].get_xdata().tolist() == [100.0, 1000.0, 10000.0]
        gains = magnitude.lines[0].get_ydata()
        assert math.isnan(gains[1])
        assert not math.isnan(gains[0])
        assert not math.isnan(gains[2])
        phases = phase.lines[0].get_ydata()
        assert math.isnan(phases[1])
    finally:
        plt.close(figure)


def test_plot_refuses_when_nothing_is_measurable():
    points = [ResponsePoint(frequency_hz=100.0, gain_db=None, phase_deg=None, excluded_reason="response clipped")]

    with pytest.raises(ValueError, match="no usable points"):
        _result(points).plot()
