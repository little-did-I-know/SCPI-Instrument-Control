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
    assert got.channel_name == "C1"  # was 'voltage'
    assert got.sample_rate == pytest.approx(SAMPLE_RATE)  # was a fabricated 1e9
    np.testing.assert_allclose(got.time_data, wf.time)  # was a 0-dim timestamp STRING
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


def test_plain_csv_round_trip(tmp_path):
    """Plain CSV carries no metadata; deriving the rate and synthesizing the
    name is CORRECT behaviour, not a gap. Pin it so nobody 'fixes' it."""
    wf = make_waveform()
    p = tmp_path / "cap.csv"
    saver()._save_csv(wf, str(p), include_metadata=False)

    loaded = WaveformLoader.load(p)

    assert len(loaded) == 1
    got = loaded[0]
    assert got.channel_name == "CH1"  # synthesized: the format cannot carry 'C1'
    assert got.sample_rate == pytest.approx(SAMPLE_RATE, rel=1e-6)  # derived from the time axis
    np.testing.assert_allclose(got.time_data, wf.time)
    np.testing.assert_allclose(got.voltage_data, wf.voltage)


def test_csv_enhanced_loads_at_all(tmp_path):
    """The bug: np.loadtxt(skiprows=1) could not skip the '#' block, so the
    richest CSV variant raised ValueError: could not convert string 'Time (s)'."""
    wf = make_waveform()
    p = tmp_path / "cap_enh.csv"
    saver()._save_csv(wf, str(p), include_metadata=True, metadata={"dut": "board7"})

    loaded = WaveformLoader.load(p)

    assert len(loaded) == 1
    np.testing.assert_allclose(loaded[0].time_data, wf.time)
    np.testing.assert_allclose(loaded[0].voltage_data, wf.voltage)


def test_csv_enhanced_reads_channel_and_rate_from_its_header(tmp_path):
    """CSV_ENHANCED is the one CSV variant that carries them -- read, don't fabricate."""
    wf = make_waveform(channel="C3")
    p = tmp_path / "cap_enh2.csv"
    saver()._save_csv(wf, str(p), include_metadata=True)

    got = WaveformLoader.load(p)[0]

    assert got.channel_name == "C3"
    assert got.sample_rate == pytest.approx(SAMPLE_RATE)


def test_csv_with_legacy_siglent_header_still_loads(tmp_path):
    """Files written before the rename carry '# Siglent Oscilloscope Waveform
    Data'. Comment-skipping is generic, so they must still load."""
    p = tmp_path / "legacy.csv"
    p.write_text(
        "# Siglent Oscilloscope Waveform Data\n"
        "# Captured: 2026-01-01T00:00:00\n"
        "# Channel: C2\n"
        "# Sample Rate: 1000000.0 Sa/s\n"
        "# Samples: 3\n"
        "#\n"
        "Time (s),Voltage (V)\n"
        "0.0,0.0\n"
        "1e-06,0.5\n"
        "2e-06,1.0\n"
    )

    got = WaveformLoader.load(p)[0]

    assert got.channel_name == "C2"
    assert got.sample_rate == pytest.approx(1e6)
    assert len(got.time_data) == 3


def test_single_column_csv_raises_rather_than_returning_nothing(tmp_path):
    """A file with no voltage column must fail loudly, not yield an empty report."""
    p = tmp_path / "one_col.csv"
    p.write_text("Voltage (V)\n0.0\n0.5\n1.0\n")

    with pytest.raises(ValueError):
        WaveformLoader.load(p)


def test_csv_header_with_an_empty_channel_value_falls_back(tmp_path):
    """A malformed '# Channel:' line must not produce an empty channel name."""
    p = tmp_path / "empty_ch.csv"
    p.write_text("# Channel:\n# Sample Rate: 1000000.0 Sa/s\nTime (s),Voltage (V)\n0.0,0.0\n1e-06,0.5\n")

    got = WaveformLoader.load(p)[0]

    assert got.channel_name == "CH1"
    assert got.sample_rate == pytest.approx(1e6)


