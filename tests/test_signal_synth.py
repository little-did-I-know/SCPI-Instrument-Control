"""Public synthetic-signal generators."""

import itertools
import time
from dataclasses import replace

import numpy as np
import pytest

from scpi_control import exceptions
from scpi_control.signal_synth import SignalSpec, SuperposedSignal, make_waveform, make_waveform_combined, stream, synthesize, synthesize_combined


def _dominant_frequency(voltage, sample_rate):
    spectrum = np.abs(np.fft.rfft(voltage - np.mean(voltage)))
    return np.fft.rfftfreq(len(voltage), 1.0 / sample_rate)[np.argmax(spectrum)]


def test_sine_frequency_and_amplitude():
    spec = SignalSpec(kind="sine", frequency=1_000.0, amplitude=2.0)
    v = synthesize(spec, sample_rate=1_000_000.0, n_points=10_000)
    assert v.shape == (10_000,)
    assert np.max(v) == pytest.approx(2.0, abs=0.01)
    assert np.min(v) == pytest.approx(-2.0, abs=0.01)
    assert _dominant_frequency(v, 1_000_000.0) == pytest.approx(1_000.0, rel=0.02)


def test_square_duty_cycle():
    spec = SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0, duty=0.25)
    v = synthesize(spec, sample_rate=1_000_000.0, n_points=10_000)
    high_fraction = np.mean(v > 0)
    assert high_fraction == pytest.approx(0.25, abs=0.02)
    assert set(np.round(np.unique(v), 6)) == {-1.0, 1.0}


def test_triangle_and_ramp_shapes():
    tri = synthesize(SignalSpec(kind="triangle", frequency=100.0, amplitude=1.0), 100_000.0, 5_000)
    ramp = synthesize(SignalSpec(kind="ramp", frequency=100.0, amplitude=1.0), 100_000.0, 5_000)
    assert np.max(tri) == pytest.approx(1.0, abs=0.01)
    assert np.min(tri) == pytest.approx(-1.0, abs=0.01)
    # A ramp resets once per period: exactly ~5 large negative jumps in 5 periods
    jumps = np.sum(np.diff(ramp) < -1.0)
    assert jumps == pytest.approx(5, abs=1)


def test_dc_and_offset():
    v = synthesize(SignalSpec(kind="dc", offset=0.7), 1_000.0, 100)
    np.testing.assert_allclose(v, 0.7)


def test_noise_kind_statistics():
    v = synthesize(SignalSpec(kind="noise", amplitude=0.5, seed=1), 1_000.0, 50_000)
    assert np.std(v) == pytest.approx(0.5, rel=0.05)
    assert np.mean(v) == pytest.approx(0.0, abs=0.02)


def test_noise_rms_rides_on_signal():
    clean = synthesize(SignalSpec(kind="sine", seed=3), 1_000_000.0, 10_000)
    noisy = synthesize(SignalSpec(kind="sine", noise_rms=0.05, seed=3), 1_000_000.0, 10_000)
    assert np.std(noisy - clean) == pytest.approx(0.05, rel=0.1)


def test_seed_reproducibility():
    spec = SignalSpec(kind="sine", noise_rms=0.05, seed=42)
    a = synthesize(spec, 1_000_000.0, 1_000)
    b = synthesize(spec, 1_000_000.0, 1_000)
    np.testing.assert_array_equal(a, b)
    unseeded = SignalSpec(kind="sine", noise_rms=0.05)
    c = synthesize(unseeded, 1_000_000.0, 1_000)
    d = synthesize(unseeded, 1_000_000.0, 1_000)
    assert not np.array_equal(c, d)


