"""Framing must be decided by the caller, and never guessed from binary bytes.

Backend review 2026-07-31, finding High-6. `_parse_block_total` located a
definite-length block with `data.find(b"#")` -- anywhere in the buffer, over
binary content -- so a screenshot containing `#3123` was read as a header:
the read stopped at a fabricated length, the caller got a truncated image, and
the remainder poisoned the next query (the reviewer's repro returned image-tail
bytes from *IDN?).

This module has no I/O: the reader is driven by an injected read_chunk(n), so
every case here is a list of byte strings.
"""

import pytest

from scpi_control import exceptions
from scpi_control.connection.framing import (
    Framing,
    TransportClosed,
    TransportIdle,
    parse_block_header,
    read_framed,
)


def chunks(*items):
    """A read_chunk callable that plays `items` and then raises TransportIdle.

    bytes -> buffered and handed out up to `hint` bytes at a time, like a real
    socket: anything past `hint` stays queued for the next call instead of
    being dropped. TransportIdle/TransportClosed classes -> raised once the
    buffer they follow is drained.
    """
    queue = list(items)
    pending = b""

    def read_chunk(hint):
        nonlocal pending
        while not pending and queue:
            step = queue.pop(0)
            if isinstance(step, type) and issubclass(step, Exception):
                raise step()
            pending = step
        if not pending:
            raise TransportIdle()
        piece, pending = (pending, b"") if not hint else (pending[:hint], pending[hint:])
        return piece

    return read_chunk


class TestParseBlockHeader:
    def test_header_at_the_start(self):
        scan = parse_block_header(b"#3012" + b"x" * 12)
        assert scan.verdict == "block"
        # "#" (1) + digit-count digit (1) + 3-digit length field (3) + payload (12) = 17.
        assert scan.total == 1 + 1 + 3 + 12

    def test_printable_echo_prefix_still_frames(self):
        # Legacy Siglent answers `C1:WF DAT2,#9000000070<payload>`.
        scan = parse_block_header(b"C1:WF DAT2,#9000000070" + b"y" * 70)
        assert scan.verdict == "block"
        assert scan.total == len(b"C1:WF DAT2,#9000000070") + 70

    def test_binary_before_the_hash_is_not_a_header(self):
        # THE High-6 CASE: a BMP whose bytes happen to contain `#3123`.
        bmp = b"BM\x36\x00\x00\x00" + b"\x00\x01\x02" + b"#3123" + b"\xff" * 50
        assert parse_block_header(bmp).verdict == "absent"

    def test_split_header_is_incomplete_not_absent(self):
        assert parse_block_header(b"#").verdict == "incomplete"
        assert parse_block_header(b"#3").verdict == "incomplete"
        assert parse_block_header(b"#30").verdict == "incomplete"

    def test_indefinite_length_block_is_not_definite(self):
        assert parse_block_header(b"#0abc").verdict == "absent"

    def test_non_digit_length_field_is_absent(self):
        assert parse_block_header(b"#2ab").verdict == "absent"

    def test_empty_buffer_is_incomplete(self):
        assert parse_block_header(b"").verdict == "incomplete"

    def test_hash_at_or_beyond_the_max_header_prefix_bound_is_absent(self):
        # The scan only looks at the first _MAX_HEADER_PREFIX printable bytes.
        # A '#' sitting exactly at that boundary (index _MAX_HEADER_PREFIX,
        # one past the last scanned index) is never seen, so a response that
        # took its time getting there is correctly given up on rather than
        # scanned forever.
        from scpi_control.connection.framing import _MAX_HEADER_PREFIX

        at_bound = b"x" * _MAX_HEADER_PREFIX + b"#3000" + b"y" * 100
        assert parse_block_header(at_bound).verdict == "absent"


class TestReadFramed:
    def test_never_over_reads_past_the_declared_block_length(self):
        # Regression: while the header is unresolved, read_framed must never
        # request more than it can attribute to this frame. A read_chunk that
        # can hand back a big chunk in one call must not be allowed to swallow
        # the frame AND whatever the transport buffered right after it --
        # those trailing bytes belong to the transport's buffer, where a
        # terminator drain or a desync check still needs to see them.
        # Reviewer's repro: b"#15abcde" is a complete 8-byte block ('#','1'
        # digit-count, '5' length field -> 5-byte payload "abcde"); 8 bytes of
        # "X" follow it in the same underlying buffer and must not be read.
        buffer = b"#15abcde" + b"X" * 8
        cursor = [0]

        def read_chunk(hint):
            pos = cursor[0]
            if pos >= len(buffer):
                raise TransportIdle()
            take = min(hint, 16, len(buffer) - pos)
            piece = buffer[pos : pos + take]
            cursor[0] = pos + take
            return piece

        read = read_framed(read_chunk, Framing.AUTO)
        assert read.data == b"#15abcde"
        assert read.block_total == 8
        assert len(read.data) == read.block_total
        # The trailing "X"s were never consumed; they're still on the buffer.
        assert cursor[0] == 8

    def test_block_assembled_across_chunks(self):
        read = read_framed(chunks(b"#210", b"0123456789"), Framing.BLOCK)
        assert read.data == b"#2100123456789"
        # block_total is the full response size, so it must equal len(read.data).
        assert read.block_total == len(read.data) == 14

    def test_block_framing_refuses_a_headerless_response(self):
        with pytest.raises(exceptions.CommandError):
            read_framed(chunks(b"\x01\x02\x03", TransportIdle), Framing.BLOCK)

    def test_block_truncated_by_peer_close_raises_connection_error(self):
        with pytest.raises(exceptions.SiglentConnectionError):
            read_framed(chunks(b"#210012", TransportClosed), Framing.BLOCK)

    def test_block_stalled_mid_payload_raises_timeout(self):
        with pytest.raises(exceptions.SiglentTimeoutError):
            read_framed(chunks(b"#210012", TransportIdle), Framing.BLOCK)

    def test_stream_never_looks_for_a_header(self):
        # Same bytes as a valid block: STREAM must return all of them and
        # report no block total, not stop at the declared length.
        read = read_framed(chunks(b"#210", b"0123456789", b"surplus"), Framing.STREAM)
        assert read.data == b"#2100123456789surplus"
        assert read.block_total is None

    def test_auto_falls_back_to_draining_a_headerless_response(self):
        read = read_framed(chunks(b"BM\x00\x01#3123", b"\xff\xfe"), Framing.AUTO)
        assert read.data == b"BM\x00\x01#3123\xff\xfe"
        assert read.block_total is None

    def test_auto_notifies_the_transport_when_it_gives_up_on_a_header(self):
        # The socket loosens its timeout for the idle drain; the callback is
        # how a pure module tells it to.
        called = []
        read_framed(chunks(b"\x00\x01\x02", TransportIdle), Framing.AUTO, on_headerless=lambda: called.append(True))
        assert called == [True]

    def test_no_data_at_all_is_a_timeout(self):
        with pytest.raises(exceptions.SiglentTimeoutError):
            read_framed(chunks(TransportIdle), Framing.AUTO)
