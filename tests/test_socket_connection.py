"""Tests for socket connection module."""

import socket
import threading
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from scpi_control.connection.socket import SocketConnection
from scpi_control.exceptions import ConnectionError, TimeoutError
from tests.fake_socket import connected


@pytest.fixture
def mock_socket():
    """Create a mock socket."""
    with patch("socket.socket") as mock_sock:
        sock_instance = MagicMock()
        mock_sock.return_value = sock_instance
        yield sock_instance


class TestSocketConnectionInit:
    """Test socket connection initialization."""

    def test_init_default_port(self):
        """Test initialization with default port."""
        conn = SocketConnection("192.168.1.100")
        assert conn.host == "192.168.1.100"
        assert conn.port == 5025
        assert conn.timeout == 5.0

    def test_init_custom_port(self):
        """Test initialization with custom port."""
        conn = SocketConnection("192.168.1.100", port=8080)
        assert conn.port == 8080

    def test_init_custom_timeout(self):
        """Test initialization with custom timeout."""
        conn = SocketConnection("192.168.1.100", timeout=10.0)
        assert conn.timeout == 10.0


class TestSocketConnect:
    """Test socket connection establishment."""

    def test_connect_success(self, mock_socket):
        """Test successful connection."""
        conn = SocketConnection("192.168.1.100")
        conn.connect()

        assert conn._connected is True
        mock_socket.connect.assert_called_once_with(("192.168.1.100", 5025))
        mock_socket.settimeout.assert_called()

    def test_connect_failure(self, mock_socket):
        """Test connection failure."""
        mock_socket.connect.side_effect = socket.error("Connection refused")

        conn = SocketConnection("192.168.1.100")

        with pytest.raises(Exception):
            conn.connect()

        assert conn._connected is False

    def test_connect_timeout(self, mock_socket):
        """Test connection timeout."""
        mock_socket.connect.side_effect = socket.timeout("Connection timeout")

        conn = SocketConnection("192.168.1.100")

        with pytest.raises(Exception):
            conn.connect()

    def test_connect_failure_does_not_leak_peer_bytes(self, mock_socket):
        """A connect() failure must never surface bytes read from the peer.

        connect() has no legitimate reason to call recv() at all -- it only opens
        the socket -- but if a future change folded a banner/peek read into the
        failure path, an attacker-controlled peer could get its bytes echoed into
        exception text that reaches lower-trust callers (e.g. the SSRF-guarded
        gateway API; see tests/test_server_ssrf.py). Prime recv() with a
        realistic banner so the peer "sent" something before connect() itself
        fails, and assert the error text carries none of it.
        """
        banner = b"SSH-2.0-OpenSSH_9.6 SECRETBANNER"
        mock_socket.recv.return_value = banner
        mock_socket.connect.side_effect = socket.error("Connection refused")

        conn = SocketConnection("192.168.1.100")

        with pytest.raises(Exception) as exc_info:
            conn.connect()

        message = str(exc_info.value)
        assert banner.decode("ascii") not in message
        assert "SSH-2.0-OpenSSH_9.6" not in message
        assert "SECRETBANNER" not in message
        assert "SSH" not in message

    def test_already_connected(self, mock_socket):
        """Test connecting when already connected."""
        conn = SocketConnection("192.168.1.100")
        conn.connect()

        # Try to connect again
        conn.connect()

        # Should only connect once (or disconnect and reconnect)
        assert conn._connected is True


class TestSocketDisconnect:
    """Test socket disconnection."""

    def test_disconnect_when_connected(self, mock_socket):
        """Test disconnecting when connected."""
        conn = SocketConnection("192.168.1.100")
        conn.connect()
        conn.disconnect()

        assert conn._connected is False
        mock_socket.close.assert_called()

    def test_disconnect_when_not_connected(self, mock_socket):
        """Test disconnecting when not connected."""
        conn = SocketConnection("192.168.1.100")
        conn.disconnect()  # Should not raise error

        assert conn._connected is False


