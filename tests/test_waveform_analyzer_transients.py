"""The transient-detection contract WaveformAnalyzer owes its callers.

detect_transients used to slice its own return to 10 and throw the count away,
so a capture with 400 transients was indistinguishable from one with 10. Any
caller that truncates has to be able to say what it dropped, which means the
analyzer must hand over the true list and let the caller decide. These pin that:
unbounded by default, bounded only on request.

Pure CPU over in-memory arrays -- no instrument, no network.
"""

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
