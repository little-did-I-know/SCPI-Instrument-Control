"""Dialect-aware SCDP screen-dump parsing.

Modern Siglent scopes (SDS800X HD) answer ``SCDP`` with a raw BMP whose size is
in its header (read by exact byte count); legacy scopes and the mock answer
``SCDP?`` with an IEEE-488.2 definite-length block. Neither needs an
oscilloscope -- the readers are driven by fakes.
"""

import struct
import threading

import pytest

from scpi_control.screen_capture import ScreenCapture, _extract_ieee_block, _read_bmp_by_header


class _SeqReader:
    """A ``read_exact(n) -> bytes`` callable that returns exactly n bytes (like a socket)."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def __call__(self, n: int) -> bytes:
        chunk = self.data[self.pos : self.pos + n]
        self.pos += len(chunk)
        return chunk


def _raw_bmp(payload_len: int) -> bytes:
    """A minimal raw BMP: 'BM' + little-endian uint32 total size + body."""
    total = 6 + payload_len
    return b"BM" + struct.pack("<I", total) + (b"\xab" * payload_len)


def _ieee_block(payload: bytes) -> bytes:
    """Wrap payload in an IEEE-488.2 block: #<ndigits><length><payload>."""
    length = str(len(payload)).encode()
    return b"#" + str(len(length)).encode() + length + payload


# --- modern: raw BMP read by header size ---


def test_read_bmp_by_header_reads_declared_size():
    bmp = _raw_bmp(2000)
    # A trailing terminator after the declared size must NOT be pulled into the image.
    out = _read_bmp_by_header(_SeqReader(bmp + b"\n"))
    assert out == bmp
    assert struct.unpack("<I", out[2:6])[0] == len(out)


def test_read_bmp_by_header_rejects_non_bmp():
    with pytest.raises(RuntimeError):
        _read_bmp_by_header(_SeqReader(b"#9 not a bmp"))


# --- legacy/mock: IEEE-488.2 block (or an already-stripped payload) ---


def test_extract_ieee_block_strips_header():
    bmp = _raw_bmp(58)
    assert _extract_ieee_block(_ieee_block(bmp)) == bmp


def test_extract_ieee_block_passes_through_bare_payload():
    bmp = _raw_bmp(58)  # connection already stripped the block header
    assert _extract_ieee_block(bmp) == bmp


def test_extract_ieee_block_empty_raises():
    with pytest.raises(RuntimeError):
        _extract_ieee_block(b"")


# --- dialect-aware capture wiring ---


class _Conn:
    def __init__(self, data: bytes, sequential: bool, drain_error: Exception = None):
        self._data = data
        self._seq = _SeqReader(data)
        self._sequential = sequential
        self.lock = threading.RLock()
        self.drain_calls = 0
        self.resync_calls = 0
        self._drain_error = drain_error

    def read_raw(self, n=None, framing=None) -> bytes:
        return self._seq(n) if self._sequential else self._data

    def drain_input(self) -> int:
        # A stand-in for BaseConnection.drain_input(): _capture_with_scdp
        # calls this after the modern read to discard a trailing byte, but
        # this fake has nothing buffered to discard.
        self.drain_calls += 1
        if self._drain_error is not None:
            raise self._drain_error
        return 0

    def resync(self) -> int:
        # Present so a capture that asks for the WRONG verb is visible rather
        # than an AttributeError: resync() may take a protocol-level action
        # (VISAConnection prefers a device clear), which post-capture
        # housekeeping has no business requesting.
        self.resync_calls += 1
        return 0


class _Scope:
    def __init__(self, conn, dialect):
        self._connection = conn
        self.dialect = dialect
        self.written = []

    def write(self, cmd):
        self.written.append(cmd)


def test_capture_modern_sends_scdp_and_reads_bmp_by_size():
    bmp = _raw_bmp(500)
    conn = _Conn(bmp, sequential=True)
    scope = _Scope(conn, dialect="modern")
    assert ScreenCapture(scope).capture_screenshot() == bmp
    assert scope.written == ["SCDP"]
    # Discarding the terminator behind the image is a DRAIN, not a session
    # recovery. resync() may abort the instrument's pending operation
    # (VISAConnection prefers a device clear), which is not something a
    # finished screenshot should trigger.
    assert conn.drain_calls == 1
    assert conn.resync_calls == 0


def test_a_failed_drain_does_not_throw_away_a_captured_screenshot():
    # The image has already been read when the drain runs. A transport fault
    # in that housekeeping used to propagate out of capture_screenshot() as
    # "Failed to capture screenshot" -- with the complete image in hand.
    # SocketConnection's drain catches only socket.timeout, so a peer reset
    # mid-drain is exactly this.
    bmp = _raw_bmp(500)
    conn = _Conn(bmp, sequential=True, drain_error=ConnectionResetError("peer reset during the drain"))
    scope = _Scope(conn, dialect="modern")
    assert ScreenCapture(scope).capture_screenshot() == bmp
    assert conn.drain_calls == 1


def test_a_failed_drain_is_reported_rather_than_swallowed(caplog):
    bmp = _raw_bmp(64)
    conn = _Conn(bmp, sequential=True, drain_error=ConnectionResetError("peer reset during the drain"))
    scope = _Scope(conn, dialect="modern")
    with caplog.at_level("WARNING"):
        ScreenCapture(scope).capture_screenshot()
    assert "peer reset during the drain" in caplog.text


def test_capture_legacy_sends_scdp_query_and_extracts_block():
    bmp = _raw_bmp(58)
    scope = _Scope(_Conn(_ieee_block(bmp), sequential=False), dialect="legacy")
    assert ScreenCapture(scope).capture_screenshot() == bmp
    assert scope.written == ["SCDP?"]