def test_t0_shifts_phase():
    spec = SignalSpec(kind="sine", frequency=1_000.0)
    a = synthesize(spec, 1_000_000.0, 1_000, t0=0.0)
    b = synthesize(spec, 1_000_000.0, 1_000, t0=0.25e-3)  # quarter period
    assert not np.allclose(a, b)


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "sawtooth"},
        {"frequency": 0.0},
        {"frequency": -5.0},
        {"kind": "square", "duty": 0.0},
        {"kind": "square", "duty": 1.0},
    ],
)
def test_invalid_spec_raises(bad):
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(SignalSpec(**bad), 1_000.0, 100)


@pytest.mark.parametrize("sample_rate,n_points", [(0.0, 100), (-1.0, 100), (1_000.0, 0)])
def test_invalid_dimensions_raise(sample_rate, n_points):
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(SignalSpec(), sample_rate, n_points)


def test_classifier_smoke():
    """Synthesized signals exercise the report generator's classifier (spec smoke test).

    NOTE: mirror the report-WaveformData construction and expected labels from
    tests/test_signal_type_classification.py (its `_wf` helper) if the kwargs
    below have drifted from that file's current shape.
    """
    from scpi_control.report_generator.models.report_data import WaveformData as ReportWaveform
    from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer

    for kind, expected in (("square", "square"), ("sine", "sine")):
        wf = make_waveform(SignalSpec(kind=kind, frequency=1_000.0, seed=9), sample_rate=1_000_000.0, n_points=20_000)
        report_wf = ReportWaveform(channel="C1", time=wf.time, voltage=wf.voltage, sample_rate=wf.sample_rate, record_length=len(wf.voltage))
        got, _confidence = WaveformAnalyzer.detect_signal_type(report_wf)
        assert got == expected


def test_make_waveform():
    wf = make_waveform(SignalSpec(kind="square", seed=5), sample_rate=100_000.0, n_points=2_000, channel=3)
    assert wf.channel == 3
    assert wf.sample_rate == pytest.approx(100_000.0)
    assert len(wf.time) == len(wf.voltage) == 2_000
    assert wf.time[1] - wf.time[0] == pytest.approx(1e-5)


def test_stream_chunks_are_phase_continuous():
    spec = SignalSpec(kind="sine", frequency=1_000.0)
    joined = np.concatenate(list(stream(spec, 1_000_000.0, 1_000, duration=0.01)))
    expected = synthesize(spec, 1_000_000.0, 10_000)
    assert joined.shape == expected.shape
    np.testing.assert_allclose(joined, expected, rtol=0, atol=1e-9)


def test_stream_duration_yields_partial_final_chunk():
    chunks = list(stream(SignalSpec(seed=1), 10_000.0, 300, duration=0.1))  # 1000 samples
    assert [len(c) for c in chunks] == [300, 300, 300, 100]


def test_stream_exact_chunk_multiple_has_no_empty_tail():
    chunks = list(stream(SignalSpec(seed=1), 10_000.0, 250, duration=0.1))  # 1000 samples
    assert [len(c) for c in chunks] == [250, 250, 250, 250]


def test_stream_infinite_by_default():
    chunks = list(itertools.islice(stream(SignalSpec(seed=1), 10_000.0, 128), 3))
    assert [len(c) for c in chunks] == [128, 128, 128]


def test_stream_seeded_reproducible_and_nonrepeating():
    spec = SignalSpec(kind="noise", amplitude=0.5, seed=42)
    a = list(itertools.islice(stream(spec, 10_000.0, 256), 3))
    b = list(itertools.islice(stream(spec, 10_000.0, 256), 3))
    for x, y in zip(a, b):
        np.testing.assert_array_equal(x, y)  # run-to-run reproducible
    assert not np.array_equal(a[0], a[1])  # non-repeating across chunks


def test_stream_unseeded_noise_differs_per_stream():
    spec = SignalSpec(kind="noise", amplitude=0.5)
    a = next(iter(stream(spec, 10_000.0, 256)))
    b = next(iter(stream(spec, 10_000.0, 256)))
    assert not np.array_equal(a, b)


