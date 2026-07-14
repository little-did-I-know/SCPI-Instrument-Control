"""REST API tests. Skipped entirely when the [web] extra is not installed."""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # fastapi.testclient needs it; raises RuntimeError (not ImportError) without it
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


@pytest.fixture()
def client():
    manager = SessionManager()
    app = create_app(manager)
    with TestClient(app) as test_client:
        yield test_client
    manager.close_all()


def test_lists_no_sessions_initially(client):
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert response.json() == []


def test_unknown_session_is_404(client):
    response = client.get("/api/sessions/deadbeef")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] and body["detail"]


def test_unmatched_route_404_shares_error_shape(client):
    response = client.get("/api/definitely-not-a-route")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error", "detail"}


def test_wrong_method_405_shares_error_shape(client):
    response = client.delete("/api/sessions")  # only GET/POST exist on this path
    assert response.status_code == 405
    body = response.json()
    assert set(body) == {"error", "detail"}


def test_wrong_method_405_keeps_allow_header(client):
    # Fix 7: the StarletteHTTPException handler must preserve the Allow header.
    response = client.delete("/api/sessions")
    assert response.status_code == 405
    assert "allow" in {k.lower() for k in response.headers}


def test_lifespan_shutdown_closes_sessions():
    # Fix 6: leaving the app context (lifespan teardown) closes live sessions.
    manager = SessionManager()
    with TestClient(create_app(manager)) as client:
        body = client.post("/api/sessions", json={"mock": True}).json()
        session = manager.get(body["id"])
        assert session.state == "connected"
    # No explicit close_all() -> the lifespan teardown must have closed it.
    assert session.state == "closed"


