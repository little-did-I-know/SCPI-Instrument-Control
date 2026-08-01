"""VISAConnection must be instantiable (audit H10, found by two audits).

Every USB/GPIB/RS-232 path raised TypeError at construction because two abstract
methods (`read`, `read_raw`) were never implemented, and `ABCMeta` rejected the
class before `__init__` ever ran. These tests run WITHOUT pyvisa installed --
that is the point: the entire pre-existing test_visa_connection.py is
skip-guarded on pyvisa availability, so it never exercised this bug. `__init__`
itself makes no pyvisa calls (the real `pyvisa.ResourceManager()` call lives in
`connect()`), so patching the availability flag lets construction complete here
even though pyvisa is absent.
"""

from unittest.mock import MagicMock, patch

import pytest

from scpi_control.connection.base import BaseConnection
from scpi_control.connection.visa_connection import VISAConnection
from scpi_control.exceptions import SiglentConnectionError


def test_visa_connection_is_concrete():
    # The bug: abstract read/read_raw made this frozenset non-empty, so the class
    # could never be instantiated. Runs without pyvisa -- this is what caught H10.
    assert not getattr(VISAConnection, "__abstractmethods__", frozenset())


def test_visa_connection_constructs():
    with patch("scpi_control.connection.visa_connection.PYVISA_AVAILABLE", True):
        conn = VISAConnection("GPIB0::12::INSTR")
    assert isinstance(conn, BaseConnection)


def test_base_init_ran():
    """super().__init__() was never called, so _connected/lock were missing."""
    with patch("scpi_control.connection.visa_connection.PYVISA_AVAILABLE", True):
        conn = VISAConnection("GPIB0::12::INSTR")
    assert conn._connected is False
    assert conn.lock is not None
    assert conn.is_connected is False


def _fake_session():
    """A connection with a stub resource attached, as connect() would leave it.

    `_connected` has to be set alongside `_resource`: since wave 3, is_connected
    is "_connected AND _resource is not None", so that a connect that failed
    half-way stops reporting itself connected (see
    tests/test_visa_contract_compliance.py).
    """
    with patch("scpi_control.connection.visa_connection.PYVISA_AVAILABLE", True):
        conn = VISAConnection("GPIB0::12::INSTR")
    conn._resource = MagicMock()
    conn._connected = True
    return conn


def test_read_strips_terminator():
    conn = _fake_session()
    conn._resource.read.return_value = "response\n"
    assert conn.read() == "response"


def test_read_raw_honors_size():
    conn = _fake_session()
    conn._resource.read_bytes.return_value = b"12345678"
    assert conn.read_raw(8) == b"12345678"
    conn._resource.read_bytes.assert_called_once_with(8)


def test_read_raw_none_frames_the_response():
    # Wave 3 changed what "no size" means here: read_raw(None) frames the
    # response through connection.framing instead of delegating to pyvisa's
    # read_raw(), so the 0x0A in the middle of this block no longer ends the
    # read. A complete definite-length block terminates on its own declared
    # length, which is what lets this run in a file that deliberately has no
    # pyvisa (and so no VISA timeout to end an open-ended read with).
    conn = _fake_session()
    block = b"#15he\nlo"
    remaining = [block]

    def read_bytes(count, *args, **kwargs):
        head, remaining[0] = remaining[0][:count], remaining[0][count:]
        return head

    conn._resource.read_bytes.side_effect = read_bytes
    assert conn.read_raw() == block


def test_read_without_connection_raises():
    with patch("scpi_control.connection.visa_connection.PYVISA_AVAILABLE", True):
        conn = VISAConnection("GPIB0::12::INSTR")

    with pytest.raises(SiglentConnectionError):
        conn.read()


def test_read_raw_without_connection_raises():
    with patch("scpi_control.connection.visa_connection.PYVISA_AVAILABLE", True):
        conn = VISAConnection("GPIB0::12::INSTR")

    with pytest.raises(SiglentConnectionError):
        conn.read_raw()