def test_stream_start_time_offsets_the_signal():
    spec = SignalSpec(kind="sine", frequency=1_000.0)
    first = next(iter(stream(spec, 1_000_000.0, 500, start_time=0.25e-3)))
    np.testing.assert_allclose(first, synthesize(spec, 1_000_000.0, 500, t0=0.25e-3), rtol=0, atol=1e-9)


def test_stream_realtime_paces_chunks():
    started = time.monotonic()
    list(stream(SignalSpec(seed=1), 1_000.0, 50, duration=0.15, realtime=True))  # 3 x 50 ms
    elapsed = time.monotonic() - started
    # Chunk 0 is immediate; chunks 1 and 2 wait until 50 ms and 100 ms.
    assert elapsed >= 0.09


def test_stream_not_realtime_is_fast():
    started = time.monotonic()
    list(stream(SignalSpec(seed=1), 1_000.0, 50, duration=0.15))
    assert time.monotonic() - started < 0.05


def test_stream_validates_at_call_time():
    with pytest.raises(exceptions.InvalidParameterError):
        stream(SignalSpec(), 1_000.0, 0)  # no iteration needed
    with pytest.raises(exceptions.InvalidParameterError):
        stream(SignalSpec(), 1_000.0, 100, duration=-1.0)
    with pytest.raises(exceptions.InvalidParameterError):
        stream(SignalSpec(kind="sawtooth"), 1_000.0, 100)


def test_superposed_dc_components_sum():
    signal = SuperposedSignal((SignalSpec(kind="dc", offset=1.0), SignalSpec(kind="dc", offset=0.5)))
    v = synthesize_combined(signal, 1_000.0, 100)
    np.testing.assert_allclose(v, 1.5)


def test_superposed_noise_reflects_the_noisy_components_variance():
    quiet = SignalSpec(kind="dc", offset=0.0, noise_rms=0.0)
    noisy = SignalSpec(kind="dc", offset=0.0, noise_rms=0.5, seed=1)
    signal = SuperposedSignal((quiet, noisy))
    v = synthesize_combined(signal, 1_000.0, 50_000)
    assert np.std(v) == pytest.approx(0.5, rel=0.05)


def test_superposed_independently_seeded_components_are_reproducible():
    signal = SuperposedSignal(
        (
            SignalSpec(kind="sine", frequency=1_000.0, noise_rms=0.02, seed=5),
            SignalSpec(kind="sine", frequency=3_000.0, noise_rms=0.02, seed=9),
        )
    )
    a = synthesize_combined(signal, 1_000_000.0, 2_000)
    b = synthesize_combined(signal, 1_000_000.0, 2_000)
    np.testing.assert_array_equal(a, b)


def test_superposed_signal_requires_at_least_two_components():
    with pytest.raises(exceptions.InvalidParameterError):
        SuperposedSignal(components=(SignalSpec(),))


def test_make_waveform_combined():
    signal = SuperposedSignal((SignalSpec(kind="dc", offset=1.0), SignalSpec(kind="dc", offset=0.5)))
    wf = make_waveform_combined(signal, sample_rate=100_000.0, n_points=2_000, channel=2)
    assert wf.channel == 2
    assert wf.sample_rate == pytest.approx(100_000.0)
    assert wf.record_length == 2_000
    np.testing.assert_allclose(wf.voltage, 1.5)


def test_clip_level_zero_is_a_true_no_op_regardless_of_softness():
    base = dict(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.05, drift_amplitude=0.1, seed=7)
    unclipped = synthesize(SignalSpec(**base), 1_000_000.0, 5_000)
    off_hard = synthesize(SignalSpec(clip_level=0.0, clip_softness=0.0, **base), 1_000_000.0, 5_000)
    off_soft = synthesize(SignalSpec(clip_level=0.0, clip_softness=1.0, **base), 1_000_000.0, 5_000)
    np.testing.assert_array_equal(unclipped, off_hard)
    np.testing.assert_array_equal(unclipped, off_soft)


