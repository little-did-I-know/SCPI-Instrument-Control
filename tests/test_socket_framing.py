"""The socket must not read a block header out of payload bytes.

Backend review 2026-07-31, High-6. `_parse_block_total` scanned for `#`
anywhere in the buffer, so a screenshot containing `#3123` was truncated at a
fabricated length and the remainder poisoned the next query.
"""

import pytest

from scpi_control import exceptions
from scpi_control.connection.framing import Framing
from tests.fake_socket import Close, Timeout, connected

# A BMP-shaped payload whose bytes contain something that looks like a header.
POISON = b"BM\x36\x04\x00\x00" + b"\x00" * 4 + b"#3123" + b"\xff" * 40
BLOCK = b"#3012" + b"0123456789ab"


def test_binary_containing_a_hash_is_returned_whole():
    conn, _ = connected([POISON, Timeout])
    assert conn.read_raw() == POISON


def test_a_real_block_still_frames_exactly():
    conn, _ = connected([BLOCK, b"\n\n"])
    assert conn.read_raw().startswith(BLOCK)


def test_block_framing_refuses_a_headerless_reply():
    conn, _ = connected([POISON, Timeout])
    with pytest.raises(exceptions.CommandError):
        conn.read_raw(framing=Framing.BLOCK)


def test_stream_framing_does_not_scan_at_all():
    conn, _ = connected([BLOCK, b"surplus", Timeout])
    assert conn.read_raw(framing=Framing.STREAM) == BLOCK + b"surplus"


def test_peer_close_mid_block_raises_rather_than_returning_short():
    conn, _ = connected([b"#3012" + b"0123", Close])
    with pytest.raises(exceptions.SiglentConnectionError):
        conn.read_raw(framing=Framing.BLOCK)