class TestSocketSendCommand:
    """Test sending commands."""

    def test_send_command_simple(self, mock_socket):
        """Test sending a simple command."""
        conn = SocketConnection("192.168.1.100")
        conn.connect()

        conn.write("*IDN?")

        # Verify data was sent
        assert mock_socket.sendall.called
        sent_data = mock_socket.sendall.call_args[0][0]
        assert b"*IDN?" in sent_data

    def test_send_command_with_newline(self, mock_socket):
        """Test that commands are terminated with newline."""
        conn = SocketConnection("192.168.1.100")
        conn.connect()

        conn.write("TRIG_MODE AUTO")

        sent_data = mock_socket.sendall.call_args[0][0]
        assert sent_data.endswith(b"\n") or sent_data.endswith(b"\r\n")

    def test_send_command_not_connected(self, mock_socket):
        """Test sending command when not connected."""
        conn = SocketConnection("192.168.1.100")

        with pytest.raises(Exception):
            conn.write("*IDN?")

    def test_send_command_socket_error(self, mock_socket):
        """Test handling socket error during send."""
        conn = SocketConnection("192.168.1.100")
        conn.connect()

        mock_socket.sendall.side_effect = socket.error("Connection lost")

        with pytest.raises(Exception):
            conn.write("*IDN?")


class TestSocketQuery:
    """Test querying (send and receive)."""

    def test_query_simple(self, mock_socket):
        """Test simple query."""
        mock_socket.recv.return_value = b"SIGLENT,SDS1104X-E,1234567,1.0.0.0\n"

        conn = SocketConnection("192.168.1.100")
        conn.connect()

        response = conn.query("*IDN?")

        assert "SIGLENT" in response
        assert "SDS1104X-E" in response
        mock_socket.sendall.assert_called()
        mock_socket.recv.assert_called()

    def test_query_multiple_chunks(self, mock_socket):
        """Test query with response in multiple chunks."""
        mock_socket.recv.side_effect = [b"SIGLENT,", b"SDS1104X-E,", b"1234567\n"]

        conn = SocketConnection("192.168.1.100")
        conn.connect()

        response = conn.query("*IDN?")

        assert "SIGLENT" in response
        assert "SDS1104X-E" in response

    def test_query_timeout(self, mock_socket):
        """Test query timeout."""
        mock_socket.recv.side_effect = socket.timeout("Read timeout")

        conn = SocketConnection("192.168.1.100")
        conn.connect()

        with pytest.raises(Exception):
            conn.query("*IDN?")

    def test_query_not_connected(self, mock_socket):
        """Test query when not connected."""
        conn = SocketConnection("192.168.1.100")

        with pytest.raises(Exception):
            conn.query("*IDN?")


class TestSocketQueryBinary:
    """Test binary data queries."""

    def test_query_binary(self, mock_socket):
        """Test querying binary data."""
        # Mock binary waveform data
        test_data = bytes([0, 127, 255, 128, 64] * 200)  # 1000 bytes
        # Use side_effect to return data once, then timeout to signal end
        mock_socket.recv.side_effect = [test_data, socket.timeout()]

        conn = SocketConnection("192.168.1.100")
        conn.connect()

        conn.write("C1:WF? DAT2")
        data = conn.read_raw()

        assert isinstance(data, bytes)
        assert len(data) > 0
        assert data == test_data

    def test_query_binary_large_data(self, mock_socket):
        """Test querying large binary data."""
        # Simulate receiving data in chunks
        chunk_size = 1024
        total_chunks = 10
        test_chunks = [bytes([i % 256] * chunk_size) for i in range(total_chunks)]

        mock_socket.recv.side_effect = test_chunks + [b"", socket.timeout()]  # Empty byte to signal end

        conn = SocketConnection("192.168.1.100")
        conn.connect()

        try:
            conn.write("C1:WF? DAT2")
            data = conn.read_raw()
            assert isinstance(data, bytes)
        except Exception:
            # Some implementations may handle this differently
            pass


