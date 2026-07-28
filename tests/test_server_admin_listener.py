"""The admin listener: where it binds, and that it can be switched off."""

import asyncio
import signal

import pytest
import uvicorn
from fastapi import FastAPI

from scpi_control.server.__main__ import ADMIN_HOST, _QuietServer, main


@pytest.fixture
def captured(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        "scpi_control.server.__main__._run_servers",
        lambda main_app, host, port, admin_app, admin_port: calls.update(host=host, port=port, admin_app=admin_app, admin_port=admin_port),
    )
    # Some of these tests use a fresh, empty tmp_path store, which opens the
    # setup screen -- conftest.py's autouse _no_real_browser fixture keeps
    # that from popping a real browser window.
    return calls


def test_the_admin_listener_binds_loopback_only(captured, tmp_path):
    # The host-only boundary IS this constant. If it ever becomes 0.0.0.0 the
    # entire admin surface -- minting and revoking access -- is exposed to the
    # LAN with no credential of any kind.
    assert ADMIN_HOST == "127.0.0.1"


def test_serving_starts_an_admin_app_by_default(captured, tmp_path):
    main(["--config-dir", str(tmp_path), "--port", "9999"])
    assert captured["admin_app"] is not None
    assert captured["admin_port"] == 8766


def test_admin_port_is_configurable(captured, tmp_path):
    main(["--config-dir", str(tmp_path), "--admin-port", "9100"])
    assert captured["admin_port"] == 9100


def test_no_admin_starts_only_the_main_listener(captured, tmp_path):
    main(["--config-dir", str(tmp_path), "--no-admin"])
    assert captured["admin_app"] is None


def test_there_is_no_admin_host_flag(tmp_path):
    # Deliberate: the only knob is the port. A host flag would let someone bind
    # the admin surface wide, which no amount of documentation would undo.
    with pytest.raises(SystemExit):
        main(["--config-dir", str(tmp_path), "--admin-host", "0.0.0.0"])


def test_port_colliding_with_admin_port_exits_cleanly(captured, tmp_path):
    # Without this check, --port and --admin-port landing on the same number
    # fails deep inside uvicorn's socket bind with a bare traceback instead of
    # a sentence explaining the operator's typo.
    with pytest.raises(SystemExit):
        main(["--config-dir", str(tmp_path), "--port", "8766"])


def test_port_colliding_with_admin_port_is_fine_under_no_admin(captured, tmp_path):
    # The collision only matters when the admin listener is actually going to
    # start on that port.
    main(["--config-dir", str(tmp_path), "--port", "8766", "--no-admin"])
    assert captured["port"] == 8766
    assert captured["admin_app"] is None


# --- Ctrl+C: both servers actually stop -------------------------------------
#
# The tests above cover binding and flags but not the thing most likely to be
# quietly wrong: two uvicorn servers sharing one event loop, where only the
# main one installs signal handlers. If the shutdown wiring in _run_servers is
# missing or backwards, Ctrl+C stops one server while the other keeps the
# process alive -- a bug that never shows up in a "does it start" test. This
# drives the real _run_servers with fake Server-like objects (no real socket
# binding) standing in for uvicorn.Server, so the exact shutdown-propagation
# logic in _serve_both runs for real.


@pytest.mark.timeout(10)
def test_main_server_returning_stops_the_admin_server_too(monkeypatch):
    from scpi_control.server import __main__ as mod

    created = []

    class FakeServer:
        """Stands in for uvicorn.Server: no sockets, just should_exit/serve/run."""

        def __init__(self, config):
            self.config = config
            self.should_exit = False
            self.exited = False
            self.ran = False
            created.append(self)

        def run(self, sockets=None):
            # Real uvicorn.Server.run() is asyncio.run(self.serve(...)) plus the
            # event-loop selection this fake has no use for. Keeping the
            # self.serve() indirection is the point: _run_servers substitutes
            # its own serve() on the instance, so driving the pair through
            # run() is what proves the substitution actually reaches it.
            self.ran = True
            return asyncio.run(self.serve(sockets=sockets))

        async def serve(self, sockets=None):
            if self is created[0]:
                # The main server: simulate Ctrl+C by returning right away,
                # the way uvicorn's serve() returns once it has handled
                # SIGINT and torn its own server down.
                await asyncio.sleep(0)
                return
            # The admin server: keep "running" until told to stop, exactly
            # like the real server would while waiting on should_exit. Bounded
            # rather than an unconditional while loop: a missing should_exit
            # propagation then fails in milliseconds with a clear message
            # instead of hanging the test session (the @pytest.mark.timeout
            # above is only a backstop).
            for _ in range(1000):
                if self.should_exit:
                    break
                await asyncio.sleep(0)
            else:
                raise AssertionError("should_exit was never set")
            # One more yield before marking exited: if _run_servers stopped
            # awaiting this task after setting should_exit, asyncio.run's own
            # cleanup would cancel it while it's asleep here, and exited would
            # never become True. That turns "forgot to await admin_task" into
            # a real assertion failure instead of passing by accident.
            await asyncio.sleep(0.05)
            self.exited = True

    monkeypatch.setattr(mod.uvicorn, "Server", FakeServer)
    monkeypatch.setattr(mod, "_QuietServer", FakeServer)

    # The main host deliberately differs from ADMIN_HOST so the config
    # assertions below can tell "the admin server got its own host" apart
    # from "it got whatever host the main server got".
    mod._run_servers(main_app=object(), host="0.0.0.0", port=1234, admin_app=object(), admin_port=5678)

    assert len(created) == 2
    main_server, admin_server = created
    # The pair must be driven by the main server's own run(): that is the only
    # thing in either uvicorn generation that selects the event loop
    # implementation, and the --no-admin path gets it for free. A revert to a
    # bare asyncio.run() here would still pass every assertion below while
    # silently putting the default path on a different loop than --no-admin.
    assert main_server.ran is True
    assert admin_server.ran is False
    assert admin_server.should_exit is True
    assert admin_server.exited is True
    # The line that decides the security boundary: uvicorn.Config(admin_app,
    # host=ADMIN_HOST, ...). If that ever regresses to host=host, this is the
    # only thing in the suite that would notice.
    assert admin_server.config.host == ADMIN_HOST
    assert main_server.config.host == "0.0.0.0"


def test_the_admin_server_leaves_signal_handling_alone():
    # The brief's original approach (assigning install_signal_handlers) was a
    # silent no-op on uvicorn 0.34.3, which captures signals through a context
    # manager instead. This asserts the override actually overrides
    # something, so a future uvicorn that restructures signal capture fails
    # here rather than leaving both servers fighting over SIGINT.
    assert "capture_signals" in vars(uvicorn.Server)
    handler = signal.getsignal(signal.SIGINT)
    server = _QuietServer(uvicorn.Config(FastAPI(), host="127.0.0.1", port=0))
    with server.capture_signals():
        assert signal.getsignal(signal.SIGINT) is handler
    assert signal.getsignal(signal.SIGINT) is handler