def test_hard_clip_flat_tops_the_rail():
    spec = SignalSpec(kind="sine", frequency=100.0, amplitude=2.0, clip_level=1.0, clip_softness=0.0, seed=1)
    v = synthesize(spec, sample_rate=1_000_000.0, n_points=100_000)
    assert np.max(np.abs(v)) == pytest.approx(1.0, abs=1e-9)
    at_rail = np.isclose(v, 1.0, atol=1e-9) | np.isclose(v, -1.0, atol=1e-9)
    # Evidence of genuine flat-topping, not merely a peak touch: many samples
    # pinned to the rail, and specifically several of them consecutive.
    assert at_rail.sum() > 10
    consecutive = np.diff(np.flatnonzero(at_rail))
    assert np.any(consecutive == 1), "no consecutive flat-topped samples found -- not a genuine flat top"


def test_soft_clip_matches_independent_tanh_reconstruction():
    spec_clean = SignalSpec(kind="sine", frequency=100.0, amplitude=2.0, seed=1)
    spec_clipped = SignalSpec(kind="sine", frequency=100.0, amplitude=2.0, clip_level=1.0, clip_softness=1.0, seed=1)
    pre_clip = synthesize(spec_clean, sample_rate=100_000.0, n_points=5_000)
    actual = synthesize(spec_clipped, sample_rate=100_000.0, n_points=5_000)
    expected = 1.0 * np.tanh(pre_clip / 1.0)
    np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)


def test_intermediate_softness_is_the_linear_blend_of_hard_and_soft():
    clip_level = 1.0
    softness = 0.5
    spec_clean = SignalSpec(kind="sine", frequency=100.0, amplitude=2.0, seed=1)
    spec_clipped = SignalSpec(kind="sine", frequency=100.0, amplitude=2.0, clip_level=clip_level, clip_softness=softness, seed=1)
    pre_clip = synthesize(spec_clean, sample_rate=100_000.0, n_points=5_000)
    actual = synthesize(spec_clipped, sample_rate=100_000.0, n_points=5_000)
    u = pre_clip / clip_level
    hard = np.clip(u, -1.0, 1.0)
    soft = np.tanh(u)
    expected = clip_level * ((1.0 - softness) * hard + softness * soft)
    np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)


def test_clipping_applies_after_noise_not_before():
    # A clean DC level that never itself approaches clip_level, but with
    # noise_rms large enough that some noisy samples exceed it -- if clipping
    # were applied to the clean signal BEFORE noise was added, those samples
    # would come out as an unclipped offset+noise value instead of exactly
    # clamped to the rail.
    base = SignalSpec(kind="dc", offset=0.2, noise_rms=0.5, seed=11)
    clipped = SignalSpec(kind="dc", offset=0.2, noise_rms=0.5, clip_level=0.4, clip_softness=0.0, seed=11)
    pre_clip = synthesize(base, 10_000.0, 20_000)
    actual = synthesize(clipped, 10_000.0, 20_000)
    exceeded = np.abs(pre_clip) > 0.4
    assert exceeded.sum() > 0, "test setup didn't actually produce any samples that exceed clip_level"
    np.testing.assert_allclose(actual[exceeded], np.clip(pre_clip[exceeded], -0.4, 0.4), rtol=0, atol=1e-12)
    np.testing.assert_allclose(actual[~exceeded], pre_clip[~exceeded], rtol=0, atol=1e-12)


def test_negative_clip_level_raises():
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(SignalSpec(clip_level=-0.1), 1_000.0, 100)


@pytest.mark.parametrize("bad_softness", [-0.1, 1.1])
def test_clip_softness_out_of_range_raises(bad_softness):
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(SignalSpec(clip_level=1.0, clip_softness=bad_softness), 1_000.0, 100)