def test_csv_user_metadata_key_named_channel_cannot_override_the_real_one(tmp_path):
    """The real header always precedes the 'Additional Metadata' block; a user
    metadata key that happens to be named 'Channel' must not win."""
    p = tmp_path / "spoofed_channel.csv"
    p.write_text(
        "# Channel: C2\n"
        "# Sample Rate: 1000000.0 Sa/s\n"
        "#\n"
        "# Additional Metadata:\n"
        "# Channel: NOT-THE-REAL-CHANNEL\n"
        "# Sample Rate: 42.0 Sa/s\n"
        "Time (s),Voltage (V)\n"
        "0.0,0.0\n"
        "1e-06,0.5\n"
    )

    got = WaveformLoader.load(p)[0]

    assert got.channel_name == "C2"
    assert got.sample_rate == pytest.approx(1e6)


def test_hdf5_round_trip_preserves_everything(tmp_path):
    pytest.importorskip("h5py")
    wf = make_waveform()
    p = tmp_path / "cap.h5"
    saver()._save_hdf5(wf, str(p))

    loaded = WaveformLoader.load(p)

    assert len(loaded) == 1
    got = loaded[0]
    assert got.channel_name == "C1"  # was 'voltage'
    assert got.sample_rate == pytest.approx(SAMPLE_RATE)  # was 1e9: read from the wrong attrs
    np.testing.assert_allclose(got.time_data, wf.time)
    np.testing.assert_allclose(got.voltage_data, wf.voltage)


def test_hdf5_with_user_metadata_loads(tmp_path):
    """The bug: the writer adds a 'metadata' GROUP, the loader sliced it ->
    TypeError: Accessing a group is done with bytes or str, not <class 'slice'>."""
    pytest.importorskip("h5py")
    wf = make_waveform()
    p = tmp_path / "cap_meta.h5"
    saver()._save_hdf5(wf, str(p), metadata={"dut": "board7", "operator": "robin"})

    loaded = WaveformLoader.load(p)

    assert len(loaded) == 1
    assert loaded[0].channel_name == "C1"
    np.testing.assert_allclose(loaded[0].voltage_data, wf.voltage)


def test_foreign_hdf5_still_loads_heuristically(tmp_path):
    """A third-party HDF5 has none of our dataset names; best-effort must
    still work, mirroring test_foreign_npz_still_loads_heuristically."""
    h5py = pytest.importorskip("h5py")
    p = tmp_path / "foreign.h5"
    with h5py.File(p, "w") as f:
        f.create_dataset("t_axis", data=np.arange(10) / 1e3)
        f.create_dataset("ch_a", data=np.ones(10))

    loaded = WaveformLoader.load(p)

    assert len(loaded) == 1
    assert len(loaded[0].time_data) == 10


def test_foreign_hdf5_with_a_string_time_dataset_is_rejected_cleanly(tmp_path):
    """A foreign file can use our dataset names without our numeric contract.

    The quasi-schema branch derives sample_rate from the time axis when the attr
    is absent, so a string 'time' dataset must raise our ValueError rather than
    an opaque numpy TypeError -- mirroring the NPZ and MAT string-key tests.
    """
    h5py = pytest.importorskip("h5py")
    p = tmp_path / "stringy.h5"
    with h5py.File(p, "w") as f:
        f.create_dataset("time", data=np.array([b"2026-01-01", b"2026-01-02"]))
        f.create_dataset("voltage", data=np.ones(2))

    with pytest.raises(ValueError):
        WaveformLoader.load(p)


def test_load_multiple_raises_on_a_bad_file(tmp_path):
    """A failed load must not silently become an empty report."""
    good = tmp_path / "good.npz"
    saver()._save_npy(make_waveform(), str(good))
    bad = tmp_path / "bad.npz"
    bad.write_text("not an npz at all")

    with pytest.raises(Exception):
        WaveformLoader.load_multiple([good, bad])


def test_load_multiple_lenient_mode_skips_and_logs(tmp_path, caplog):
    good = tmp_path / "good.npz"
    saver()._save_npy(make_waveform(), str(good))
    bad = tmp_path / "bad.npz"
    bad.write_text("not an npz at all")

    with caplog.at_level("WARNING"):
        loaded = WaveformLoader.load_multiple([good, bad], strict=False)

    assert len(loaded) == 1
    assert any("bad.npz" in r.message for r in caplog.records)


def test_load_multiple_happy_path(tmp_path):
    a = tmp_path / "a.npz"
    b = tmp_path / "b.npz"
    saver()._save_npy(make_waveform(channel="C1"), str(a))
    saver()._save_npy(make_waveform(channel="C2"), str(b))

    loaded = WaveformLoader.load_multiple([a, b])

    assert [w.channel_name for w in loaded] == ["C1", "C2"]
