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

from scpi_control import Oscilloscope
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