def test_clipping_raises_thd_via_odd_harmonic_distortion():
    """The actual point of the feature: clipping is a classic distortion source.

    Compares THD of a clean sine against a hard-clipped version of the SAME
    sine (same seed/frequency/amplitude) via the repo's own canonical THD
    entry point, scpi_control.analysis.FFTAnalyzer.thd_of_waveform.
    """
    from scpi_control.analysis import FFTAnalyzer

    sample_rate = 1_000_000.0
    n_points = 50_000
    clean_spec = SignalSpec(kind="sine", frequency=1_000.0, amplitude=2.0, seed=1)
    clipped_spec = SignalSpec(kind="sine", frequency=1_000.0, amplitude=2.0, clip_level=1.0, clip_softness=0.0, seed=1)

    clean_wf = make_waveform(clean_spec, sample_rate=sample_rate, n_points=n_points)
    clipped_wf = make_waveform(clipped_spec, sample_rate=sample_rate, n_points=n_points)

    thd_clean = FFTAnalyzer.thd_of_waveform(clean_wf)
    thd_clipped = FFTAnalyzer.thd_of_waveform(clipped_wf)

    assert thd_clean is not None
    assert thd_clipped is not None
    assert thd_clipped > thd_clean * 10, f"expected clipping to measurably raise THD: clean={thd_clean!r}%, clipped={thd_clipped!r}%"


def _bin_amplitudes(samples, rate):
    """Single-sided amplitude per FFT bin. Only valid for an integer number of
    cycles in the buffer -- every caller below arranges that -- otherwise leakage
    spreads a tone across neighbouring bins and the ratios stop being exact.
    Mirrors tests/test_signal_kinds.py's identically-named helper."""
    return np.abs(np.fft.rfft(samples)) * 2.0 / len(samples)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"distortion_h2": -0.1},
        {"distortion_h3": -0.1},
        {"distortion_h2": float("nan")},
        {"distortion_h2": float("inf")},
        {"distortion_h3": float("nan")},
        {"distortion_h3": float("inf")},
    ],
)
def test_negative_or_non_finite_distortion_is_rejected(kwargs):
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(SignalSpec(kind="sine", frequency=1_000.0, **kwargs), 1_000_000.0, 1_000)


def test_distortion_with_zero_amplitude_raises_h2():
    # kind="dc" legitimately runs with amplitude=0 (see _dc, which ignores
    # amplitude entirely) -- the guard has to trigger specifically when
    # distortion is ALSO requested, since the waveshaper normalizes by
    # amplitude and would divide by zero.
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(SignalSpec(kind="dc", amplitude=0.0, distortion_h2=0.1), 1_000.0, 100)


def test_distortion_with_zero_amplitude_raises_h3():
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(SignalSpec(kind="dc", amplitude=0.0, distortion_h3=0.1), 1_000.0, 100)


def test_zero_amplitude_without_distortion_is_still_fine():
    # The amplitude==0 guard must not fire when distortion is off -- this is
    # the ordinary, legitimate "dc" use case it must not break.
    v = synthesize(SignalSpec(kind="dc", amplitude=0.0, offset=0.3), 1_000.0, 100)
    np.testing.assert_allclose(v, 0.3)


def test_distortion_h2_alone_produces_a_pure_second_harmonic():
    """The claim the docstring makes about Chebyshev vs. a naive polynomial,
    proven numerically: a pure sinusoid distorted by T_2 alone must show up as
    an isolated 2nd-harmonic bin, with the fundamental unchanged and no
    leakage into DC or the 3rd harmonic. A naive u**2 polynomial would leak
    into DC (sin(theta)**2 == 0.5*(1 - cos(2*theta))), which is exactly what
    this test would catch."""
    rate, n, freq = 100_000.0, 100_000, 1_000.0  # 1 s buffer -> 1 Hz bins, 1000 whole cycles
    amplitude = 2.0
    h2 = 0.3
    spec = SignalSpec(kind="sine", frequency=freq, amplitude=amplitude, distortion_h2=h2, noise_rms=0.0)
    mag = _bin_amplitudes(synthesize(spec, rate, n), rate)
    bin_hz = rate / n
    dc_bin = 0
    fundamental_bin = int(freq / bin_hz)
    second_bin = int(2 * freq / bin_hz)
    third_bin = int(3 * freq / bin_hz)
    assert mag[fundamental_bin] == pytest.approx(amplitude, rel=1e-6)
    assert mag[second_bin] == pytest.approx(h2 * amplitude, rel=1e-6)
    assert mag[dc_bin] < 1e-9
    assert mag[third_bin] < 1e-9


