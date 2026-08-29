"""Public synthetic-signal generators."""

import itertools
import time

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
