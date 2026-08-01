"""A short read must not be returned as a successful one.

Backend review 2026-07-31 (Medium). When the peer closed mid-response, read()
and sized read_raw() broke out of their loops and returned what they had, with
is_connected still True: a 3.301 measurement arrived as "3.3", and a truncated
BMP was written to disk as a complete file. Where a length is known, a short
read is now an error; where it is not, the data is returned but the connection
stops claiming to be up.

Also here: a byte above 0x7F escaped read() as a raw UnicodeDecodeError, which
subclasses ValueError and was swallowed upstream (new_acquisition_ready read it
as "no gate"). None of this library's exceptions subclass ValueError, which is
the point.
"""

import pytest

from scpi_control import exceptions
from scpi_control.connection.framing import Framing
from tests.fake_socket import Close, Timeout, connected


def test_peer_close_before_the_terminator_is_an_error():
    conn, _ = connected([b"3.3", Close])
    with pytest.raises(exceptions.SiglentConnectionError):
        conn.read()


def test_a_short_sized_read_is_an_error():
    conn, _ = connected([b"12345", Close])
    with pytest.raises(exceptions.SiglentConnectionError) as excinfo:
        conn.read_raw(size=16)
    assert "16" in str(excinfo.value) and "5" in str(excinfo.value)


def test_a_stream_read_returns_what_arrived_but_stops_claiming_connected():
    conn, _ = connected([b"BM\x00\x01\x02", Close])
    assert conn.read_raw(framing=Framing.STREAM) == b"BM\x00\x01\x02"
    assert conn.is_connected is False


def test_non_ascii_is_a_typed_transport_error_not_a_valueerror():
    conn, _ = connected([b"3.3\xff\n"])
    with pytest.raises(exceptions.SiglentConnectionError) as excinfo:
        conn.read()
    assert not isinstance(excinfo.value, ValueError)


def test_a_decode_failure_marks_the_session_desynced():
    conn, _ = connected([b"3.3\xff\n"])
    with pytest.raises(exceptions.SiglentConnectionError):
        conn.read()
    assert conn._desynced is True