def test_distortion_h3_alone_produces_a_pure_third_harmonic():
    """Mirror of the h2 test above, for T_3 -- see that test's docstring."""
    rate, n, freq = 100_000.0, 100_000, 1_000.0
    amplitude = 2.0
    h3 = 0.3
    spec = SignalSpec(kind="sine", frequency=freq, amplitude=amplitude, distortion_h3=h3, noise_rms=0.0)
    mag = _bin_amplitudes(synthesize(spec, rate, n), rate)
    bin_hz = rate / n
    dc_bin = 0
    fundamental_bin = int(freq / bin_hz)
    second_bin = int(2 * freq / bin_hz)
    third_bin = int(3 * freq / bin_hz)
    assert mag[fundamental_bin] == pytest.approx(amplitude, rel=1e-6)
    assert mag[third_bin] == pytest.approx(h3 * amplitude, rel=1e-6)
    assert mag[dc_bin] < 1e-9
    assert mag[second_bin] < 1e-9


def test_distortion_and_h2_and_h3_together_land_in_separate_bins_additively():
    rate, n, freq = 100_000.0, 100_000, 1_000.0
    amplitude = 2.0
    h2, h3 = 0.2, 0.15
    spec = SignalSpec(kind="sine", frequency=freq, amplitude=amplitude, distortion_h2=h2, distortion_h3=h3, noise_rms=0.0)
    mag = _bin_amplitudes(synthesize(spec, rate, n), rate)
    bin_hz = rate / n
    fundamental_bin = int(freq / bin_hz)
    second_bin = int(2 * freq / bin_hz)
    third_bin = int(3 * freq / bin_hz)
    assert mag[fundamental_bin] == pytest.approx(amplitude, rel=1e-6)
    assert mag[second_bin] == pytest.approx(h2 * amplitude, rel=1e-6)
    assert mag[third_bin] == pytest.approx(h3 * amplitude, rel=1e-6)


def test_distortion_h2_purity_is_unaffected_by_a_nonzero_offset():
    """Regression test: the waveshaper normalizes against (samples - offset),
    NOT raw samples -- offset is a static bias, not part of the oscillating
    carrier the Chebyshev identity is about. Before that fix, a nonzero offset
    leaked into the fundamental bin (2.6 V instead of 2.0 V for this exact
    amplitude/offset/h2 combination, verified by hand) because normalizing
    against the offset-shifted signal pushes u away from cos(theta)."""
    rate, n, freq = 100_000.0, 100_000, 1_000.0
    amplitude, offset, h2 = 2.0, 0.5, 0.3
    spec = SignalSpec(kind="sine", frequency=freq, amplitude=amplitude, offset=offset, distortion_h2=h2, noise_rms=0.0)
    v = synthesize(spec, rate, n)
    mag = _bin_amplitudes(v, rate)
    bin_hz = rate / n
    fundamental_bin = int(freq / bin_hz)
    second_bin = int(2 * freq / bin_hz)
    third_bin = int(3 * freq / bin_hz)
    assert np.mean(v) == pytest.approx(offset, abs=1e-6)
    assert mag[fundamental_bin] == pytest.approx(amplitude, rel=1e-6)
    assert mag[second_bin] == pytest.approx(h2 * amplitude, rel=1e-6)
    assert mag[third_bin] < 1e-9