def create_mock_session(client, model=None):
    payload = {"mock": True}
    if model:
        payload["model"] = model
    response = client.post("/api/sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


class TestSessionEndpoints:
    def test_create_mock_session_returns_info(self, client):
        body = create_mock_session(client)
        assert body["state"] == "connected"
        assert body["mock"] is True
        assert body["model"] == "SDS1104X-E"
        assert body["dialect"] == "legacy"
        assert body["num_channels"] == 4

    def test_create_modern_mock_by_model(self, client):
        body = create_mock_session(client, model="SDS824X HD")
        assert body["model"] == "SDS824X HD"
        assert body["dialect"] == "modern"

    def test_create_real_session_requires_address(self, client):
        response = client.post("/api/sessions", json={"mock": False})
        assert response.status_code == 400

    def test_delete_session(self, client):
        body = create_mock_session(client)
        assert client.delete("/api/sessions/" + body["id"]).status_code == 204
        assert client.delete("/api/sessions/" + body["id"]).status_code == 404
        assert client.get("/api/sessions").json() == []


def test_models_endpoint_lists_registry(client):
    response = client.get("/api/models")
    assert response.status_code == 200
    models = response.json()
    names = [m["model_name"] for m in models]
    assert "SDS1104X-E" in names and "SDS824X HD" in names
    assert names == sorted(names)
    assert {"model_name", "series", "num_channels", "bandwidth_mhz", "dialect"} <= set(models[0])


class TestScopeEndpoints:
    def _session(self, client):
        return create_mock_session(client)["id"]

    def test_get_state(self, client):
        sid = self._session(client)
        state = client.get("/api/sessions/{0}/scope/state".format(sid)).json()
        assert state["channels"]["1"]["enabled"] is True
        assert state["trigger"]["mode"] in ("AUTO", "NORM", "SINGLE", "STOP")
        assert isinstance(state["timebase"], float)

    def test_patch_channel_applies_and_returns_state(self, client):
        sid = self._session(client)
        response = client.patch("/api/sessions/{0}/scope/channels/1".format(sid), json={"voltage_scale": 0.5, "coupling": "AC"})
        assert response.status_code == 200
        ch1 = response.json()["channels"]["1"]
        assert ch1["voltage_scale"] == 0.5
        assert ch1["coupling"] == "AC"

    def test_patch_channel_invalid_coupling_is_400(self, client):
        sid = self._session(client)
        response = client.patch("/api/sessions/{0}/scope/channels/1".format(sid), json={"coupling": "BANANA"})
        assert response.status_code == 400

    def test_patch_timebase(self, client):
        sid = self._session(client)
        response = client.patch("/api/sessions/{0}/scope/timebase".format(sid), json={"timebase": 0.002})
        assert response.status_code == 200
        assert response.json()["timebase"] == 0.002

    def test_patch_trigger_mode(self, client):
        sid = self._session(client)
        response = client.patch("/api/sessions/{0}/scope/trigger".format(sid), json={"mode": "SINGLE"})
        assert response.status_code == 200
        assert response.json()["trigger"]["mode"] == "SINGLE"

    def test_run_stop_endpoints(self, client):
        sid = self._session(client)
        for op in ("run", "stop", "single", "auto"):
            response = client.post("/api/sessions/{0}/scope/{1}".format(sid, op))
            assert response.status_code == 200, (op, response.text)
            assert "run_state" in response.json()

    def test_unknown_session_scope_call_is_404(self, client):
        assert client.get("/api/sessions/nope/scope/state").status_code == 404


class TestTerminalAndMeasurements:
    def test_command_query_returns_response(self, client):
        sid = create_mock_session(client)["id"]
        response = client.post("/api/sessions/{0}/scope/command".format(sid), json={"command": "*IDN?"})
        assert response.status_code == 200
        body = response.json()
        assert body["command"] == "*IDN?"
        assert "SDS1104X-E" in body["response"]

    def test_command_write_returns_null_response(self, client):
        sid = create_mock_session(client)["id"]
        response = client.post("/api/sessions/{0}/scope/command".format(sid), json={"command": "TRMD AUTO"})
        assert response.status_code == 200
        assert response.json()["response"] is None

    def test_unknown_query_times_out_as_504(self, client):
        sid = create_mock_session(client)["id"]
        response = client.post("/api/sessions/{0}/scope/command".format(sid), json={"command": "BOGUS?"})
        assert response.status_code == 504

    def test_put_measurements_validates(self, client):
        sid = create_mock_session(client)["id"]
        ok = client.put("/api/sessions/{0}/scope/measurements".format(sid), json=[{"channel": 1, "mtype": "PKPK"}, {"channel": 2, "mtype": "FREQ"}])
        assert ok.status_code == 200
        assert ok.json()["measurements"] == [{"channel": 1, "mtype": "PKPK"}, {"channel": 2, "mtype": "FREQ"}]
        bad_type = client.put("/api/sessions/{0}/scope/measurements".format(sid), json=[{"channel": 1, "mtype": "NOPE"}])
        assert bad_type.status_code == 400
        bad_channel = client.put("/api/sessions/{0}/scope/measurements".format(sid), json=[{"channel": 9, "mtype": "PKPK"}])
        assert bad_channel.status_code == 400


class TestCapture:
    def test_capture_csv_single_channel(self, client):
        sid = create_mock_session(client)["id"]
        response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid))
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers.get("content-disposition", "")
        lines = response.text.strip().splitlines()
        assert lines[0] == "time_s,C1_V"
        assert len(lines) > 10
        first = lines[1].split(",")
        float(first[0])
        float(first[1])  # parseable numbers

    def test_capture_csv_multi_channel(self, client):
        sid = create_mock_session(client)["id"]
        response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1,2".format(sid))
        assert response.status_code == 200
        lines = response.text.strip().splitlines()
        assert lines[0] == "time_s,C1_V,C2_V"
        assert len(lines) > 10

    def test_capture_csv_bad_channels_param_is_400(self, client):
        sid = create_mock_session(client)["id"]
        assert client.get("/api/sessions/{0}/scope/capture.csv?channels=banana".format(sid)).status_code == 400


