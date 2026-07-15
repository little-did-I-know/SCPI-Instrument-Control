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