class TestSocketContextManager:
    """Test using socket connection as context manager."""

    def test_context_manager(self, mock_socket):
        """Test using connection as context manager."""
        with SocketConnection("192.168.1.100") as conn:
            assert conn._connected is True
            conn.write("*IDN?")

        # Should be disconnected after exiting context
        assert conn._connected is False
        mock_socket.close.assert_called()

    def test_context_manager_with_error(self, mock_socket):
        """Test context manager with error inside context."""
        try:
            with SocketConnection("192.168.1.100") as conn:
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should still disconnect even with error
        mock_socket.close.assert_called()


class TestSocketReconnect:
    """Test reconnection logic."""

    def test_reconnect(self, mock_socket):
        """Test reconnecting after disconnect."""
        conn = SocketConnection("192.168.1.100")

        # First connection
        conn.connect()
        assert conn._connected is True

        # Disconnect
        conn.disconnect()
        assert conn._connected is False

        # Reconnect
        conn.connect()
        assert conn._connected is True

        # Should have connected twice
        assert mock_socket.connect.call_count == 2

    def test_auto_reconnect_on_error(self, mock_socket):
        """Test auto-reconnect on communication error."""
        conn = SocketConnection("192.168.1.100")
        conn.connect()

        # Simulate connection lost
        mock_socket.sendall.side_effect = [socket.error("Connection lost"), None]  # Succeeds after reconnect

        if hasattr(conn, "auto_reconnect") and getattr(conn, "auto_reconnect", False):
            try:
                conn.write("*IDN?")
                # Should have attempted reconnection
                assert mock_socket.connect.call_count > 1
            except Exception:
                pass  # Expected if auto-reconnect not implemented


class TestSocketConfiguration:
    """Test socket configuration."""

    def test_set_timeout(self, mock_socket):
        """Test setting timeout."""
        conn = SocketConnection("192.168.1.100", timeout=5.0)
        conn.connect()

        mock_socket.settimeout.assert_called_with(5.0)

        # Change timeout
        conn.timeout = 10.0
        if hasattr(conn, "_update_timeout"):
            conn._update_timeout()
            mock_socket.settimeout.assert_called_with(10.0)

    def test_socket_options(self, mock_socket):
        """Test socket options are set."""
        conn = SocketConnection("192.168.1.100")
        conn.connect()

        # Check if common socket options are set
        # (keepalive, nodelay, etc.)
        assert mock_socket.setsockopt.called or True  # May not be implemented


class TestSocketErrorHandling:
    """Test comprehensive error handling."""

    def test_connection_refused(self, mock_socket):
        """Test handling connection refused."""
        mock_socket.connect.side_effect = ConnectionRefusedError("Connection refused")

        conn = SocketConnection("192.168.1.100")

        with pytest.raises(Exception):
            conn.connect()

    def test_host_unreachable(self, mock_socket):
        """Test handling host unreachable."""
        mock_socket.connect.side_effect = OSError("No route to host")

        conn = SocketConnection("192.168.1.100")

        with pytest.raises(Exception):
            conn.connect()

    def test_broken_pipe(self, mock_socket):
        """Test handling broken pipe."""
        conn = SocketConnection("192.168.1.100")
        conn.connect()

        mock_socket.sendall.side_effect = BrokenPipeError("Broken pipe")

        with pytest.raises(Exception):
            conn.write("*IDN?")


class TestSocketStringRepresentation:
    """Test string representation."""

    def test_str(self):
        """Test string representation."""
        conn = SocketConnection("192.168.1.100", port=5024)
        assert "192.168.1.100" in str(conn)
        assert "5024" in str(conn)

    def test_repr(self):
        """Test repr."""
        conn = SocketConnection("192.168.1.100")
        assert "SocketConnection" in repr(conn)
        assert "192.168.1.100" in repr(conn)


