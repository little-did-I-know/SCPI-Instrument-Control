"""Reference lookup must not escape the storage directory (audit H21)."""

import numpy as np

from scpi_control.reference_waveform import ReferenceWaveform


def test_absolute_path_is_not_honoured(tmp_path):
    outside = tmp_path / "outside.npz"
    np.savez_compressed(outside, time=np.arange(4, dtype=float), voltage=np.zeros(4))
    store = ReferenceWaveform(str(tmp_path / "refs"))
    assert store.load_reference(str(outside)) is None


def test_traversal_is_not_honoured(tmp_path):
    outside = tmp_path / "outside.npz"
    np.savez_compressed(outside, time=np.arange(4, dtype=float), voltage=np.zeros(4))
    store = ReferenceWaveform(str(tmp_path / "refs"))
    assert store.load_reference("../outside.npz") is None
    assert store.load_reference("..\\outside.npz") is None


def test_ordinary_name_still_resolves(tmp_path):
    class _Waveform:
        time = np.linspace(0, 1, 8)
        voltage = np.zeros(8)
        channel = 1

    store = ReferenceWaveform(str(tmp_path))
    store.save_reference(_Waveform(), "base")
    assert store.load_reference("base") is not None
