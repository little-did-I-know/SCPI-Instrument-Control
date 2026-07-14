"""REST API tests. Skipped entirely when the [web] extra is not installed."""

import pytest

fastapi = pytest.importorskip("fastapi")
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
