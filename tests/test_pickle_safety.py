"""A crafted .npz must never execute its payload when loaded (audit H21/M53)."""

import numpy as np
import pytest

from scpi_control.report_generator.utils.waveform_loader import WaveformLoader
from scpi_control.waveform_io import load_waveform

MARKER = []


class _Payload:
    """Pickle that would call a side-effecting function on load."""

    def __reduce__(self):
        return (_touch, ())


def _touch():
    MARKER.append("executed")
    return 0


def _write_malicious_npz(path):
    # The payload must be the object-array element itself (not pre-serialized
    # bytes) -- np.array(pickle.dumps(_Payload()), dtype=object) would pickle
    # a harmless bytes object, never calling _Payload.__reduce__ on load. It
    # must also live under a key the loader actually reads: numpy loads NPZ
    # members lazily, so a key like "evil" that _load_npz never touches never
    # triggers deserialization regardless of allow_pickle. meta_-prefixed
    # keys are read unconditionally, so that's what a real attacker would use.
    with open(path, "wb") as handle:
        np.savez(handle, time=np.arange(4, dtype=float), voltage=np.zeros(4), meta_evil=np.array(_Payload(), dtype=object))


def test_loading_a_pickled_payload_does_not_execute_it(tmp_path):
    MARKER.clear()
    path = tmp_path / "evil.npz"
    _write_malicious_npz(path)
    # numpy raises ValueError ("Object arrays cannot be loaded when
    # allow_pickle=False"). Assert that type, not bare Exception, so an
    # unrelated failure (missing file, bad parse) cannot pass for the fix.
    with pytest.raises(ValueError):
        load_waveform(str(path))
    assert MARKER == [], "pickle payload executed during load"


def test_ordinary_npz_still_round_trips(tmp_path):
    path = tmp_path / "ok.npz"
    np.savez(path, time=np.arange(4, dtype=float), voltage=np.ones(4), channel=np.array(1))
    loaded = load_waveform(str(path))
    assert len(loaded.voltage) == 4


def _write_malicious_npz_for_report_loader(path):
    # report_generator.utils.waveform_loader.WaveformLoader._load_npz is a
    # SEPARATE implementation from waveform_io._load_npz above -- it does not
    # read meta_-prefixed keys at all. It first checks (by key name only,
    # ws.TIME/ws.VOLTAGE/ws.CHANNEL/ws.SAMPLE_RATE) whether the file "looks
    # like ours"; if so it delegates to waveform_io.load_waveform, i.e. the
    # site already covered above. Omitting one of those four keys forces the
    # OTHER branch, _npz_heuristic, which is this loader's own code and is
    # what we need to exercise here.
    #
    # _npz_heuristic builds its voltage-key list with:
    #   [k for k in data.files if k != time_key and np.asarray(data[k])...]
    # That touches data[k] -- triggering deserialization -- for every key
    # other than the chosen time key, unconditionally, before it ever checks
    # whether the key looks like voltage data. So a payload under any
    # non-time key (no meta_ prefix needed) is read on every load attempt.
    with open(path, "wb") as handle:
        np.savez(handle, time=np.arange(4, dtype=float), evil=np.array(_Payload(), dtype=object))


def test_report_loader_does_not_execute_pickle_payload(tmp_path):
    MARKER.clear()
    path = tmp_path / "evil_report.npz"
    _write_malicious_npz_for_report_loader(path)
    with pytest.raises(ValueError):
        WaveformLoader.load(path)
    assert MARKER == [], "pickle payload executed during report-generator load"