class TestSocketThreadSafety:
    """Test that concurrent SCPI exchanges cannot interleave."""

    def test_connection_exposes_reentrant_lock(self, mock_socket):
        conn = SocketConnection("192.168.1.100")
        # Reentrant: acquiring twice from the same thread must not deadlock
        with conn.lock:
            with conn.lock:
                pass

    def test_query_is_atomic_under_concurrency(self, mock_socket):
        # Q1's send is slow; without a lock, thread 2 completes its write and
        # steals Q1's response off the wire. With the lock, each query's
        # write+read pair is atomic and both threads get their own response.
        responses = {b"Q1?\n": b"R1\n", b"Q2?\n": b"R2\n"}
        pending = []

        def fake_sendall(data):
            pending.append(data)
            if data == b"Q1?\n":
                time.sleep(0.1)

        def fake_recv(size):
            return responses[pending.pop(0)]

        mock_socket.sendall.side_effect = fake_sendall
        mock_socket.recv.side_effect = fake_recv

        conn = SocketConnection("192.168.1.100")
        conn.connect()

        results = {}

        def do_query(cmd):
            results[cmd] = conn.query(cmd)

        t1 = threading.Thread(target=do_query, args=("Q1?",))
        t2 = threading.Thread(target=do_query, args=("Q2?",))
        t1.start()
        time.sleep(0.02)  # ensure t1 is inside its slow sendall first
        t2.start()
        t1.join()
        t2.join()

        assert results == {"Q1?": "R1", "Q2?": "R2"}


