"""The report loader must read exactly what the library's savers write.

Every test here writes with the real saver and reads with the real loader --
the round-trip nobody had, and the reason four of five formats silently
corrupted data.
"""

import numpy as np
import pytest

from scpi_control.report_generator.utils.waveform_loader import WaveformLoader
from scpi_control.waveform import Waveform, WaveformData

SAMPLE_RATE = 1e6


def make_waveform(channel="C1", n=100):
    """A waveform whose voltages are NOT numerically equal to its time axis.

    (sin(t) ~= t for microsecond-scale t, which would mask a time/voltage mixup.)
    """
    t = np.arange(n) / SAMPLE_RATE
    v = np.sin(2 * np.pi * 10_000 * t)
    return WaveformData(time=t, voltage=v, channel=channel, sample_rate=SAMPLE_RATE, record_length=n)


def saver():
    return object.__new__(Waveform)


def test_npz_round_trip_preserves_everything(tmp_path):
    wf = make_waveform()
    p = tmp_path / "cap.npz"
    saver()._save_npy(wf, str(p))

    loaded = WaveformLoader.load(p)

    assert len(loaded) == 1
    got = loaded[0]
    assert got.channel_name == "C1"                      # was 'voltage'
    assert got.sample_rate == pytest.approx(SAMPLE_RATE)  # was a fabricated 1e9
    np.testing.assert_allclose(got.time_data, wf.time)    # was a 0-dim timestamp STRING
    np.testing.assert_allclose(got.voltage_data, wf.voltage)
    assert got.record_length == 100


def test_npz_timestamp_never_shadows_time(tmp_path):
    """The original bug: 'timestamp' matched `"time" in key` and overwrote `time`."""
    wf = make_waveform()
    p = tmp_path / "cap.npz"
    saver()._save_npy(wf, str(p))

    got = WaveformLoader.load(p)[0]

    assert got.time_data.ndim == 1
    assert len(got.time_data) == 100
    assert not isinstance(got.time_data.dtype.type(), np.str_)


def test_npz_meta_keys_do_not_disturb_the_schema_path(tmp_path):
    """meta_* keys must neither break the schema path nor become phantom
    waveforms -- nothing reads them, so they must be inert."""
    wf = make_waveform()
    p = tmp_path / "cap.npz"
    saver()._save_npy(wf, str(p), metadata={"dut": "board7"})

    got = WaveformLoader.load(p)[0]
    assert got.channel_name == "C1"
    np.testing.assert_allclose(got.time_data, wf.time)


def test_mat_round_trip_preserves_everything(tmp_path):
    pytest.importorskip("scipy")
    wf = make_waveform()
    p = tmp_path / "cap.mat"
    saver()._save_mat(wf, str(p))

    loaded = WaveformLoader.load(p)

    assert len(loaded) == 1, "the channel name must not become a phantom waveform"
    got = loaded[0]
    assert got.channel_name == "C1"
    assert got.sample_rate == pytest.approx(SAMPLE_RATE)
    np.testing.assert_allclose(got.time_data, wf.time)
    np.testing.assert_allclose(got.voltage_data, wf.voltage)


def test_mat_does_not_invent_a_channel_waveform(tmp_path):
    """`key.startswith("ch")` matched 'channel', making array(['C1']) a 'waveform'."""
    pytest.importorskip("scipy")
    p = tmp_path / "cap.mat"
    saver()._save_mat(make_waveform(), str(p))

    for got in WaveformLoader.load(p):
        assert np.issubdtype(got.voltage_data.dtype, np.number)


def test_foreign_npz_still_loads_heuristically(tmp_path):
    """A third-party NPZ has none of our keys; best-effort must still work."""
    p = tmp_path / "foreign.npz"
    np.savez(p, t_axis=np.arange(10) / 1e3, ch_a=np.ones(10))

    loaded = WaveformLoader.load(p)

    assert len(loaded) == 1
    assert len(loaded[0].time_data) == 10


def test_foreign_npz_with_both_time_and_timestamp(tmp_path):
    """The shadowing bug must not come back via the fallback path."""
    p = tmp_path / "foreign2.npz"
    np.savez(p, time=np.arange(10) / 1e3, timestamp="2026-01-01T00:00:00", signal=np.ones(10))

    got = WaveformLoader.load(p)[0]

    assert got.time_data.ndim == 1
    assert len(got.time_data) == 10


def test_foreign_npz_with_our_names_but_no_sample_rate_falls_back(tmp_path):
    """time/voltage/channel but no sample_rate is NOT our schema -- it must
    fall back, not die on KeyError."""
    p = tmp_path / "partial.npz"
    np.savez(p, time=np.arange(10) / 1e3, voltage=np.ones(10), channel="C1")

    loaded = WaveformLoader.load(p)

    assert len(loaded) == 1
    assert len(loaded[0].time_data) == 10


def test_foreign_npz_with_a_string_first_key_is_rejected_cleanly(tmp_path):
    """A string array must never become the time axis via the last-resort branch."""
    p = tmp_path / "stringy.npz"
    np.savez(p, label=np.array(["a", "b", "c"]), signal=np.ones(3))

    with pytest.raises(ValueError):
        WaveformLoader.load(p)


def test_foreign_mat_with_a_string_first_key_is_rejected_cleanly(tmp_path):
    """A string array must never become the time axis on the MAT path either."""
    pytest.importorskip("scipy")
    from scipy.io import savemat

    p = tmp_path / "stringy.mat"
    savemat(str(p), {"label": np.array(["aa", "bb"]), "signal": np.arange(10.0) + 1})

    with pytest.raises(ValueError):
        WaveformLoader.load(p)


def test_foreign_mat_scalar_fields_do_not_become_waveforms(tmp_path):
    """A scalar like sample_rate must not flatten into a 1-sample 'waveform'."""
    pytest.importorskip("scipy")
    from scipy.io import savemat

    p = tmp_path / "foreign.mat"
    savemat(str(p), {"time": np.arange(10) / 1e3, "voltage": np.ones(10), "sample_rate": 1e3})

    loaded = WaveformLoader.load(p)

    assert len(loaded) == 1
    assert loaded[0].record_length == 10
