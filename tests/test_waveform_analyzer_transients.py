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


def test_detect_transients_is_unbounded_by_default(bursty_waveform):
    """THE regression test. A silent internal cap here is invisible at this
    call site -- it just quietly reports a noisy signal as a clean one -- so the
    default must return every transient found, however many that is."""
    transients = WaveformAnalyzer.detect_transients(bursty_waveform)

    assert len(transients) > 10, "the default must not truncate"


def test_detect_transients_truncates_to_an_explicit_limit(bursty_waveform):
    transients = WaveformAnalyzer.detect_transients(bursty_waveform, limit=4)

    assert len(transients) == 4


def test_detect_regions_still_appends_at_most_ten_transients(bursty_waveform):
    """detect_regions fed plots and PDFs with a 10-region cap long before the
    limit parameter existed; making the analyzer unbounded must not change what
    it renders.

    Counts transients specifically rather than every region: the fixture is a
    sine, so the default plateau pass contributes nothing today, and a total
    would pin that coincidence instead of the cap.
    """
    WaveformAnalyzer.detect_regions(bursty_waveform, auto_detect_edges=False, auto_detect_transients=True)

    assert len([r for r in bursty_waveform.regions if r.region_type == "transient"]) == 10


def test_detect_edges_survives_an_edge_near_the_end_of_the_record():
    """detect_edges used to index t[len(t)] whenever a detected edge's window
    ran past the last sample -- an IndexError that silently dropped all region
    analysis for that capture.

    window = int(len(t) * 0.02), so it only reaches >= 10 once the record has
    >= 500 samples; below that the old clamp (min(len(t), ...)) never actually
    hit the out-of-bounds case. A 1000-sample record with a step edge at index
    985 puts the derivative peak at idx=984, inside the `idx < len(t) - 10`
    guard (984 < 990) but with idx + window = 984 + 20 = 1004 -- past the last
    valid index (999). This pins the fix: end_idx must clamp to len(t) - 1,
    not len(t).
    """
    n, rate = 1000, 1e6
    t = np.arange(n) / rate
    v = np.zeros(n)
    v[985:] = 5.0  # step edge whose derivative peak lands at idx=984
    waveform = WaveformData(channel="C1", time=t, voltage=v, sample_rate=rate, record_length=n)

    edges = WaveformAnalyzer.detect_edges(waveform)

    assert len(edges) == 1
    edge = edges[0]
    assert edge.region_type == "edge_rising"
    assert np.isfinite(edge.end_time)
    assert t[0] <= edge.end_time <= t[-1]
