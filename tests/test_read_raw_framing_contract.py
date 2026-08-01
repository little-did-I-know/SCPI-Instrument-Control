"""Every transport takes the same framing declaration, and the mock enforces it.

Backend review 2026-07-31 wave 3. The caller always knows whether it asked for
a definite-length block; the transport does not. Declaring it is what removes
the guess from the paths we control -- and the mock HOLDS callers to the
declaration, so a call site that declares the wrong framing fails in CI instead
of on hardware (the wave-2 lesson: a mock that answers what the parser expects
cannot catch a parser that expects the wrong thing).
"""

import inspect

import pytest

from scpi_control import exceptions
from scpi_control.connection.base import BaseConnection
from scpi_control.connection.framing import Framing
from scpi_control.connection.mock import MockConnection
from scpi_control.connection.socket import SocketConnection
from scpi_control.connection.visa_connection import VISAConnection

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,SDS1EBAC0L0098,7.6.1.15"


@pytest.mark.parametrize("cls", [BaseConnection, SocketConnection, VISAConnection, MockConnection])
def test_read_raw_accepts_a_framing_declaration(cls):
    parameters = inspect.signature(cls.read_raw).parameters
    assert "framing" in parameters
    assert parameters["framing"].default is Framing.AUTO


@pytest.mark.parametrize("cls", [BaseConnection, SocketConnection, VISAConnection, MockConnection])
def test_every_connection_can_resync(cls):
    assert callable(getattr(cls, "resync", None))


def test_mock_serves_a_block_when_block_is_declared():
    conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True})
    conn.connect()
    conn.write("SCDP?")
    assert conn.read_raw(framing=Framing.BLOCK).startswith(b"#")


def test_mock_rejects_a_block_declaration_it_cannot_honour():
    # The mock's own answer is the wire truth here: declaring BLOCK for a
    # response that carries no header must fail loudly, not silently pass.
    conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True})
    conn.connect()
    conn.write("SCDP?")
    conn.mock_raw_response = b"BM\x36\x00\x00\x00 not a block"
    with pytest.raises(exceptions.CommandError):
        conn.read_raw(framing=Framing.BLOCK)


def test_mock_stream_framing_returns_the_payload_untouched():
    conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True})
    conn.connect()
    conn.write("SCDP?")
    payload = conn.read_raw(framing=Framing.STREAM)
    assert payload == conn.read_raw(framing=Framing.STREAM)
