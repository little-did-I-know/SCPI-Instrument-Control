"""VISAConnection must honour the same contract SocketConnection does.

Backend review 2026-07-31, High-4. The file contained ZERO lock references
(base.py:23-24 requires the reentrant lock across compound exchanges), read()
and read_raw() leaked raw VisaIOError while write()/query() translated it, a
failed connect left _resource set (so is_connected reported True) and leaked
the ResourceManager, and read_termination="\\n" stayed in force for binary
reads, where a 0x0A inside a waveform ends the read.

NOTE ON EVIDENCE: there is no VISA instrument here and pyvisa is not installed,
so these tests pin OUR contract against a stub resource. Nothing here is
confirmed against instrument behaviour, and no comment in the module may imply
otherwise.

The stub matters: with pyvisa absent the module-level name is None, so patching
PYVISA_AVAILABLE alone makes every error path die with AttributeError instead of
the behaviour under test. The existing contract tests only get away with it
because they never touch an error path.
"""

import types
from unittest.mock import MagicMock, patch

import pytest

from scpi_control import exceptions
from scpi_control.connection.framing import Framing


class FakeVisaIOError(Exception):
    def __init__(self, error_code=-1073807339, message="VI_ERROR_TMO: Timeout expired"):
        super().__init__(message)
        self.error_code = error_code


def _stub_pyvisa():
    """A stand-in pyvisa module with just the surface visa_connection touches."""
    module = types.ModuleType("pyvisa")
    module.errors = types.SimpleNamespace(VisaIOError=FakeVisaIOError)
    module.constants = types.SimpleNamespace(
        StatusCode=types.SimpleNamespace(error_timeout=-1073807339), Parity=types.SimpleNamespace(none=0), StopBits=types.SimpleNamespace(one=10), ControlFlow=types.SimpleNamespace(none=0)
    )
    module.ResourceManager = MagicMock()
    return module


@pytest.fixture
def visa():
    """Yield a VISAConnection class with a stub pyvisa injected."""
    from scpi_control.connection import visa_connection as module

    stub = _stub_pyvisa()
    with patch.object(module, "pyvisa", stub), patch.object(module, "PYVISA_AVAILABLE", True):
        yield module, stub


def _connected(module, stub):
    conn = module.VISAConnection("USB0::0x1234::0x5678::SN::INSTR")
    resource = MagicMock()
    stub.ResourceManager.return_value.open_resource.return_value = resource
    conn.connect()
    return conn, resource


def _serve(payload, watcher=None):
    """A read side effect that hands out `payload`, then times out.

    Fits either primitive: called with a count (read_bytes) it takes that many
    bytes, called with none (read_raw) it takes everything left, standing in
    for a read to END. A finished VISA read raises a timeout rather than
    returning b"" -- there is no peer-close to observe on a USB/GPIB session --
    so that is what this does once the payload runs out. `watcher` is called
    with no arguments on every read, for tests that need to observe state from
    inside the call.
    """
    remaining = [payload]

    def read(count=None, *args, **kwargs):
        if watcher is not None:
            watcher()
        if not remaining[0]:
            raise FakeVisaIOError()
        if count is None:
            head, remaining[0] = remaining[0], b""
        else:
            head, remaining[0] = remaining[0][:count], remaining[0][count:]
        return head

    return read


def _serve_session(resource, payload, watcher=None):
    """Serve one payload across BOTH read primitives, from one buffer.

    Lets a test watch the transport switch primitives part-way through a
    response without the same bytes being handed out twice -- and means
    neither primitive is left as a bare MagicMock handing back an object that
    is not bytes.
    """
    reader = _serve(payload, watcher=watcher)
    resource.read_bytes.side_effect = reader
    resource.read_raw.side_effect = reader


# A minimal definite-length block: '#1' + one length digit + zero payload bytes.
TINY_BLOCK = b"#10"


class TestLocking:
    @pytest.mark.parametrize("method,args", [("write", ("*IDN?",)), ("query", ("*IDN?",)), ("read", ()), ("read_raw", ())])
    def test_exchanges_hold_the_lock(self, visa, method, args):
        module, stub = visa
        conn, resource = _connected(module, stub)
        held = []
        resource.write.side_effect = lambda *a, **k: held.append(conn.lock._is_owned())
        resource.query.side_effect = lambda *a, **k: held.append(conn.lock._is_owned()) or "x"
        resource.read.side_effect = lambda *a, **k: held.append(conn.lock._is_owned()) or "x"
        # read_raw() reads through the framing reader, so the observable call is
        # read_bytes, not read_raw.
        resource.read_bytes.side_effect = _serve(TINY_BLOCK, watcher=lambda: held.append(conn.lock._is_owned()))
        getattr(conn, method)(*args)
        assert held and all(held), f"{method}() ran without holding the connection lock"


