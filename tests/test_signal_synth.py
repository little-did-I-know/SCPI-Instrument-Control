"""Public synthetic-signal generators."""

import numpy as np
import pytest

from scpi_control import exceptions
from scpi_control.signal_synth import SignalSpec, make_waveform, synthesize


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
