"""A scripted stand-in for a real TCP socket.

Backend review 2026-07-31 wave 3. Every transport bug in this wave is
timing-shaped -- a reply that arrives after we gave up, a terminator that
arrives late, a peer that closes mid-response -- so the tests have to control
WHEN bytes appear, not just what they are. This plays a scripted timeline
against SocketConnection with no network and no waiting.

MSG_PEEK is modelled honestly: a peek does not consume. If it silently did,
the terminator guard in tests/test_socket_resync.py would pass without its fix,
which is the entire reason that guard exists.
"""

import socket


class Timeout:
    """Script step: the next recv() raises socket.timeout."""


class Close:
    """Script step: the peer closes; every later recv() returns b""."""


class AfterSend:
    """Script step: withhold everything after it until one more sendall().

    Without this a fake delivers the whole script the instant it is asked, so
    "the reply to the NEXT command" would already be sitting in the buffer and
    the resync would eat it -- a test that passes for the wrong reason. This is
    what makes "arrives only once the next command goes out" expressible.
    """


class FakeSocket:
    """socket.socket stand-in driven by a list of bytes / Timeout / Close / AfterSend steps."""

    def __init__(self, script=None):
        self.script = list(script or [])
        self.sent = []
        self.timeouts = []
        self.closed = False
        self._pending = b""
        self._timeout = None
        self._peer_closed = False
        self._barrier_at = None

    # --- the parts of the socket API SocketConnection uses -----------------
    def settimeout(self, value):
        self._timeout = value
        self.timeouts.append(value)

    def gettimeout(self):
        return self._timeout

    def connect(self, address):
        self.address = address

    def sendall(self, payload):
        self.sent.append(payload)

    def close(self):
        self.closed = True

    def recv(self, bufsize, flags=0):
        if not self._pending:
            if self._peer_closed:
                return b""
            self._advance()
        chunk = self._pending[:bufsize]
        if not flags & socket.MSG_PEEK:
            self._pending = self._pending[len(chunk) :]
        return chunk

    # --- script driver -----------------------------------------------------
    def _advance(self):
        while self.script:
            step = self.script[0]
            if step is AfterSend or isinstance(step, AfterSend):
                if self._barrier_at is None:
                    self._barrier_at = len(self.sent)
                if len(self.sent) <= self._barrier_at:
                    raise socket.timeout("scripted: waiting for the next command")
                self._barrier_at = None
                self.script.pop(0)
                continue
            self.script.pop(0)
            if isinstance(step, bytes):
                self._pending = step
                return
            if step is Timeout or isinstance(step, Timeout):
                raise socket.timeout("scripted timeout")
            if step is Close or isinstance(step, Close):
                self._peer_closed = True
                return
        raise socket.timeout("scripted timeout (script exhausted)")


def connected(script=None, timeout=5.0, host="192.168.1.100", port=5025):
    """Return (connection, fake) with the connection already 'connected'."""
    from scpi_control.connection.socket import SocketConnection

    conn = SocketConnection(host, port=port, timeout=timeout)
    fake = FakeSocket(script)
    conn._socket = fake
    conn._connected = True
    return conn, fake
