"""The frequency response result model."""

import math

import pytest

from scpi_control.frequency_response.model import FrequencyResponse, ResponsePoint, SweepSettings


def _settings(**overrides):
    defaults = dict(reference_channel=1, response_channel=2, awg_channel=1, frequencies=(100.0, 1000.0), amplitude_vpp=2.0, settle_s=0.0, autorange=True)
    defaults.update(overrides)
    return SweepSettings(**defaults)


def _rc_points(cutoff_hz=1000.0, points_per_decade=10, start_hz=100.0, decades=2):
    """Analytic first-order low-pass points -- the shape cutoff_hz() must find."""
    points = []
    for index in range(points_per_decade * decades + 1):
        frequency = start_hz * 10 ** (index / points_per_decade)
        ratio = frequency / cutoff_hz
        points.append(
            ResponsePoint(
                frequency_hz=frequency,
                gain_db=-10 * math.log10(1 + ratio**2),
                phase_deg=-math.degrees(math.atan(ratio)),
                reference_vpp=2.0,
                response_vpp=2.0 / math.sqrt(1 + ratio**2),
                cycles_in_window=14.0,
                samples_per_cycle=1000.0,
                volts_per_div=0.5,
            )
        )
    return points


def test_excluded_reason_is_required_exactly_when_there_is_no_gain():
    with pytest.raises(ValueError):
        ResponsePoint(frequency_hz=100.0, gain_db=None, phase_deg=None)
    with pytest.raises(ValueError):
        ResponsePoint(frequency_hz=100.0, gain_db=-3.0, phase_deg=-45.0, excluded_reason="response clipped")


def test_usable_drops_excluded_points():
    good = _rc_points()[0]
    bad = ResponsePoint(frequency_hz=5000.0, gain_db=None, phase_deg=None, excluded_reason="response below vertical resolution")
    result = FrequencyResponse(settings=_settings(), points=[good, bad])
    assert result.usable() == [good]


def test_cutoff_hz_finds_the_minus_three_db_crossing():
    result = FrequencyResponse(settings=_settings(), points=_rc_points(cutoff_hz=1000.0))
    # Interpolated between decade points, so a few percent of error is inherent.
    assert result.cutoff_hz() == pytest.approx(1000.0, rel=0.05)


def test_cutoff_hz_is_none_when_the_response_never_crosses():
    flat = [
        ResponsePoint(frequency_hz=f, gain_db=-0.1, phase_deg=0.0, reference_vpp=2.0, response_vpp=2.0, cycles_in_window=14.0, samples_per_cycle=1000.0, volts_per_div=0.5)
        for f in (100.0, 200.0, 400.0)
    ]
    assert FrequencyResponse(settings=_settings(), points=flat).cutoff_hz() is None


def _rc_point(frequency_hz, cutoff_hz=1000.0):
    ratio = frequency_hz / cutoff_hz
    return ResponsePoint(
        frequency_hz=frequency_hz,
        gain_db=-10 * math.log10(1 + ratio**2),
        phase_deg=-math.degrees(math.atan(ratio)),
        reference_vpp=2.0,
        response_vpp=2.0 / math.sqrt(1 + ratio**2),
        cycles_in_window=14.0,
        samples_per_cycle=1000.0,
        volts_per_div=0.5,
    )


def test_cutoff_hz_is_order_independent():
    # points/frequencies= is a documented public input with no ordering
    # requirement (the guide invites callers to pass an explicit frequencies=
    # list). Walking self.points in caller-supplied order rather than sorted
    # by frequency answers a different question for an unordered sweep --
    # shuffled and descending must find the SAME crossing as ascending, not
    # a different (or no) one.
    frequencies = [100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0]
    ascending = [_rc_point(f) for f in frequencies]
    shuffled = [_rc_point(f) for f in (100.0, 10000.0, 1000.0, 200.0, 500.0, 2000.0, 5000.0)]
    descending = [_rc_point(f) for f in reversed(frequencies)]

    ascending_cutoff = FrequencyResponse(settings=_settings(), points=ascending).cutoff_hz()
    shuffled_cutoff = FrequencyResponse(settings=_settings(), points=shuffled).cutoff_hz()
    descending_cutoff = FrequencyResponse(settings=_settings(), points=descending).cutoff_hz()

    assert ascending_cutoff is not None
    assert shuffled_cutoff == pytest.approx(ascending_cutoff)
    assert descending_cutoff == pytest.approx(ascending_cutoff)


def test_cutoff_hz_is_none_without_two_usable_points():
    assert FrequencyResponse(settings=_settings(), points=[]).cutoff_hz() is None
