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


def test_the_default_read_resets_the_stride_to_one():
    # Not "leaves it alone": the interval is instrument state, so a stride left
    # over from the live view would silently decimate an export.
    scope, sent = _recording_scope(idn=MODERN_IDN)
    scope.get_waveform(1, provenance=False)
    assert ":WAVeform:INTerval 1" in sent


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
    """The behavioural version of test_the_default_read_resets_the_stride_to_one
    above: that test only pins the command string. Now that the mock honours
    :WAVeform:INTerval, the actual leak this class's docstring warns about is
    expressible -- a strided read followed by a plain read on the SAME
    connection must return the full record, not the previous stride's
    decimated count.
    """
    conn = MockConnection(idn=MODERN_IDN, sample_rate=20_000.0, timebase=1e-3)
    conn.record_length = 1000
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()

    scope.get_waveform(1, provenance=False, stride=7)
    full = scope.get_waveform(1, provenance=False)

    assert len(full.voltage) == 1000


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
