"""Tests for asking the instrument to stride waveform data on the wire.

The gateway's live view renders at most MAX_FRAME_POINTS per frame
(server/adapters.py), but until now the driver always fetched the entire
record and strided it down after the transfer -- on a deep record that is
megabytes crossing the wire to draw two thousand points, holding the
session's single worker thread for the length of the transfer.

`:WAVeform:INTerval` is instrument state, not a per-request argument: if
`stride=None` left the setting untouched, a stride set by the live view
would leak into the next CSV/JSON export on that session and hand someone a
decimated file they believe is complete. So every read sets the interval
explicitly -- including the default path, which resets it to 1.
"""

import logging

import numpy as np
import pytest

from scpi_control import Oscilloscope, exceptions
from scpi_control.connection.mock import MockConnection

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
MODERN_IDN = "Siglent Technologies,SDS814X HD,MOCK0001,1.0.0.0"


def _connected_scope(**kwargs):
    conn = MockConnection("mock", **kwargs)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope


def _recording_scope(**kwargs):
    """A connected scope plus the list of every command it has written.

    MockConnection already records every write it receives (`self.writes`),
    so this just hands that list back alongside the scope -- no separate
    recorder needed.
    """
    conn = MockConnection("mock", **kwargs)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope, conn.writes


def test_a_stride_is_sent_before_the_read():
    scope, sent = _recording_scope(idn=MODERN_IDN)
    scope.get_waveform(1, provenance=False, stride=7)
    assert ":WAVeform:INTerval 7" in sent


def test_stride_is_not_sent_on_a_dialect_without_the_command():
    scope, sent = _recording_scope(idn=LEGACY_IDN)
    scope.get_waveform(1, provenance=False, stride=7)
    assert not any("INTerval" in cmd for cmd in sent)


def test_record_length_query_is_mapped_on_modern():
    scope = _connected_scope(idn=MODERN_IDN, custom_responses={":ACQuire:POINts?": "1400000"})
    assert scope.record_length() == 1400000


def test_the_interval_write_precedes_the_preamble_read():
    # The placement is load-bearing (see waveform_transfer.ModernTransfer.acquire):
    # the preamble must be read back under the interval THIS call asked for, not
    # whatever a previous caller (e.g. the live view) left set on the instrument --
    # otherwise that stride leaks into whatever reads the preamble next. Pinned in
    # the index-comparison style already used by
    # test_modern_waveform_transfer.py::test_preamble_is_read_before_data, so a
    # future reorder fails loudly instead of silently reintroducing the leak.
    scope, sent = _recording_scope(idn=MODERN_IDN)
    scope.get_waveform(1, provenance=False, stride=7)
    sent_upper = [c.upper() for c in sent]
    interval_idx = sent_upper.index(":WAVEFORM:INTERVAL 7")
    preamble_idx = sent_upper.index(":WAVEFORM:PREAMBLE?")
    assert interval_idx < preamble_idx


def test_zero_stride_is_rejected():
    scope = _connected_scope(idn=MODERN_IDN)
    with pytest.raises(exceptions.InvalidParameterError):
        scope.get_waveform(1, provenance=False, stride=0)


def test_negative_stride_is_rejected():
    # int(stride or 1) alone would collapse a negative stride to itself
    # (not to 1) and write it straight onto the wire -- ":WAVeform:INTerval -3"
    # -- unless it is rejected first.
    scope = _connected_scope(idn=MODERN_IDN)
    with pytest.raises(exceptions.InvalidParameterError):
        scope.get_waveform(1, provenance=False, stride=-3)


def test_a_strided_read_returns_the_decimated_point_count_and_scaled_dt():
    """The test that would have caught the mock doing nothing: before the mock
    honored :WAVeform:INTerval, a stride changed no bytes on the wire -- same
    point count back, same dt. This pins both halves of striding actually
    working: fewer points, and a time axis scaled to match.
    """
    conn = MockConnection(idn=MODERN_IDN, sample_rate=20_000.0, timebase=1e-3)
    conn.record_length = 1000
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()

    wf = scope.get_waveform(1, provenance=False, stride=7)

    assert len(wf.voltage) == 143  # ceil(1000 / 7)
    dt = float(np.mean(np.diff(wf.time)))
    assert dt == pytest.approx(7 / 20_000.0)


def test_a_float_stride_is_coerced_to_an_integer_before_being_sent():
    # `effective_stride = stride or 1` alone puts a float straight onto the
    # wire (":WAVeform:INTerval 2.5") -- Task 3's minor asked to reject
    # stride < 1, not to stop coercing to int. Restore the coercion.
    scope, sent = _recording_scope(idn=MODERN_IDN)
    scope.get_waveform(1, provenance=False, stride=2.5)
    assert ":WAVeform:INTerval 2" in sent
    assert not any("2.5" in cmd for cmd in sent)


