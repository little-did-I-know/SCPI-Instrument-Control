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
    # A caller holding a BaseConnection-typed reference must be able to call
    # read_raw(size, framing) positionally against ANY implementation. Keyword-only
    # on one connection (VISA once did this) breaks that uniformly for callers
    # that don't know which concrete class they're holding.
    assert parameters["framing"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD


@pytest.mark.parametrize("cls", [BaseConnection, SocketConnection, VISAConnection, MockConnection])
def test_every_connection_can_resync(cls):
    assert callable(getattr(cls, "resync", None))


def test_resync_no_op_returns_zero():
    # The interface is resync() -> int, a no-op default returning 0 -- not
    # just "callable". BaseConnection is abstract and cannot be instantiated
    # directly, so prove the concrete return value via MockConnection, which
    # inherits the base no-op unchanged.
    conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True})
    assert conn.resync() == 0


@pytest.mark.parametrize("cls", [BaseConnection, SocketConnection, VISAConnection, MockConnection])
def test_every_connection_can_drain_its_input(cls):
    # Separate from resync() on purpose: discarding queued bytes and aborting
    # the instrument's current operation are different requests, and a caller
    # with housekeeping to do must be able to make only the first one.
    assert callable(getattr(cls, "drain_input", None))


def test_drain_input_no_op_returns_zero():
    conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True})
    assert conn.drain_input() == 0


def test_framing_is_exported_from_the_connection_package():
    # `framing` is a public argument of BaseConnection.read_raw and of
    # Oscilloscope.read_raw, and the changelog tells subclass authors they must
    # accept it -- so the type has to be importable from the package that
    # documents it, not only from a submodule path.
    import scpi_control.connection as package

    assert "Framing" in package.__all__
    assert package.Framing is Framing


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


def test_mock_honours_size_and_block_together_on_a_genuine_block():
    # Documented on Oscilloscope.read_raw: MockConnection's BLOCK check and
    # size truncation both apply to the same read -- a genuine block still
    # gets truncated to `size`.
    conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True})
    conn.connect()
    conn.write("SCDP?")
    truncated = conn.read_raw(size=4, framing=Framing.BLOCK)
    assert truncated == conn.read_raw(framing=Framing.BLOCK)[:4]


def test_mock_block_declaration_is_enforced_even_when_size_is_given():
    # The specific claim Oscilloscope.read_raw's docstring pins for
    # MockConnection: the BLOCK check runs unconditionally, BEFORE size
    # truncation -- passing `size` does not suppress it. A call site that
    # declares the wrong wire shape must fail loudly even on a sized read.
    conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True})
    conn.connect()
    conn.write("SCDP?")
    conn.mock_raw_response = b"BM\x36\x00\x00\x00 not a block"
    with pytest.raises(exceptions.CommandError):
        conn.read_raw(size=8, framing=Framing.BLOCK)
