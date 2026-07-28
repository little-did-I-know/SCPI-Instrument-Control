"""The admin listener: where it binds, and that it can be switched off."""

import asyncio

import pytest

from scpi_control.server.__main__ import ADMIN_HOST, main


@pytest.fixture
def captured(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        "scpi_control.server.__main__._run_servers",
        lambda main_app, host, port, admin_app, admin_port: calls.update(host=host, port=port, admin_app=admin_app, admin_port=admin_port),
    )
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
        """Stands in for uvicorn.Server: no sockets, just should_exit/serve."""

        def __init__(self, config):
            self.config = config
            self.should_exit = False
            self.exited = False
            created.append(self)

        async def serve(self):
            if self is created[0]:
                # The main server: simulate Ctrl+C by returning right away,
                # the way uvicorn's serve() returns once it has handled
                # SIGINT and torn its own server down.
                await asyncio.sleep(0)
                return
            # The admin server: keep "running" until told to stop, exactly
            # like the real server would while waiting on should_exit.
            while not self.should_exit:
                await asyncio.sleep(0)
            self.exited = True

    monkeypatch.setattr(mod.uvicorn, "Server", FakeServer)
    monkeypatch.setattr(mod, "_QuietServer", FakeServer)

    mod._run_servers(main_app=object(), host="127.0.0.1", port=1234, admin_app=object(), admin_port=5678)

    assert len(created) == 2
    main_server, admin_server = created
    assert admin_server.should_exit is True
    assert admin_server.exited is True