def test_a_stride_left_over_from_a_prior_read_does_not_leak_into_the_next_one():
    """THE interval-leak guard (Task 7). Pins the actual observable failure
    mode -- not just the wire command -- so it cannot rot: a strided read
    followed by a plain read on the SAME connection must return the full
    record, not the previous stride's decimated count.

    An earlier version of this suite also had
    test_the_default_read_resets_the_stride_to_one, asserting only that
    ":WAVeform:INTerval 1" appeared in the sent commands. It was removed as
    redundant once this test existed: mutation-testing acquire() (making the
    :WAVeform:INTerval write conditional on `stride is not None`, Task 7)
    fails BOTH tests identically, and the command-string assertion is
    strictly weaker -- it would also break on an inconsequential wire-format
    change (e.g. a future dialect spelling the command differently) that
    changes no observable behaviour, which this test would not.

    If you are about to make the interval write in ModernTransfer.acquire()
    (scpi_control/waveform_transfer.py) conditional -- e.g. "only write if it
    differs from the last value" -- this is the test that will fail. Do not
    work around it; the write must stay unconditional (see the comment at
    that write site).
    """
    conn = MockConnection(idn=MODERN_IDN, sample_rate=20_000.0, timebase=1e-3)
    conn.record_length = 1000
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()

    scope.get_waveform(1, provenance=False, stride=7)
    full = scope.get_waveform(1, provenance=False)

    assert len(full.voltage) == 1000


def test_a_data_interval_mismatch_is_logged_once_per_transition_not_every_frame(monkeypatch, caplog):
    """Task 3 added a cross-check in ModernTransfer.acquire (waveform_transfer.py)
    that compares the PREamble's DATA_INTERVAL against the stride we asked
    for, and logs a warning on disagreement. It runs on EVERY acquire(),
    including stride==1 on the export path -- so if real hardware's echo
    disagreed with what this driver reads, the live view would log one
    WARNING per frame, indefinitely, at up to four frames a second.

    Same once-per-transition discipline as the poll-path fix: one WARNING
    when the mismatch starts, one recovery record when it stops, nothing
    while it persists -- and the recovery record must be WARNING too, not a
    quieter level: an operator or alerting pipeline filtering at WARNING (the
    level the onset logs at) must see the disagreement both start AND clear,
    or the log is exactly as ambiguous as it was before this fix for that
    reader. A level-agnostic "a recovery record exists" assertion cannot tell
    that design apart from one that quietly logs recovery at INFO, so this
    pins the level explicitly.
    """
    import scpi_control.waveform_transfer as wt

    scope = _connected_scope(idn=MODERN_IDN)
    real_parse = wt.parse_modern_wavedesc
    mismatch = {"on": True}

    def fake_parse(payload, *, error_context=""):
        meta = dict(real_parse(payload, error_context=error_context))
        if mismatch["on"]:
            meta["data_interval"] = meta["data_interval"] + 1
        return meta

    monkeypatch.setattr(wt, "parse_modern_wavedesc", fake_parse)

    logger_name = "scpi_control.waveform_transfer"
    with caplog.at_level(logging.WARNING, logger=logger_name):
        caplog.clear()
        scope.get_waveform(1, provenance=False)  # mismatch starts
        scope.get_waveform(1, provenance=False)  # steady state: still mismatched

        # Filtered on "DATA_INTERVAL" too, not just level -- an unrelated INFO
        # line ("Acquired N samples...") is logged by the same acquire() on
        # every call and must not be mistaken for the mismatch/recovery record.
        # Onset and recovery are both WARNING now, so they're told apart by
        # message content ("may not be scaled" vs. "cleared"), not level.
        onsets = [r for r in caplog.records if r.name == logger_name and r.levelno == logging.WARNING and "DATA_INTERVAL" in r.getMessage() and "may not be scaled" in r.getMessage()]
        assert len(onsets) == 1, "a persistent mismatch must log once, not once per frame: {0}".format(onsets)
        assert "channel 1" in onsets[0].getMessage()

        mismatch["on"] = False
        scope.get_waveform(1, provenance=False)  # recovers

        recoveries = [r for r in caplog.records if r.name == logger_name and "DATA_INTERVAL" in r.getMessage() and "cleared" in r.getMessage()]
        assert len(recoveries) == 1, "the recovery must log exactly once: {0}".format(recoveries)
        assert recoveries[0].levelno == logging.WARNING, "the recovery record must be WARNING, matching the onset's level"
        assert "channel 1" in recoveries[0].getMessage()

        # Still exactly one onset overall -- the recovery must not be logged
        # as a second onset, and the earlier steady-state mismatch tick must
        # not have logged another onset either.
        onsets_after = [r for r in caplog.records if r.name == logger_name and r.levelno == logging.WARNING and "DATA_INTERVAL" in r.getMessage() and "may not be scaled" in r.getMessage()]
        assert len(onsets_after) == 1


def test_a_stride_needing_more_than_one_window_raises():
    """A strided record that would not fit in a single :WAVeform:DATA?
    transfer must raise rather than mis-assemble: the general chunking loop's
    `start` bookkeeping is only valid in the same (strided) space as
    :WAVeform:STARt when nothing is being decimated (stride == 1) -- see
    ModernTransfer.acquire's else-branch comment.
    """
    conn = MockConnection(idn=MODERN_IDN, sample_rate=20_000.0, timebase=1e-3)
    conn.record_length = 1000
    conn.max_points = 100  # strided count at stride=2 (500) exceeds this
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()

    with pytest.raises(exceptions.FeatureNotSupportedError):
        scope.get_waveform(1, provenance=False, stride=2)
