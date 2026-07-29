"""A waveform-data read that can block on demand.

No existing test can reproduce the defect this sub-project fixes: the mock
answers a waveform query instantly, so a poll tick is free and the session's
single worker thread never contends between the scope poll and a user
command. `MockConnection(waveform_gate=...)` is the test double that makes
this reproducible -- a waveform-data read blocks until the test releases the
gate, deterministically and without sleeping.

The real entry point for a waveform-data read is `write()` followed by
`read_raw()` (see waveform_transfer.py's SiglentTransfer.acquire, which holds
the connection lock across exactly this pair). There is no `query_binary` on
MockConnection -- that name only exists on VisaConnection/SocketConnection --
so the gate is proven here against the actual pair the driver uses, with the
legacy dialect's own waveform query string ("C1:WF? DAT2", scpi_commands.py's
"get_waveform" mapping for the default Siglent dialect).
"""

import threading

from scpi_control.connection.mock import MockConnection


def test_the_waveform_gate_blocks_until_released():
    gate = threading.Event()
    conn = MockConnection(waveform_gate=gate)
    conn.connect()
    done = threading.Event()

    def read():
        conn.write("C1:WF? DAT2")
        conn.read_raw()
        done.set()

    worker = threading.Thread(target=read, daemon=True)
    worker.start()
    try:
        assert not done.wait(timeout=0.2), "the read returned without the gate being released"
    finally:
        # Always release the gate, even if the assertion above fails, so a
        # broken gate cannot leave the worker thread blocked forever.
        gate.set()
    assert done.wait(timeout=2.0), "the read did not return after the gate was released"
    worker.join(timeout=2.0)
    assert not worker.is_alive(), "worker thread did not exit after the read returned"


def test_no_gate_means_no_blocking():
    # Every existing test constructs MockConnection without a gate and must be
    # completely unaffected.
    conn = MockConnection()
    conn.connect()
    conn.write("C1:WF? DAT2")
    conn.read_raw()
