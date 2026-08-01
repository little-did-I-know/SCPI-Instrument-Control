"""One acquisition is one compound exchange, so it holds the lock throughout.

Backend review 2026-07-31 (Medium). base.py:23-24: "Callers doing compound
exchanges (write + read_raw) must hold it too." The modern acquire() wrote
source/width/interval OUTSIDE any lock and then took the lock separately for
the preamble and for EACH chunk window -- so a concurrent caller could flip the
source or the interval between two windows of one record, and the halves would
be assembled into a single waveform. The SCDP screenshot held no lock at all
across its write -> sleep -> read.
"""

import threading

from scpi_control.connection.mock import MockConnection
from scpi_control.oscilloscope import Oscilloscope

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
MODERN_IDN = "Siglent Technologies,SDS824X HD,SDS08A0C802019,3.8.12.1.1.3.6"


def _scope(**kwargs):
    conn = MockConnection("mock", idn=MODERN_IDN, channel_states={1: True}, **kwargs)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope, conn


def test_no_other_writer_interleaves_inside_one_acquisition():
    scope, conn = _scope()
    intruder_wrote = threading.Event()
    source_written = threading.Event()

    # A plain "start a thread and hope the scheduler interleaves it" race
    # does not reliably exercise anything here: verified empirically (10/10
    # runs) that the intruder thread wins the GIL immediately after
    # thread.start() and completes its whole write-under-lock before the
    # main thread's acquire() issues its first write, landing entirely
    # BEFORE the acquisition on every run regardless of whether the
    # production code is locked correctly -- a vacuous pass either way.
    #
    # Instead, force a deterministic handshake right after the first
    # (previously unlocked) write in the sequence: the intruder is given a
    # bounded window to run there. Pre-fix, the lock is free at that point,
    # so the intruder acquires it and writes almost instantly. Post-fix, the
    # outer lock is already held by the main thread at that point, so the
    # intruder blocks on conn.lock for the whole window and the wait always
    # times out -- a fixed, known cost, not a hang.
    original_write = conn.write

    def hooked_write(command):
        original_write(command)
        if command.upper() == ":WAVEFORM:SOURCE C1":
            source_written.set()
            intruder_wrote.wait(timeout=0.3)

    conn.write = hooked_write

    def intrude():
        source_written.wait(timeout=5)
        with conn.lock:
            conn.write(":WAVeform:SOURce C4")
            intruder_wrote.set()

    thread = threading.Thread(target=intrude, daemon=True)
    thread.start()
    scope.waveform.acquire(1)
    thread.join(timeout=5)

    # The intruder's write must land entirely before or entirely after the
    # acquisition's own writes -- never between them.
    writes = [w.upper() for w in conn.writes]
    intruder = [i for i, w in enumerate(writes) if w == ":WAVEFORM:SOURCE C4"]
    acquisition = [i for i, w in enumerate(writes) if "PREAMBLE" in w or "DATA?" in w or "SOURCE C1" in w]
    assert intruder_wrote.is_set()
    assert acquisition, f"no acquisition writes observed in {writes}"
    assert all(i < min(acquisition) or i > max(acquisition) for i in intruder), f"a concurrent write landed inside one acquisition: {writes}"


def test_screenshot_holds_the_lock_across_write_and_read():
    # The LEGACY SCDP? path, because the mock actually serves it
    # (mock/base.py:984-988) -- so this asserts on a capture that succeeds,
    # rather than on one that raises for an unrelated reason.
    conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True})
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    observed = []
    original_read_raw = conn.read_raw

    def watched_read_raw(*args, **kwargs):
        observed.append(conn.lock._is_owned())
        return original_read_raw(*args, **kwargs)

    conn.read_raw = watched_read_raw
    assert scope.screen_capture.capture_screenshot()
    assert observed and all(observed), "SCDP read ran without holding the connection lock"