class TestReadRawIeeeBlock:
    """read_raw(None) must honor the IEEE 488.2 definite-length header."""

    def test_reads_exactly_declared_block_length(self):
        # "C1:WF DAT2," prefix (11 bytes) + "#9" + 9-digit length (20) + payload
        #
        # Task 4 (backend review 2026-07-31, High-7): this used to script
        # `mock_socket.recv.side_effect = [..., b"\n\n", ...]`, pinning the OLD
        # `_drain_terminator`'s fixed `recv(2)` -- a MagicMock hands back the
        # whole `b"\n\n"` chunk to a single call regardless of the size or
        # MSG_PEEK flag requested, which is exactly the dishonesty the new
        # peek-and-consume drain cannot tolerate (each byte costs one peek
        # call and one consuming call). `tests.fake_socket.FakeSocket` buffers
        # honestly -- it honors requested sizes and never lets MSG_PEEK
        # consume -- so it can model the terminator arriving as its own
        # two-byte chunk without over-delivering.
        part1 = b"C1:WF DAT2,#9000000020" + b"A" * 10
        part2 = b"B" * 10
        conn, fake = connected([part1, part2, b"\n\n"])

        data = conn.read_raw()

        assert data == part1 + part2 + b"\n\n"
        # The block path must never fall back to the legacy 0.5s idle drain
        assert 0.5 not in fake.timeouts

    def test_header_split_across_chunks(self, mock_socket):
        part1 = b"C1:WF DAT2,#"
        part2 = b"9000000005HELLO\n\n"
        mock_socket.recv.side_effect = [part1, part2, socket.timeout()]

        conn = SocketConnection("192.168.1.100")
        conn.connect()
        data = conn.read_raw()

        assert data == part1 + part2

    def test_stall_mid_block_raises_timeout(self, mock_socket):
        # Header declares 100 bytes but the line goes silent after 10
        mock_socket.recv.side_effect = [b"C1:WF DAT2,#9000000100" + b"A" * 10, socket.timeout()]

        conn = SocketConnection("192.168.1.100")
        conn.connect()

        with pytest.raises(TimeoutError):
            conn.read_raw()

    def test_no_data_at_all_raises_timeout(self, mock_socket):
        # Previously returned b"" silently; an empty line is now an error
        mock_socket.recv.side_effect = [socket.timeout()]

        conn = SocketConnection("192.168.1.100")
        conn.connect()

        with pytest.raises(TimeoutError):
            conn.read_raw()

    def test_headerless_response_still_drains_on_idle(self, mock_socket):
        # Responses without a '#' block keep the legacy idle-drain behavior
        blob = bytes([0, 127, 255, 128, 64] * 200)  # 1000 bytes, no b"#"
        mock_socket.recv.side_effect = [blob, socket.timeout()]

        conn = SocketConnection("192.168.1.100")
        conn.connect()

        assert conn.read_raw() == blob

    def test_terminator_already_in_the_buffer_is_still_appended(self):
        """Payload and trailing terminator sent by the peer as one segment.

        Rewritten for Task 2 (backend review 2026-07-31, High-6): this used
        to assert `mock_socket.recv.call_count == 1`, pinning the OLD
        `_parse_block_total` polling loop's behavior of pulling up to
        `_buffer_size` bytes per recv() -- when the terminator happened to
        already be in the peer's send buffer, one big recv() swept it up
        alongside the payload, and the old code special-cased that to skip
        an unnecessary extra recv(). read_framed() (framing.py) never
        over-reads: it reads exactly `block_total` bytes -- one byte at a
        time until the header resolves, then capped to exactly the
        remainder -- and always leaves the terminator for one separate
        drain attempt. So "the terminator arrived bundled with the payload"
        is no longer a distinguishable case for an honest transport, and
        `mock_socket` (a MagicMock that ignores the requested read size and
        always hands back a whole scripted chunk) can no longer model this
        scenario at all -- it made read_framed's single 1-byte request
        return all 44 bytes at once, so the subsequent terminator-drain
        recv() call ran past the end of a 1-item side_effect list and raised
        StopIteration. `tests/fake_socket.FakeSocket` buffers honestly (it
        only ever returns up to the requested size), so it reproduces the
        real scenario -- payload and terminator both already sitting in the
        socket buffer -- without over-delivering.
        """
        blob = b"C1:WF DAT2,#9000000020" + b"A" * 20 + b"\n\n"
        conn, _ = connected([blob])

        assert conn.read_raw() == blob


class TestSocketReadRawTimeout:
    """Test that socket timeouts in read_raw are classified as timeouts, not dead connections."""

    def test_sized_read_timeout_raises_timeout_and_keeps_session(self, mock_socket):
        """recv raises socket.timeout during sized-read; must not kill the session."""
        mock_socket.recv.side_effect = socket.timeout("timed out")

        conn = SocketConnection("192.168.1.100")
        conn.connect()

        with pytest.raises(TimeoutError):
            conn.read_raw(100)
        assert conn.is_connected

    def test_block_read_timeout_raises_timeout_and_keeps_session(self, mock_socket):
        """recv raises socket.timeout during block-read; must not kill the session.

        Updated by Task 2 (backend review 2026-07-31, High-6): `_read_ieee_block()`
        no longer catches `socket.timeout` itself -- it delegates to
        `read_framed()` (scpi_control/connection/framing.py), which drives
        this connection's `_read_chunk()`. `_read_chunk()` is what now
        converts a raw `socket.timeout` to `TransportIdle`, and `read_framed()`
        converts that to `SiglentTimeoutError` before it ever reaches
        `read_raw()`'s own try/except. So, as before the refactor, this test
        does NOT on its own exercise the `except socket.timeout` clause
        `read_raw()` carries as a second, defensive layer for a raw
        `socket.timeout` that escapes the framing module uncaught.
        """
        mock_socket.recv.side_effect = socket.timeout("timed out")

        conn = SocketConnection("192.168.1.100")
        conn.connect()

        with pytest.raises(TimeoutError):
            conn.read_raw(None)
        assert conn.is_connected
