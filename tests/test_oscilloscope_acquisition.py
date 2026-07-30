"""Tests for Oscilloscope.new_acquisition_ready() -- the cheap "has a new frame
landed?" gate the live-view poll loop asks before fetching a waveform.

Against a real Siglent SDS824X HD at a long timebase, polling on a timer alone
means the poll loop asks roughly six times faster than the instrument can
produce a frame; the read blocks for the rest of the acquisition and, because
the session's single worker thread also services user commands, every control
in the web UI hangs for the length of the capture. new_acquisition_ready() is
the cheap question asked first, before paying for that blocking read.
"""

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection


def _connected_scope(**kwargs):
    conn = MockConnection("mock", **kwargs)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope


def test_new_acquisition_ready_is_none_when_the_dialect_cannot_tell():
    # The tri-state is the whole design: None means "no gate available", and the
    # adapter falls back to timing rather than guessing a vendor's semantics.
    scope = _connected_scope(idn="Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0")
    assert scope.new_acquisition_ready() is None


def test_new_acquisition_ready_reads_bit_zero_of_inr():
    # The manual's own example (SDS800XHD guide p.829) polls INR? and tests
    # state & 0x01 for "Acquisition finished".
    scope = _connected_scope(
        idn="Siglent Technologies,SDS824X HD,SDS08A0X804831,3.8.12.1.1.3.6",
        custom_responses={"INR?": ["0", "1", "2", "3"]},
    )
    assert scope.new_acquisition_ready() is False  # 0 -> no new data
    assert scope.new_acquisition_ready() is True  # 1 -> bit 0 set
    assert scope.new_acquisition_ready() is False  # 2 -> other bit only
    assert scope.new_acquisition_ready() is True  # 3 -> bit 0 set among others


def test_new_acquisition_ready_is_none_when_the_query_fails():
    # A failed gate must degrade to "cannot tell" for this tick, not raise into
    # the poll loop and kill the session.
    scope = _connected_scope(
        idn="Siglent Technologies,SDS824X HD,SDS08A0X804831,3.8.12.1.1.3.6",
        custom_responses={"INR?": "not-a-number"},
    )
    assert scope.new_acquisition_ready() is None


MODERN_IDN = "Siglent Technologies,SDS824X HD,SDS08A0X804831,3.8.12.1.1.3.6"


def test_the_gate_parses_the_header_prefixed_reply_hardware_actually_sends():
    """MEASURED on the real SDS824X HD (fw 3.8.12.1.1.3.6), 2026-07-30: INR?
    answers "INR 8193" / "INR 8192" / "INR 0" -- HEADER-PREFIXED, not the bare
    integer every test above injects. Only the ":"-prefixed modern queries
    answer bare; legacy-style ones like INR? carry the header.

    int("INR 8193") raises ValueError, which new_acquisition_ready() catches
    and turns into None = "this dialect has no gate". Silently, every tick,
    with no log -- so the modern new-acquisition gate never ran on the
    instrument at all and the poll fell back to timing-based backoff. That is
    the entire feature this module's docstring describes.

    8193 = 8192 + 1: bit 0 (new signal acquired) set alongside an unrelated
    bit 13, which is exactly why the mask matters and a bare equality would
    not do.
    """
    scope = _connected_scope(
        idn=MODERN_IDN,
        custom_responses={"INR?": ["INR 8193", "INR 8192", "INR 0", "INR 1"]},
    )
    assert scope.new_acquisition_ready() is True   # 8193 -> bit 0 set
    assert scope.new_acquisition_ready() is False  # 8192 -> bit 13 only
    assert scope.new_acquisition_ready() is False  # 0 -> nothing latched
    assert scope.new_acquisition_ready() is True   # 1 -> bit 0 set


def test_the_modern_mock_answers_inr_the_way_the_instrument_does():
    """The gap that let this ship: the modern mock had NO INR? handler at all,
    so the query raised and the gate degraded to None in CI too. Every test
    that exercised the gate injected a bare "1"/"0" through custom_responses
    -- a shape the instrument never sends. With no unpatched test ever asking
    the mock for INR?, nothing could notice.
    """
    scope = _connected_scope(idn=MODERN_IDN)

    reply = scope._connection.query("INR?")

    assert reply.upper().startswith("INR"), (
        "the mock must reproduce the instrument's header prefix, or it re-hides the bug: {0!r}".format(reply)
    )
    assert scope.new_acquisition_ready() in (True, False), "the gate must resolve against the unpatched mock"
