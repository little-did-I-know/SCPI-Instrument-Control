"""Exact-frequency tone extraction and point classification."""

import math

import numpy as np
import pytest

from scpi_control.frequency_response.estimate import estimate_point, tone_at
from scpi_control.waveform import WaveformData

SAMPLE_RATE = 1_000_000.0
SAMPLES = 14_000


def _times():
    return np.arange(SAMPLES) / SAMPLE_RATE


def _waveform(volts, channel=1, voltage_scale=0.5, voltage_offset=0.0):
    return WaveformData(time=_times(), voltage=np.asarray(volts, dtype=float), channel=channel, sample_rate=SAMPLE_RATE, voltage_scale=voltage_scale, voltage_offset=voltage_offset, timebase=1e-3)


def test_tone_at_recovers_amplitude_and_phase_between_bins():
    # 1250 Hz over 14 ms is 17.5 cycles: a HALF-BIN offset, the worst case for
    # an implementation that snaps to the nearest FFT bin. Exact evaluation is
    # unaffected; snapping costs ~15% of amplitude and ~90 degrees of phase.
    frequency, amplitude, phase = 1250.0, 1.3, 0.7
    times = _times()
    volts = amplitude * np.cos(2 * np.pi * frequency * times + phase)

    tone = tone_at(volts, times, frequency)

    assert 2 * abs(tone) == pytest.approx(amplitude, rel=1e-3)
    assert math.degrees(np.angle(tone)) == pytest.approx(math.degrees(phase), abs=0.1)


def test_estimate_point_reports_gain_and_phase_difference():
    frequency, gain, phase = 1250.0, 0.5, -0.6
    times = _times()
    reference = _waveform(np.cos(2 * np.pi * frequency * times))
    response = _waveform(gain * np.cos(2 * np.pi * frequency * times + phase), channel=2)

    point = estimate_point(reference, response, frequency)

    assert point.gain_db == pytest.approx(20 * math.log10(gain), abs=0.01)
    assert point.phase_deg == pytest.approx(math.degrees(phase), abs=0.1)
    assert point.excluded_reason is None
    assert point.cycles_in_window == pytest.approx(17.5, rel=0.01)
    assert point.samples_per_cycle == pytest.approx(800.0, rel=0.01)


def test_a_response_at_the_quantization_floor_is_excluded():
    frequency = 1000.0
    times = _times()
    reference = _waveform(np.cos(2 * np.pi * frequency * times))
    # 1 mVpp on a 0.5 V/div scale is 0.002 divisions: under MIN_DIVISIONS.
    response = _waveform(0.0005 * np.cos(2 * np.pi * frequency * times), channel=2)

    point = estimate_point(reference, response, frequency)

    assert point.gain_db is None
    assert point.phase_deg is None
    assert "below vertical resolution" in point.excluded_reason


def test_a_flat_quantized_response_is_excluded_without_a_scale():
    frequency = 1000.0
    times = _times()
    reference = _waveform(np.cos(2 * np.pi * frequency * times))
    # Three distinct values, and no voltage_scale to apply the division rule to.
    response = _waveform(np.round(0.4 * np.cos(2 * np.pi * frequency * times)), channel=2, voltage_scale=None)

    point = estimate_point(reference, response, frequency)

    assert point.gain_db is None
    assert "below vertical resolution" in point.excluded_reason


def test_a_response_beyond_four_divisions_is_excluded():
    frequency = 1000.0
    times = _times()
    reference = _waveform(np.cos(2 * np.pi * frequency * times))
    # +/-1 V on a 0.2 V/div scale is +/-5 divisions: off the screen.
    response = _waveform(np.cos(2 * np.pi * frequency * times), channel=2, voltage_scale=0.2)

    point = estimate_point(reference, response, frequency)

    assert point.gain_db is None
    assert "divisions" in point.excluded_reason


def test_a_clipped_off_screen_response_names_clipping_not_the_floor():
    # A hard square wave at +/-1.0 V on a 0.2 V/div scale is +/-5 divisions:
    # off the screen. It also has exactly 2 distinct values, same as a
    # flat-topped/clipped trace -- which is exactly the combination where a
    # floor-check-before-clip-check ordering misreports "below vertical
    # resolution" for what is actually an overdriven, saturated signal.
    frequency = 1000.0
    times = _times()
    reference = _waveform(np.cos(2 * np.pi * frequency * times))
    half = SAMPLES // 2
    response = _waveform(np.concatenate([np.full(half, 1.0), np.full(SAMPLES - half, -1.0)]), channel=2, voltage_scale=0.2)

    point = estimate_point(reference, response, frequency)

    assert point.gain_db is None
    assert "divisions" in point.excluded_reason
    assert "below vertical resolution" not in point.excluded_reason


def test_a_reference_at_the_floor_names_the_source():
    frequency = 1000.0
    times = _times()
    # 1e-4 Vpp on the default 0.5 V/div scale is 0.0004 divisions: under
    # MIN_DIVISIONS, but genuinely non-zero, so tone_at(reference, ...) is not
    # bit-exact zero. This isolates the _at_floor(reference) branch of
    # _exclusion from the belt-and-braces zero-tone fallback in
    # estimate_point, which a bit-exact-zero reference would also satisfy.
    reference = _waveform(1e-4 * np.cos(2 * np.pi * frequency * times))
    response = _waveform(np.cos(2 * np.pi * frequency * times), channel=2)

    point = estimate_point(reference, response, frequency)

    assert point.gain_db is None
    assert point.excluded_reason == "reference below vertical resolution — source connected?"


def test_an_exactly_zero_reference_is_also_excluded():
    # A bit-exact-zero reference is the degenerate case the belt-and-braces
    # check in estimate_point exists for (dividing by a zero tone would
    # otherwise produce inf rather than an honest exclusion). In practice
    # _at_floor(reference) catches this first -- an all-zero trace collapses
    # to a single distinct value -- so this is kept as its own test to keep
    # that guard covered without conflating it with the floor-message test above.
    frequency = 1000.0
    times = _times()
    reference = _waveform(np.zeros(SAMPLES))
    response = _waveform(np.cos(2 * np.pi * frequency * times), channel=2)

    point = estimate_point(reference, response, frequency)

    assert point.gain_db is None
    assert point.phase_deg is None


def test_a_coarsely_sampled_point_is_kept_but_flagged():
    # 100 kHz at 1 MSa/s is 10 samples per cycle, below MIN_SAMPLES_PER_CYCLE.
    frequency = 100_000.0
    times = _times()
    reference = _waveform(np.cos(2 * np.pi * frequency * times))
    response = _waveform(0.5 * np.cos(2 * np.pi * frequency * times), channel=2)

    point = estimate_point(reference, response, frequency)

    assert point.gain_db is not None
    assert point.samples_per_cycle == pytest.approx(10.0, rel=0.01)
