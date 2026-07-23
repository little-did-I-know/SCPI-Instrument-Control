"""MockConnection.read_raw honors size and the screenshot contract (audit M10).

A real instrument's read_raw(size) returns at most `size` bytes; the mock used
to ignore `size` entirely and always hand back the full payload regardless of
what was asked for. This matters for the lab-gateway server's screenshot path
and any chunked transfer.
"""

from scpi_control.connection.mock import MockConnection


def test_read_raw_respects_size_limit_on_waveform_branch():
    conn = MockConnection()
    conn.connect()

    # Establish that the natural (untruncated) payload is longer than the
    # size we are about to request, so the size=8 assertion below actually
    # exercises truncation instead of coincidentally passing.
    conn.write("C1:WF? DAT2")
    full = conn.read_raw()
    assert len(full) > 8, "test assumes the natural waveform payload exceeds 8 bytes"

    conn.write("C1:WF? DAT2")
    truncated = conn.read_raw(size=8)
    assert len(truncated) <= 8


def test_read_raw_returns_full_screenshot_block_when_size_is_none():
    conn = MockConnection()
    conn.connect()
    conn.write("SCDP?")

    block = conn.read_raw()
    assert block.startswith(b"#"), "IEEE 488.2 block header"


def test_read_raw_respects_size_limit_on_screenshot_branch():
    conn = MockConnection()
    conn.connect()

    conn.write("SCDP?")
    full = conn.read_raw()
    assert len(full) > 4, "test assumes the screenshot block exceeds 4 bytes"

    conn.write("SCDP?")
    truncated = conn.read_raw(size=4)
    assert len(truncated) <= 4