class TestErrorTranslation:
    @pytest.mark.parametrize("method,args", [("read", ()), ("read_raw", ())])
    def test_timeouts_are_translated(self, visa, method, args):
        module, stub = visa
        conn, resource = _connected(module, stub)
        resource.read.side_effect = FakeVisaIOError()
        resource.read_raw.side_effect = FakeVisaIOError()
        resource.read_bytes.side_effect = FakeVisaIOError()
        with pytest.raises(exceptions.SiglentTimeoutError):
            getattr(conn, method)(*args)

    def test_non_timeout_errors_become_connection_errors(self, visa):
        module, stub = visa
        conn, resource = _connected(module, stub)
        resource.read.side_effect = FakeVisaIOError(error_code=-1073807194, message="VI_ERROR_CONN_LOST")
        with pytest.raises(exceptions.SiglentConnectionError):
            conn.read()

    def test_a_timeout_marks_the_session_desynced(self, visa):
        # Mirrors SocketConnection: an abandoned read leaves the session
        # position unknown, and the next send has to clear it.
        module, stub = visa
        conn, resource = _connected(module, stub)
        resource.read.side_effect = FakeVisaIOError()
        with pytest.raises(exceptions.SiglentTimeoutError):
            conn.read()
        assert conn._desynced is True


class TestConnectCleanup:
    def test_a_failure_after_open_does_not_report_connected(self, visa):
        module, stub = visa
        conn = module.VISAConnection("USB0::0x1234::0x5678::SN::INSTR")
        resource = MagicMock()
        type(resource).timeout = property(lambda self: 0, lambda self, value: (_ for _ in ()).throw(FakeVisaIOError(error_code=-1, message="cannot set timeout")))
        stub.ResourceManager.return_value.open_resource.return_value = resource
        with pytest.raises(exceptions.SiglentConnectionError):
            conn.connect()
        assert conn.is_connected is False
        assert conn._resource is None
        assert conn._resource_manager is None
        resource.close.assert_called_once()

    def test_connecting_twice_does_not_open_a_second_resource(self, visa):
        module, stub = visa
        conn, _ = _connected(module, stub)
        conn.connect()
        assert stub.ResourceManager.return_value.open_resource.call_count == 1

    def test_disconnect_releases_both_handles(self, visa):
        module, stub = visa
        conn, resource = _connected(module, stub)
        manager = stub.ResourceManager.return_value
        conn.disconnect()
        resource.close.assert_called_once()
        manager.close.assert_called_once()
        assert conn.is_connected is False
        assert conn._resource is None
        assert conn._resource_manager is None


