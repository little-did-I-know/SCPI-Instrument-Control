"""The transient-detection contract WaveformAnalyzer owes its callers.

detect_transients used to slice its own return to 10 and throw the count away,
so a capture with 400 transients was indistinguishable from one with 10. Any
caller that truncates has to be able to say what it dropped, which means the
analyzer must hand over the true list and let the caller decide. These pin that:
unbounded by default, bounded only on request.

Pure CPU over in-memory arrays -- no instrument, no network.
"""

import numpy as np

from scpi_control.report_generator.models.report_data import WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer


def make_bursty_waveform(channel="C1", n=4000, rate=1e6, freq=10_000, bursts=20, width=6):
    """A sine carrying `bursts` multi-sample spikes.

    The spikes are several samples wide because detect_transients discards any
    region shorter than 0.1% of the capture; single-sample spikes never clear it.
    """
    t = np.arange(n) / rate
    v = np.sin(2 * np.pi * freq * t)
    for start in np.linspace(50, n - 100, bursts).astype(int):
        v[start : start + width] += 8.0
    return WaveformData(channel=channel, time=t, voltage=v, sample_rate=rate, record_length=n)


def test_detect_transients_is_unbounded_by_default():
    """THE regression test. A silent internal cap here is invisible at this
    call site -- it just quietly reports a noisy signal as a clean one -- so the
    default must return every transient found, however many that is."""
    transients = WaveformAnalyzer.detect_transients(make_bursty_waveform())

    assert len(transients) > 10, "the default must not truncate"


def test_detect_transients_truncates_to_an_explicit_limit():
    transients = WaveformAnalyzer.detect_transients(make_bursty_waveform(), limit=4)

    assert len(transients) == 4


def test_detect_regions_still_appends_at_most_ten_transients():
    """detect_regions fed plots and PDFs with a 10-region cap long before the
    limit parameter existed; making the analyzer unbounded must not change what
    it renders."""
    waveform = make_bursty_waveform()

    WaveformAnalyzer.detect_regions(waveform, auto_detect_edges=False, auto_detect_transients=True)

    assert len(waveform.regions) == 10
