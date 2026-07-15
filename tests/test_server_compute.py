"""Pure analysis computations for the poll loop. No FastAPI dependency."""

import numpy as np
import pytest

from scpi_control.server.compute import MAX_SPECTRUM_BINS, empty_spectrum_frame, spectrum_frame
from scpi_control.waveform import WaveformData


def _sine_waveform(freq=50.0, n=4096, rate=1000.0, amplitude=1.0):
    t = np.arange(n) / rate
    return WaveformData(time=t, voltage=amplitude * np.sin(2 * np.pi * freq * t), channel=1)


SPECTRUM_CONFIG = {"enabled": True, "channel": 1, "window": "hanning", "db": True}


class TestSpectrumFrame:
    def test_peak_lands_at_the_sine_frequency(self):
        frame = spectrum_frame(SPECTRUM_CONFIG, {"C1": _sine_waveform()})
        assert frame is not None and frame["type"] == "spectrum"
        df_full = 1000.0 / 4096  # rfftfreq bin width before pooling
        assert abs(frame["peaks"][0][0] - 50.0) <= 2 * df_full
        assert frame["channel"] == 1 and frame["db"] is True and frame["window"] == "hanning"
        assert frame["f0"] == 0.0 and frame["df"] > 0

    def test_points_are_capped_and_pooling_preserves_the_peak(self):
        # n=4096 -> 2049 rfft bins -> pooled by 2; max-pool must keep the exact peak magnitude
        frame = spectrum_frame(SPECTRUM_CONFIG, {"C1": _sine_waveform()})
        assert 0 < len(frame["points"]) <= MAX_SPECTRUM_BINS
        assert max(frame["points"]) == pytest.approx(frame["peaks"][0][1])

    def test_df_scales_with_the_pooling_factor(self):
        frame = spectrum_frame(SPECTRUM_CONFIG, {"C1": _sine_waveform()})
        df_full = 1000.0 / 4096
        assert frame["df"] == pytest.approx(df_full * 2)

    def test_thd_of_a_pure_sine_is_small(self):
        frame = spectrum_frame(SPECTRUM_CONFIG, {"C1": _sine_waveform()})
        assert frame["thd"] is not None and frame["thd"] < 5.0

    def test_long_records_are_truncated_not_fatal(self):
        frame = spectrum_frame(SPECTRUM_CONFIG, {"C1": _sine_waveform(n=200_000)})
        assert frame is not None and 0 < len(frame["points"]) <= MAX_SPECTRUM_BINS

    def test_missing_source_channel_returns_none(self):
        assert spectrum_frame(SPECTRUM_CONFIG, {}) is None

    def test_too_short_waveform_returns_none(self):
        wf = WaveformData(time=np.array([0.0]), voltage=np.array([1.0]), channel=1)
        assert spectrum_frame(SPECTRUM_CONFIG, {"C1": wf}) is None

    def test_empty_frame_shape(self):
        frame = empty_spectrum_frame(SPECTRUM_CONFIG)
        assert frame["type"] == "spectrum" and frame["points"] == [] and frame["peaks"] == [] and frame["thd"] is None
        assert frame["channel"] == 1 and frame["db"] is True and frame["window"] == "hanning"


from scpi_control.server.compute import filtered_waveform, reference_stats


def _two_tone(n=4096, rate=1000.0):
    t = np.arange(n) / rate
    return WaveformData(time=t, voltage=np.sin(2 * np.pi * 10 * t) + np.sin(2 * np.pi * 200 * t), channel=1)


def _filter_config(**overrides):
    config = {"source": 1, "kind": "lowpass", "cutoff_low": None, "cutoff_high": None, "order": 5, "enabled": True}
    config.update(overrides)
    return config


def _tone_magnitude(waveform, freq, rate=1000.0):
    spectrum = np.abs(np.fft.rfft(waveform.voltage))
    bin_index = int(round(freq * len(waveform.voltage) / rate))
    return float(spectrum[bin_index])


class TestFilteredWaveform:
    def test_lowpass_attenuates_the_high_tone(self):
        out = filtered_waveform(_filter_config(cutoff_high=50.0), {"C1": _two_tone()})
        assert out is not None
        assert _tone_magnitude(out, 200) < 0.1 * _tone_magnitude(out, 10)

    def test_highpass_attenuates_the_low_tone(self):
        out = filtered_waveform(_filter_config(kind="highpass", cutoff_low=100.0), {"C1": _two_tone()})
        assert out is not None
        assert _tone_magnitude(out, 10) < 0.1 * _tone_magnitude(out, 200)

    def test_bandpass_needs_both_cutoffs(self):
        assert filtered_waveform(_filter_config(kind="bandpass", cutoff_low=5.0), {"C1": _two_tone()}) is None

    def test_nyquist_violation_returns_none(self):
        # rate 1000 -> Nyquist 500; 600 Hz cutoff is invalid -> library returns None
        assert filtered_waveform(_filter_config(cutoff_high=600.0), {"C1": _two_tone()}) is None

    def test_missing_source_returns_none(self):
        assert filtered_waveform(_filter_config(cutoff_high=50.0), {}) is None

    def test_missing_required_cutoff_returns_none(self):
        assert filtered_waveform(_filter_config(), {"C1": _two_tone()}) is None


class TestReferenceStats:
    def test_identical_trace_correlates_perfectly(self):
        wf = _sine_waveform()
        reference = {"name": "golden", "channel": 1, "data": {"time": wf.time, "voltage": wf.voltage}}
        stats = reference_stats(reference, {"C1": wf})
        assert stats["type"] == "reference_stats"
        assert stats["correlation"] == pytest.approx(1.0)
        assert stats["max_deviation"] == pytest.approx(0.0)

    def test_interpolates_when_lengths_differ(self):
        # Both over the same time span (0 to 4s), different sample densities
        t_live = np.linspace(0, 4.0, 4096)
        v_live = np.sin(2 * np.pi * 50 * t_live)
        live = WaveformData(time=t_live, voltage=v_live, channel=1)

        t_ref = np.linspace(0, 4.0, 1024)
        v_ref = np.sin(2 * np.pi * 50 * t_ref)
        reference = {"name": "golden", "channel": 1, "data": {"time": t_ref, "voltage": v_ref}}
        stats = reference_stats(reference, {"C1": live})
        assert stats["correlation"] is not None and stats["correlation"] > 0.99

    def test_missing_channel_degrades_to_null(self):
        reference = {"name": "golden", "channel": 3, "data": {"time": np.arange(4.0), "voltage": np.ones(4)}}
        stats = reference_stats(reference, {"C1": _sine_waveform()})
        assert stats == {"type": "reference_stats", "correlation": None, "max_deviation": None}

    def test_flat_trace_correlation_is_null_not_nan(self):
        t = np.arange(64) / 1000.0
        flat = WaveformData(time=t, voltage=np.zeros(64), channel=1)
        reference = {"name": "golden", "channel": 1, "data": {"time": t, "voltage": np.zeros(64)}}
        stats = reference_stats(reference, {"C1": flat})
        assert stats["correlation"] is None
        assert stats["max_deviation"] == pytest.approx(0.0)