def test_distortion_h3_alone_with_offset_does_not_leak_into_the_second_harmonic():
    """Mirror of the h2 offset regression test above, for h3 -- this is the
    sharper failure mode: before the fix, distortion_h3 ALONE (h2=0.0) with a
    nonzero offset produced a spurious nonzero 2nd-harmonic bin that should
    not exist at all, not just a magnitude error on a bin already in use."""
    rate, n, freq = 100_000.0, 100_000, 1_000.0
    amplitude, offset, h3 = 2.0, 0.5, 0.3
    spec = SignalSpec(kind="sine", frequency=freq, amplitude=amplitude, offset=offset, distortion_h3=h3, noise_rms=0.0)
    mag = _bin_amplitudes(synthesize(spec, rate, n), rate)
    bin_hz = rate / n
    fundamental_bin = int(freq / bin_hz)
    second_bin = int(2 * freq / bin_hz)
    third_bin = int(3 * freq / bin_hz)
    assert mag[fundamental_bin] == pytest.approx(amplitude, rel=1e-6)
    assert mag[second_bin] < 1e-9
    assert mag[third_bin] == pytest.approx(h3 * amplitude, rel=1e-6)


def test_distortion_is_applied_before_clip_not_after():
    # distortion_h2 pushes a 1.0 V sine well past a 1.0 V clip_level -- if
    # distortion ran AFTER clip, an already-flat-topped +/-1.0 signal fed
    # through the waveshaper would land somewhere else entirely (the
    # waveshaper is not idempotent on a clipped square-ish wave); if it runs
    # BEFORE clip (the documented order), the final output must respect the
    # clip bound exactly, with genuine flat-topping as evidence clipping fired.
    spec = SignalSpec(kind="sine", frequency=100.0, amplitude=1.0, distortion_h2=0.9, clip_level=1.0, clip_softness=0.0, seed=1)
    v = synthesize(spec, sample_rate=1_000_000.0, n_points=100_000)
    assert np.max(np.abs(v)) == pytest.approx(1.0, abs=1e-9)
    at_rail = np.isclose(v, 1.0, atol=1e-9) | np.isclose(v, -1.0, atol=1e-9)
    assert at_rail.sum() > 10, "expected genuine clipping evidence -- distortion must be pushing samples past clip_level for clip to have anything to do"


def test_distortion_default_off_is_bit_identical_to_fields_absent():
    base = dict(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.05, drift_amplitude=0.1, seed=7)
    without_fields = synthesize(SignalSpec(**base), 1_000_000.0, 5_000)
    with_fields_off = synthesize(SignalSpec(distortion_h2=0.0, distortion_h3=0.0, **base), 1_000_000.0, 5_000)
    np.testing.assert_array_equal(without_fields, with_fields_off)


def test_superposed_signal_with_distortion_needs_no_special_casing():
    """synthesize_combined() dispatches each component through synthesize()
    unmodified, so a distorted component should need zero code changes to work
    -- verify that combining a distorted component with a plain one gives
    exactly the elementwise sum of synthesizing each independently, and that
    the distortion itself actually took effect (not silently a no-op)."""
    distorted = SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, distortion_h2=0.25, distortion_h3=0.1, seed=3)
    plain_dc = SignalSpec(kind="dc", offset=0.2)
    signal = SuperposedSignal((distorted, plain_dc))

    combined = synthesize_combined(signal, 1_000_000.0, 10_000)
    expected = synthesize(distorted, 1_000_000.0, 10_000) + synthesize(plain_dc, 1_000_000.0, 10_000)
    np.testing.assert_array_equal(combined, expected)

    undistorted_component = replace(distorted, distortion_h2=0.0, distortion_h3=0.0)
    undistorted_signal = SuperposedSignal((undistorted_component, plain_dc))
    undistorted_combined = synthesize_combined(undistorted_signal, 1_000_000.0, 10_000)
    assert not np.allclose(combined, undistorted_combined), "distortion had no measurable effect inside a SuperposedSignal"
