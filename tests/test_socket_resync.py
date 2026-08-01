"""A reply that arrives after we gave up must never answer the next question.

Backend review 2026-07-31, High-7. read() raised SiglentTimeoutError and left
the socket exactly as it found it, so the instrument's late answer stayed
queued and satisfied the NEXT query -- every value after one timeout shifted by
one query. The second source of the same shift: _drain_terminator did a fixed
recv(2) for the "\\n\\n" after a block, so a late second newline stayed behind
and became the ENTIRE next response (read() sees endswith(b"\\n") on the first
chunk and returns an empty string).
"""

import pytest

from scpi_control import exceptions
from scpi_control.connection.framing import Framing
from tests.fake_socket import AfterSend, Timeout, connected


def test_a_late_reply_does_not_answer_the_next_query():
    # Timeline: query 1 times out; its answer lands afterwards; query 2 must
    # get ITS OWN answer, not the stale one. AfterSend holds "3.301" back until
    # the second command actually goes out -- otherwise the drain would eat it
    # and the test would pass for the wrong reason.
    conn, _ = connected([Timeout, b"STALE_ANSWER\n", AfterSend, b"3.301\n"], timeout=0.05)
    with pytest.raises(exceptions.SiglentTimeoutError):
        conn.query("MEAS:VOLT?")
    assert conn.query("MEAS:CURR?") == "3.301"


def test_the_discarded_bytes_are_reported(caplog):
    conn, _ = connected([Timeout, b"STALE_ANSWER\n", AfterSend, b"3.301\n"], timeout=0.05)
    with pytest.raises(exceptions.SiglentTimeoutError):
        conn.query("MEAS:VOLT?")
    with caplog.at_level("WARNING"):
        conn.query("MEAS:CURR?")
    assert any("MEAS:VOLT?" in record.message for record in caplog.records)
    assert any("Discarded 13 stale" in record.message for record in caplog.records)  # len(b"STALE_ANSWER\n")


def test_timeout_marks_the_session_desynced():
    conn, _ = connected([Timeout], timeout=0.05)
    with pytest.raises(exceptions.SiglentTimeoutError):
        conn.read()
    assert conn._desynced is True


def test_resync_clears_the_flag_and_returns_the_byte_count():
    conn, _ = connected([Timeout, b"leftovers"], timeout=0.05)
    with pytest.raises(exceptions.SiglentTimeoutError):
        conn.read()
    assert conn.resync() == len(b"leftovers")
    assert conn._desynced is False


def test_a_late_second_newline_does_not_become_the_next_response():
    # THE off-by-one: the block's terminator is "\n\n", but NEITHER byte has
    # arrived when the drain runs -- the bounded, single-peek drain (fix
    # round 1: no more looping until timeout, see _drain_terminator) finds
    # nothing queued and gives up immediately rather than blocking for it.
    # Both terminator bytes arrive later, bundled with the real answer, once
    # query 2's own command goes out. AfterSend has to gate the FIRST byte
    # the drain would otherwise see -- if a terminator byte were available
    # immediately, the drain's one bounded peek would consume it without
    # ever touching the AfterSend step, and AfterSend only releases for a
    # probe that reaches it BEFORE the send that's supposed to unblock it;
    # a probe that reaches it only afterwards (as query 2's own read() would
    # here) sees the barrier arm and reject in the same instant. The leftover
    # terminator bytes must not be read as an (empty) answer to that query --
    # read()'s leading-terminator skip is what actually discards them.
    conn, _ = connected([b"#3012" + b"0123456789ab", AfterSend, b"\n\n7.25\n"], timeout=0.5)
    conn.read_raw(framing=Framing.BLOCK)
    assert conn.query("MEAS:VOLT?") == "7.25"


def test_the_terminator_drain_never_eats_real_data():
    # A non-terminator byte after the block belongs to nobody yet: leave it,
    # and mark the session so the next write() clears it.
    conn, _ = connected([b"#3012" + b"0123456789ab", b"XYZ", AfterSend, b"1.5\n"], timeout=0.5)
    conn.read_raw(framing=Framing.BLOCK)
    assert conn._desynced is True
    assert conn.query("MEAS:VOLT?") == "1.5"
