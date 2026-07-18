"""Exercise the analyzer against a real capture.

`tests/fixtures/cal_square_sds824x.npz` is a genuine 1 kHz probe-compensation
square wave captured over LAN from a Siglent SDS824X HD (decimated to 20k points
to keep the fixture small). Real hardware data complements the synthetic/mock
signals used elsewhere.

Note: `WaveformAnalyzer.detect_signal_type` currently labels this clean square as
"noise" -- `_is_noise` tests the autocorrelation at a lag of 10% of the record,
which for a multi-period capture is near a half-period, where a square is
strongly anti-correlated. That is a pre-existing heuristic limitation this real
capture exposes; the frequency/amplitude analysis below is unaffected.
"""

from pathlib import Path

import numpy as np

from scpi_control.report_generator.models.report_data import WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer

FIXTURE = Path(__file__).parent / "fixtures" / "cal_square_sds824x.npz"


def _load() -> WaveformData:
    data = np.load(FIXTURE, allow_pickle=True)
    return WaveformData(
        channel=str(data["channel"]),
        time=data["time"].astype("float64"),
        voltage=data["voltage"].astype("float64"),
        sample_rate=float(data["sample_rate"]),
        record_length=int(data["voltage"].size),
    )


def test_fixture_loads_as_a_real_capture():
    wf = _load()
    assert wf.voltage.size == 20000
    assert 3.5e6 < wf.sample_rate < 4.5e6  # ~4 MSa/s (decimated from 20 MSa/s)
    assert wf.channel == "C1"


def test_analyzer_finds_the_1khz_fundamental_on_real_data():
    stats = WaveformAnalyzer.analyze(_load())
    assert abs(stats["frequency"] - 1000.0) < 20.0  # measured 1 kHz cal square


def test_real_capture_amplitude():
    wf = _load()
    vpp = float(wf.voltage.max() - wf.voltage.min())
    assert 3.4 < vpp < 3.8  # measured ~3.62 Vpp
