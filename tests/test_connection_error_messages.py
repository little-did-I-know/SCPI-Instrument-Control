import socket

import pytest

from scpi_control import exceptions
from scpi_control.connection.socket import SocketConnection


class FakeSocket:
    def __init__(self, *, send_exception=None, recv_exception=None, recv_sequence=None):
        self.timeout = None
        self.address = None
        self.send_exception = send_exception
        self.recv_exception = recv_exception
        self.recv_sequence = recv_sequence or []
        self._recv_index = 0

    def settimeout(self, value):
        self.timeout = value

    def connect(self, address):
        self.address = address

    def sendall(self, data):
        if self.send_exception:
            raise self.send_exception

    def recv(self, _buffer_size):
        if self.recv_exception:
            raise self.recv_exception
        if self._recv_index < len(self.recv_sequence):
            chunk = self.recv_sequence[self._recv_index]
            self._recv_index += 1
            return chunk
        return b""

    def close(self):
        return None


def test_socket_write_timeout_has_command_and_host(monkeypatch):
    fake = FakeSocket(send_exception=socket.timeout("timed out"))
    monkeypatch.setattr("scpi_control.connection.socket.socket.socket", lambda *_args, **_kwargs: fake)

    conn = SocketConnection("1.2.3.4", port=1111, timeout=0.1)
    conn.connect()

    with pytest.raises(exceptions.TimeoutError) as excinfo:
        conn.write("MEASure?")

    message = str(excinfo.value)
    assert "1.2.3.4:1111" in message
    assert "MEASure?" in message
    assert "timeout" in message.lower()


def test_socket_read_error_has_command_and_host(monkeypatch):
    fake = FakeSocket(recv_exception=socket.error("boom"))
    monkeypatch.setattr("scpi_control.connection.socket.socket.socket", lambda *_args, **_kwargs: fake)

    conn = SocketConnection("5.6.7.8", port=2222, timeout=0.1)
    conn.connect()
    conn.write("STAT?")

    with pytest.raises(exceptions.ConnectionError) as excinfo:
        conn.read()

    message = str(excinfo.value)
    assert "5.6.7.8:2222" in message
    assert "STAT?" in message
    assert "boom" in message
