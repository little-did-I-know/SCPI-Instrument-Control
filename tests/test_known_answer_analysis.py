"""Analysis code checked against signals whose correct answer is known on paper.

Before the chirp/exponential/pulse/multitone kinds existed, these analyzers could
only be pointed at a pure sine, a square, or noise -- none of which has an
interesting closed-form rise time, pulse width, or THD. Every expected value
below is derived analytically and every tolerance is justified by sampling
resolution or a stated systematic effect.

If one of these fails, an analyzer is wrong. Widening a tolerance to make it pass
defeats the entire purpose of the file.
"""

import numpy as np
import pytest

from scpi_control.analysis import FFTAnalyzer
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer
from scpi_control.signal_synth import SignalSpec, make_waveform

RATE = 10_000_000.0  # 0.1 us per sample: fine enough that sampling error is not the dominant term
DT = 1.0 / RATE


def test_rc_step_rise_time_is_tau_times_ln_nine():
    """10%-to-90% of an exponential settles in tau*ln(9) = 2.1972*tau.

    tau is 1/50th of the high phase here, so the plateau reaches amplitude to
    within e**-50 and the only error left is the sampling grid: the analyzer
    walks outward in whole samples, so it can be off by one at each end -- which
    bounds the error at [0, 2*DT), and it measures 1.28*DT here."""
    tau = 1e-5
    waveform = make_waveform(SignalSpec(kind="exponential", frequency=1_000.0, tau=tau), RATE, 20_000)
    stats = WaveformAnalyzer.calculate_timing_stats(waveform)
    assert stats["rise_time"] == pytest.approx(tau * np.log(9.0), abs=2 * DT)


def test_a_barely_settled_rc_reads_low_by_its_plateau_deficit():
    """The same measurement on a signal that does NOT fully settle, pinned to
    the deviation that causes rather than hidden behind a loose tolerance.

    At the default tau (Th/tau = 5) the plateau only reaches 0.9866142981514304
    of amplitude. The analyzer's 10%/90% thresholds are relative to the MEASURED
    range, so they sit at +/-0.7892914385211444 instead of +/-0.8, and the
    measured rise time works out to 2.13909902*tau -- 2.65% below the ideal
    ln(9). Deriving it exactly is what makes this a known-answer test rather
    than a fudge factor:

        v(t) = 1 - 1.9866142981514304 * exp(-t/tau)
        v = -0.7892914385211444 at t = 0.10461213 * tau
        v = +0.7892914385211444 at t = 2.24371116 * tau

    Tolerance is the sampling grid, not slack: DT is tau/1000 here, and the
    analyzer's outward whole-sample walk lands on 2.14*tau, 4.2e-4 relative
    away from the derivation.
    """
    tau = 1e-4
    waveform = make_waveform(SignalSpec(kind="exponential", frequency=1_000.0, tau=tau), RATE, 20_000)
    stats = WaveformAnalyzer.calculate_timing_stats(waveform)
    assert stats["rise_time"] == pytest.approx(2.13910 * tau, rel=1e-3)


def test_pulse_timing_stats_match_the_spec_exactly():
    """A trapezoid's measured values follow from its geometry with no systematic
    error at all: the 50% crossings sit at the ramp midpoints (so the measured
    width IS pulse_width), and 10%-to-90% of a linear ramp is 0.8*edge_time.
    Tolerance is two sample periods of grid error."""
    spec = SignalSpec(kind="pulse", frequency=1_000.0, pulse_width=2e-4, edge_time=1e-5)
    stats = WaveformAnalyzer.calculate_timing_stats(make_waveform(spec, RATE, 20_000))
    assert stats["pulse_width"] == pytest.approx(spec.pulse_width, abs=2 * DT)
    assert stats["rise_time"] == pytest.approx(0.8 * spec.edge_time, abs=2 * DT)
    assert stats["fall_time"] == pytest.approx(0.8 * spec.edge_time, abs=2 * DT)
    assert stats["duty_cycle"] == pytest.approx(spec.pulse_width * spec.frequency * 100.0, abs=0.5)


@pytest.mark.parametrize("harmonics", [(0.1, 0.05), (0.2,), (0.05, 0.05, 0.05)])
def test_multitone_thd_matches_the_harmonic_rss(harmonics):
    """THD is 100*sqrt(sum(h**2)) by construction -- independent of amplitude,
    frequency and phase, because harmonic k rides at k*theta.

    Sampled over a whole number of cycles so the hanning window's leakage stays
    inside the +/-2-bin RSS the analyzer sums over; 2% covers what leaks past it."""
    rate, n, freq = 100_000.0, 100_000, 1_000.0  # 1 s, 1000 whole cycles, 1 Hz bins
    spec = SignalSpec(kind="multitone", frequency=freq, amplitude=2.0, harmonics=harmonics)
    waveform = make_waveform(spec, rate, n)
    expected = 100.0 * np.sqrt(sum(h * h for h in harmonics))
    assert WaveformAnalyzer.calculate_thd(waveform) == pytest.approx(expected, rel=0.02)
    assert FFTAnalyzer.thd_of_waveform(waveform) == pytest.approx(expected, rel=0.02)


def test_a_pure_sine_has_almost_no_thd():
    """The control for the test above: the same code path on a signal whose
    known answer is zero."""
    waveform = make_waveform(SignalSpec(kind="sine", frequency=1_000.0, amplitude=2.0), 100_000.0, 100_000)
    assert WaveformAnalyzer.calculate_thd(waveform) < 0.5


def test_chirp_energy_stays_inside_its_swept_band():
    spec = SignalSpec(kind="chirp", frequency=2_000.0, end_frequency=8_000.0, sweep_time=0.01)
    waveform = make_waveform(spec, 200_000.0, 200_000)  # 1 s = 100 whole sweeps
    peaks = WaveformAnalyzer.calculate_spectrum(waveform)["dominant_peaks"]
    assert peaks
    # The band is the exact sweep, plus one FFT bin. A linear chirp's spectrum
    # is near-rectangular over [frequency, end_frequency] with Fresnel ripple
    # on a scale of sqrt(sweep rate) = sqrt(6 kHz / 10 ms) = 775 Hz. That ripple
    # does spill past each endpoint, but attenuated; its LARGEST maxima -- the
    # Fresnel overshoot -- sit ~0.7*sqrt(rate) INSIDE the band, which is exactly
    # where the top-5 peaks land (2600 Hz and 7400 Hz, 600 Hz inside each end).
    # So nothing wider than the 1 Hz bin (1 s of samples) is derivable, and the
    # +/-10% this test used to allow was undeclared slack.
    bin_hz = waveform.sample_rate / len(waveform.voltage)
    for frequency_hz, _relative in peaks:
        assert spec.frequency - bin_hz <= frequency_hz <= spec.end_frequency + bin_hz
