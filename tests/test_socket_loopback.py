"""The socket fixes, proven against a real kernel socket buffer.

tests/fake_socket.py is a fake: it proves the code behaves as scripted. These
prove the same behaviours against an actual TCP connection, where the late
reply really does sit in the receive buffer and a binary payload arrives in
whatever chunk sizes the kernel decides, not in scripted steps. Kept short,
with short timeouts, so they stay sub-second and do not need the `slow`
marker.
"""

import socket
import threading
import time

import pytest

from scpi_control import exceptions
from scpi_control.connection.framing import Framing
from scpi_control.connection.socket import SocketConnection

POISON = b"BM\x36\x04\x00\x00" + b"\x00" * 4 + b"#3123" + b"\xff" * 40


class Server:
    """A one-connection TCP fake instrument driven by a handler callable."""

    def __init__(self, handler):
        self.handler = handler
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)
        self.port = self._listener.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        conn, _ = self._listener.accept()
        try:
            self.handler(conn)
        finally:
            conn.close()
            self._listener.close()

    def join(self):
        self._thread.join(timeout=5)


@pytest.fixture
def connect_to():
    created = []

    def factory(handler, timeout=0.3):
        server = Server(handler)
        conn = SocketConnection("127.0.0.1", port=server.port, timeout=timeout)
        conn.connect()
        created.append((conn, server))
        return conn, server

    yield factory
    for conn, server in created:
        conn.disconnect()
        server.join()


def test_a_late_reply_does_not_answer_the_next_query(connect_to):
    landed = threading.Event()

    def handler(sock):
        sock.recv(4096)  # first query: answered after the client gives up
        time.sleep(0.4)
        sock.sendall(b"STALE\n")
        landed.set()
        sock.recv(4096)  # second query
        sock.sendall(b"3.301\n")

    conn, _ = connect_to(handler)
    with pytest.raises(exceptions.SiglentTimeoutError):
        conn.query("MEAS:VOLT?")
    # Wait for the straggler to actually be in the receive buffer before
    # sending the next command. This is deliberate, not a papered-over race:
    # the drain discards what has ARRIVED, and a reply still in flight cannot
    # be told apart from the answer to the command about to go out (stated in
    # SocketConnection.resync's docstring). The test pins the guarantee the
    # library makes, not one it does not.
    assert landed.wait(timeout=5)
    assert conn.query("MEAS:CURR?") == "3.301"


def test_binary_containing_a_hash_survives_a_real_socket(connect_to):
    """AUTO is what third-party callers get by default, and the only framing
    that actually exercises parse_block_header's printable-ASCII guard --
    Framing.STREAM (below) short-circuits past that scan entirely, so it
    would pass even if the guard were broken. This is the live-socket proof
    that a `#` behind non-printable bytes is not mistaken for a block header
    when the payload arrives in real, kernel-decided chunk sizes rather than
    the fake's scripted ones (High-6)."""

    def handler(sock):
        sock.recv(4096)
        sock.sendall(POISON)

    conn, _ = connect_to(handler)
    conn.write("SCDP")
    assert conn.read_raw(framing=Framing.AUTO) == POISON


def test_binary_containing_a_hash_survives_a_real_socket_under_stream_framing(connect_to):
    """A second, narrower guard: STREAM framing itself must not misframe
    either, even though (per the test above) it never reaches
    parse_block_header at all -- it drains raw until the peer closes."""

    def handler(sock):
        sock.recv(4096)
        sock.sendall(POISON)

    conn, _ = connect_to(handler)
    conn.write("SCDP")
    assert conn.read_raw(framing=Framing.STREAM) == POISON


def test_a_peer_close_mid_response_is_an_error(connect_to):
    def handler(sock):
        sock.recv(4096)
        sock.sendall(b"3.3")  # no terminator, then close

    conn, _ = connect_to(handler)
    conn.write("MEAS:VOLT?")
    with pytest.raises(exceptions.SiglentConnectionError):
        conn.read()
