"""A reply that arrives after we gave up must never answer the next question.

Backend review 2026-07-31, High-7. read() raised SiglentTimeoutError and left
the socket exactly as it found it, so the instrument's late answer stayed
queued and satisfied the NEXT query -- every value after one timeout shifted by
one query. The second source of the same shift: _drain_terminator did a fixed
recv(2) for the "\\n\\n" after a block, so a late second newline stayed behind
and became the ENTIRE next response (read() sees endswith(b"\\n") on the first
chunk and returns an empty string).
"""

from types import SimpleNamespace

import pytest

from scpi_control import exceptions
from scpi_control.connection import socket as socket_module
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
    # Both terminator bytes arrive later, once query 2's own command goes
    # out -- AND as their OWN chunk, separate from the real answer: fix
    # round 2 found that bundling them into the SAME chunk as "7.25\n" let
    # this test pass via data.endswith(b"\n") + str.strip() alone (the
    # answer's own trailing newline satisfies the loop, and .strip() eats
    # the leading "\n\n" for free), with or without the leading-terminator
    # skip this test exists to guard. Keeping the leftover as its own
    # step means read()'s FIRST recv() in this exchange returns ONLY
    # "\n\n" -- which ends with "\n" and would look like a complete (empty)
    # response if the skip didn't force another read past it.
    #
    # AfterSend has to gate the FIRST byte the drain would otherwise see --
    # if a terminator byte were available immediately, the drain's one
    # bounded peek would consume it without ever touching the AfterSend
    # step, and AfterSend only releases for a probe that reaches it BEFORE
    # the send that's supposed to unblock it; a probe that reaches it only
    # afterwards (as query 2's own read() would here) sees the barrier arm
    # and reject in the same instant.
    conn, _ = connected([b"#3012" + b"0123456789ab", AfterSend, b"\n\n", b"7.25\n"], timeout=0.5)
    conn.read_raw(framing=Framing.BLOCK)
    assert conn.query("MEAS:VOLT?") == "7.25"


def test_a_nul_prefix_survives_a_leading_terminator_strip():
    # NUL is a normal response prefix on some instruments; a stray leading
    # terminator arriving in the SAME chunk must not stop it from being
    # stripped too. Regression for fix round 2: an earlier version stripped
    # NUL and terminator bytes in two separate passes, one per loop
    # iteration -- a NUL that only becomes leading AFTER the terminator is
    # stripped never got a second pass, because the very same iteration
    # then broke on endswith(b"\n"), leaving the NUL byte inside the
    # returned response ('\x001.5' instead of '1.5').
    conn, _ = connected([b"\n\x001.5\n"], timeout=0.5)
    assert conn.read() == "1.5"


def test_drain_input_discards_the_queue_without_declaring_the_session_recovered():
    # "Throw away what is queued" and "recover the session" are separate
    # requests. drain_input() answers only the first: the bytes go, and the
    # verdict on whether the session position is known again stays with
    # resync(), which is the verb that may take a protocol-level action.
    conn, _ = connected([b"leftovers"], timeout=0.05)
    conn._desynced = True
    assert conn.drain_input() == len(b"leftovers")
    assert conn._desynced is True


def test_resync_still_clears_the_flag_after_delegating_the_drain():
    conn, _ = connected([b"leftovers"], timeout=0.05)
    conn._desynced = True
    assert conn.resync() == len(b"leftovers")
    assert conn._desynced is False


def test_drain_input_restores_the_read_timeout_it_borrowed():
    conn, fake = connected([b"leftovers"], timeout=0.05)
    fake.settimeout(conn.timeout)
    conn.drain_input()
    assert fake.gettimeout() == conn.timeout


def test_the_terminator_drain_never_eats_real_data():
    # A non-terminator byte after the block belongs to nobody yet: leave it,
    # and mark the session so the next write() clears it.
    conn, _ = connected([b"#3012" + b"0123456789ab", b"XYZ", AfterSend, b"1.5\n"], timeout=0.5)
    conn.read_raw(framing=Framing.BLOCK)
    assert conn._desynced is True
    assert conn.query("MEAS:VOLT?") == "1.5"


def test_surplus_right_behind_the_terminator_run_is_still_seen():
    # The reason _drain_terminator peeks FOUR bytes and not exactly two: with
    # a two-byte peek, "\n\nXYZ" looks like a pure terminator run (the peek is
    # full, so nothing appears to follow it), the surplus is left queued with
    # _desynced unset, and XYZ then poisons the next read with no timeout
    # anywhere to trigger a resync. Peeking past the run is what makes the
    # surplus visible in the same call. The test that already covered the
    # surplus case used "XYZ" with NO terminator ahead of it, which a two-byte
    # peek catches just as well -- which is why this one exists.
    conn, _ = connected([b"#3012" + b"0123456789ab", b"\n\nXYZ", AfterSend, b"1.5\n"], timeout=0.5)
    assert conn.read_raw(framing=Framing.BLOCK) == b"#3012" + b"0123456789ab" + b"\n\n"
    assert conn._desynced is True, "surplus behind a full terminator run must still mark the session"
    assert conn.query("MEAS:VOLT?") == "1.5"


def test_the_loop_timeout_names_the_strays_it_discarded():
    # "(received 0 bytes so far)" was a lie whenever the loop HAD received
    # bytes and discarded them as strays: it describes a silent instrument,
    # sending whoever reads the log after the wrong fault. The loop's own
    # deadline (as opposed to a recv() timeout) is only reachable when reads
    # keep succeeding, so the clock is what has to be scripted here.
    ticks = iter([0.0, 0.0, 99.0])
    conn, _ = connected([b"\n"], timeout=5.0)
    original = socket_module.time
    socket_module.time = SimpleNamespace(time=lambda: next(ticks), sleep=lambda seconds: None)
    try:
        with pytest.raises(exceptions.SiglentTimeoutError) as raised:
            conn.read()
    finally:
        socket_module.time = original
    message = str(raised.value)
    assert "received 0 bytes so far" in message, message
    assert "discarding 1 leading stray byte" in message, message