class TestBinaryReads:
    def test_termination_is_disabled_for_a_binary_read_and_restored(self, visa):
        module, stub = visa
        conn, resource = _connected(module, stub)
        seen = []
        # A declared STREAM has no length to read to, so the read primitive is
        # read_raw (read-to-END), not the fixed-length read_bytes -- see
        # test_a_headerless_read_does_not_over_demand_a_fixed_length.
        _serve_session(resource, b"#3012", watcher=lambda: seen.append(resource.read_termination))
        conn.read_raw(framing=Framing.STREAM)
        assert seen and all(value is None for value in seen), "read_termination must be disabled while reading binary"
        assert resource.read_termination == "\n"
        assert resource.timeout == int(conn.timeout * 1000)

    def test_termination_is_restored_when_the_binary_read_fails(self, visa):
        module, stub = visa
        conn, resource = _connected(module, stub)
        resource.read_raw.side_effect = FakeVisaIOError(error_code=-1073807194, message="VI_ERROR_CONN_LOST")
        resource.read_bytes.side_effect = FakeVisaIOError(error_code=-1073807194, message="VI_ERROR_CONN_LOST")
        with pytest.raises(exceptions.SiglentConnectionError):
            conn.read_raw(framing=Framing.STREAM)
        assert resource.read_termination == "\n"
        assert resource.timeout == int(conn.timeout * 1000)

    @pytest.mark.parametrize("framing", [Framing.STREAM, Framing.AUTO])
    def test_a_headerless_read_does_not_over_demand_a_fixed_length(self, visa, framing):
        # pyvisa's read_bytes(count) loops until it holds `count` bytes and
        # raises on timeout, discarding the partial read (pyvisa docs,
        # MessageBasedResource.read_bytes). Asking it for a 4096-byte chunk of
        # a response with no declared length is therefore the same over-demand
        # this task removed from query_binary. A VISA session ends its messages
        # with END/EOI, so a headerless read uses read_raw() instead.
        module, stub = visa
        conn, resource = _connected(module, stub)
        _serve_session(resource, b"BM\x36\x00\x00\x00 no header here")
        assert conn.read_raw(framing=framing) == b"BM\x36\x00\x00\x00 no header here"
        # AUTO still probes byte-by-byte until it can rule a header out; what it
        # must never do is ask for a fixed length it has no reason to expect.
        assert all(call.args[0] == 1 for call in resource.read_bytes.call_args_list)

    def test_a_declared_stream_does_not_shorten_the_first_read(self, visa):
        # Only the idle read that proves a response ENDED may be cut short.
        # A declared STREAM has not seen a byte yet when it starts, so the
        # instrument still gets the full configured timeout to answer in.
        module, stub = visa
        conn, resource = _connected(module, stub)
        seen = []
        _serve_session(resource, b"payload", watcher=lambda: seen.append(resource.timeout))
        conn.read_raw(framing=Framing.STREAM)
        assert seen[0] == int(conn.timeout * 1000)

    def test_a_headerless_auto_read_shortens_only_the_idle_tail(self, visa):
        # The mirror image: AUTO rules out a header only after bytes have
        # arrived, so from that point the wait is just proof the response
        # ended -- and that wait is the short one.
        module, stub = visa
        conn, resource = _connected(module, stub)
        seen = []
        _serve_session(resource, b"BM\x36\x00\x00\x00 no header here", watcher=lambda: seen.append(resource.timeout))
        conn.read_raw(framing=Framing.AUTO)
        assert seen[0] == int(conn.timeout * 1000)
        assert seen[-1] == module._IDLE_DRAIN_TIMEOUT_MS
        assert resource.timeout == int(conn.timeout * 1000), "the shortened timeout must not outlive the read"

    def test_query_binary_does_not_demand_exactly_max_bytes(self, visa):
        module, stub = visa
        conn, resource = _connected(module, stub)
        resource.read_bytes.side_effect = _serve(b"#3012" + b"0123456789ab")
        assert conn.query_binary("C1:WF? DAT2", max_bytes=1_000_000).startswith(b"#3012")
        # The bug: read_bytes(1_000_000) demands exactly that many bytes and
        # blocks the whole timeout before raising, after the data arrived.
        assert all(call.args[0] < 1_000_000 for call in resource.read_bytes.call_args_list)

    def test_query_binary_rejects_a_response_over_the_ceiling(self, visa):
        module, stub = visa
        conn, resource = _connected(module, stub)
        resource.read_bytes.side_effect = _serve(b"#3012" + b"0123456789ab")
        with pytest.raises(exceptions.CommandError):
            conn.query_binary("C1:WF? DAT2", max_bytes=8)


class TestResync:
    def test_resync_prefers_a_device_clear(self, visa):
        module, stub = visa
        conn, resource = _connected(module, stub)
        conn.resync()
        resource.clear.assert_called_once()

    def test_resync_drains_when_the_resource_cannot_clear(self, visa):
        # Pins OUR drain loop -- read whole messages, count them, stop on the
        # first error -- and nothing about pyvisa. The count is a floor by
        # design: a message the instrument never terminates is discarded
        # uncounted, which _drain's docstring says outright.
        module, stub = visa
        conn, resource = _connected(module, stub)
        del resource.clear  # a resource type that exposes no device clear
        resource.read_raw.side_effect = _serve(b"stale bytes")
        assert conn.resync() == len(b"stale bytes")
        assert conn._desynced is False
        # The drain's short timeout and disabled terminator are borrowed, not kept.
        assert resource.timeout == int(conn.timeout * 1000)
        assert resource.read_termination == "\n"

    def test_write_resyncs_before_sending_when_desynced(self, visa):
        module, stub = visa
        conn, resource = _connected(module, stub)
        conn._desynced = True
        conn.write("*RST")
        resource.clear.assert_called_once()
        assert conn._desynced is False

    def test_query_resyncs_before_sending_when_desynced(self, visa):
        module, stub = visa
        conn, resource = _connected(module, stub)
        resource.query.return_value = "x"
        conn._desynced = True
        conn.query("*IDN?")
        resource.clear.assert_called_once()
        assert conn._desynced is False