class TestDiscoverEndpoint:
    def test_discover_finds_fake_instrument(self, client, monkeypatch):
        from scpi_control.server import discovery
        from tests.test_server_discovery import FakeScpiServer

        with FakeScpiServer() as server:
            monkeypatch.setattr(discovery, "SCPI_PORT", server.port)
            response = client.get("/api/discover?cidr=127.0.0.1/32")
        assert response.status_code == 200
        entries = response.json()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["address"] == "127.0.0.1"
        assert entry["model"] == "SDS1104X-E"
        assert entry["kind"] == "scope"
        assert entry["connected"] is False

    def test_discover_invalid_cidr_is_400(self, client):
        assert client.get("/api/discover?cidr=banana").status_code == 400
        assert client.get("/api/discover?cidr=10.0.0.0/8").status_code == 400

    def test_discover_merges_connected_session_without_probing(self, client, monkeypatch):
        from scpi_control.server import discovery
        from tests.test_server_discovery import FakeScpiServer

        body = create_mock_session(client)
        session = client.app.state.manager.get(body["id"])
        session.address = "127.0.0.1"  # simulate a real networked instrument held by the gateway
        with FakeScpiServer() as server:
            monkeypatch.setattr(discovery, "SCPI_PORT", server.port)
            response = client.get("/api/discover?cidr=127.0.0.1/32")
            assert server.connections == 0  # held address must never be probed
        entries = response.json()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["connected"] is True
        assert entry["session_id"] == body["id"]
        assert entry["model"] == "SDS1104X-E"

    def test_discover_tolerates_hostname_session(self, client, monkeypatch):
        from scpi_control.server import discovery
        from tests.test_server_discovery import FakeScpiServer

        body = create_mock_session(client)
        session = client.app.state.manager.get(body["id"])
        session.address = "bench-scope.local"
        with FakeScpiServer() as server:
            monkeypatch.setattr(discovery, "SCPI_PORT", server.port)
            response = client.get("/api/discover?cidr=127.0.0.1/32")
        assert response.status_code == 200
        entries = response.json()
        addresses = [e["address"] for e in entries]
        assert "bench-scope.local" in addresses  # merged session present
        assert "127.0.0.1" in addresses  # scan result present
        assert addresses.index("127.0.0.1") < addresses.index("bench-scope.local")


class TestViewers:
    def test_new_session_reports_zero_viewers(self, client):
        body = create_mock_session(client)
        assert body["viewers"] == 0
        got = client.get("/api/sessions/{0}".format(body["id"])).json()
        assert got["viewers"] == 0

    def test_viewers_counts_stream_subscribers(self, client):
        body = create_mock_session(client)
        session = client.app.state.manager.get(body["id"])
        unsubscribe = session.subscribe(lambda message: None)
        try:
            assert session.viewers == 1
            listed = client.get("/api/sessions").json()
            assert listed[0]["viewers"] == 1
        finally:
            unsubscribe()
        assert session.viewers == 0

    def test_discover_connected_entry_includes_viewers(self, client, monkeypatch):
        from scpi_control.server import discovery
        from tests.test_server_discovery import FakeScpiServer

        body = create_mock_session(client)
        session = client.app.state.manager.get(body["id"])
        session.address = "127.0.0.1"
        with FakeScpiServer() as server:
            monkeypatch.setattr(discovery, "SCPI_PORT", server.port)
            entries = client.get("/api/discover?cidr=127.0.0.1/32").json()
        connected = [e for e in entries if e.get("connected")]
        assert connected and connected[0]["viewers"] == 0


def test_cli_parses_defaults(monkeypatch):
    import scpi_control.server.__main__ as cli

    captured = {}

    def fake_run(app, host, port, **kwargs):
        captured.update(host=host, port=port)

    monkeypatch.setattr(cli.uvicorn, "run", fake_run)
    cli.main([])
    assert captured == {"host": "127.0.0.1", "port": 8765}
    cli.main(["--host", "0.0.0.0", "--port", "9000"])
    assert captured == {"host": "0.0.0.0", "port": 9000}
