"""REST API tests. Skipped entirely when the [web] extra is not installed."""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # fastapi.testclient needs it; raises RuntimeError (not ImportError) without it
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


@pytest.fixture()
def client(gateway_auth):
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as test_client:
        test_client.headers.update(headers)  # every request in this module is now authenticated
        yield test_client
    manager.close_all()


@pytest.fixture()
def ref_client(tmp_path, gateway_auth):
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, references_dir=str(tmp_path), token_store=store)
    with TestClient(app) as test_client:
        test_client.headers.update(headers)
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


def test_lifespan_shutdown_closes_sessions(gateway_auth):
    # Fix 6: leaving the app context (lifespan teardown) closes live sessions.
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    with TestClient(create_app(manager, token_store=store)) as client:
        body = client.post("/api/sessions", json={"mock": True}, headers=headers).json()
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


class TestMeasurementsSync:
    def test_get_measurements_returns_selection(self, client):
        sid = create_mock_session(client)["id"]
        client.put("/api/sessions/{0}/scope/measurements".format(sid), json=[{"channel": 1, "mtype": "PKPK"}])
        body = client.get("/api/sessions/{0}/scope/measurements".format(sid)).json()
        assert body["measurements"] == [{"channel": 1, "mtype": "PKPK"}]


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


def test_cli_parses_defaults(tmp_path, monkeypatch):
    import scpi_control.server.__main__ as cli
    from scpi_control.server.auth import TokenStore

    captured = {}
    create_app_calls = []

    def fake_create_app(**kwargs):
        create_app_calls.append(kwargs)
        return object()

    def fake_run(app, host, port, **kwargs):
        captured.update(host=host, port=port)

    # --config-dir points at tmp_path so this never touches the developer's real
    # ~/.siglent/tokens.json; create_app is stubbed so no real ASGI app is built.
    monkeypatch.setattr(cli, "create_app", fake_create_app)
    monkeypatch.setattr(cli.uvicorn, "run", fake_run)
    cli.main(["--config-dir", str(tmp_path)])
    assert captured == {"host": "127.0.0.1", "port": 8765}
    assert isinstance(create_app_calls[0]["token_store"], TokenStore)
    cli.main(["--host", "0.0.0.0", "--port", "9000", "--config-dir", str(tmp_path)])
    assert captured == {"host": "0.0.0.0", "port": 9000}


class TestScreenshot:
    def test_screenshot_returns_png(self, client):
        sid = create_mock_session(client)["id"]
        response = client.get("/api/sessions/{0}/scope/screenshot.png".format(sid))
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert "attachment" in response.headers.get("content-disposition", "")


class TestWaveformJson:
    def test_waveform_json_full_resolution(self, client):
        sid = create_mock_session(client)["id"]
        response = client.get("/api/sessions/{0}/scope/waveform?channels=1".format(sid))
        assert response.status_code == 200
        body = response.json()
        assert len(body["channels"]) == 1
        ch = body["channels"][0]
        assert ch["channel"] == 1
        assert isinstance(ch["points"], list) and len(ch["points"]) > 0
        assert isinstance(ch["points"][0], float)
        assert ch["dt"] > 0

    def test_waveform_json_decimates_to_max_points(self, client):
        sid = create_mock_session(client)["id"]
        full = client.get("/api/sessions/{0}/scope/waveform?channels=1".format(sid)).json()["channels"][0]["points"]
        capped = client.get("/api/sessions/{0}/scope/waveform?channels=1&max_points=10".format(sid)).json()["channels"][0]["points"]
        assert len(capped) <= 10
        assert len(capped) <= len(full)

    def test_waveform_json_bad_channels_is_400(self, client):
        sid = create_mock_session(client)["id"]
        assert client.get("/api/sessions/{0}/scope/waveform?channels=banana".format(sid)).status_code == 400


class TestMath:
    def test_patch_math_sets_expression_and_enabled(self, client):
        sid = create_mock_session(client)["id"]
        response = client.patch("/api/sessions/{0}/scope/math/1".format(sid), json={"expression": "C1 - C2", "enabled": True})
        assert response.status_code == 200
        entry = [m for m in response.json() if m["n"] == 1][0]
        assert entry["expression"] == "C1 - C2"
        assert entry["enabled"] is True

    def test_get_math_returns_both_channels(self, client):
        sid = create_mock_session(client)["id"]
        client.patch("/api/sessions/{0}/scope/math/2".format(sid), json={"expression": "INTG(C1)", "enabled": True})
        body = client.get("/api/sessions/{0}/scope/math".format(sid)).json()
        assert {m["n"] for m in body} == {1, 2}
        m2 = [m for m in body if m["n"] == 2][0]
        assert m2["expression"] == "INTG(C1)" and m2["enabled"] is True

    def test_patch_math_bad_index_is_400(self, client):
        sid = create_mock_session(client)["id"]
        assert client.patch("/api/sessions/{0}/scope/math/3".format(sid), json={"enabled": True}).status_code == 400

    def test_patch_math_empty_expression_is_400(self, client):
        sid = create_mock_session(client)["id"]
        assert client.patch("/api/sessions/{0}/scope/math/1".format(sid), json={"expression": "   "}).status_code == 400


def test_allowed_windows_matches_fft_analyzer():
    from scpi_control.analysis import FFTAnalyzer
    from scpi_control.server.schemas import ALLOWED_WINDOWS

    assert ALLOWED_WINDOWS == frozenset(FFTAnalyzer.WINDOW_FUNCTIONS)


class TestSpectrumConfig:
    def test_get_returns_defaults(self, client):
        sid = create_mock_session(client)["id"]
        body = client.get("/api/sessions/{0}/scope/spectrum".format(sid)).json()
        assert body == {"enabled": False, "channel": 1, "window": "hanning", "db": True}

    def test_patch_updates_and_persists(self, client):
        sid = create_mock_session(client)["id"]
        response = client.patch("/api/sessions/{0}/scope/spectrum".format(sid), json={"enabled": True, "channel": 2, "window": "flattop", "db": False})
        assert response.status_code == 200
        assert response.json() == {"enabled": True, "channel": 2, "window": "flattop", "db": False}
        assert client.get("/api/sessions/{0}/scope/spectrum".format(sid)).json()["window"] == "flattop"

    def test_patch_unknown_window_is_400(self, client):
        sid = create_mock_session(client)["id"]
        assert client.patch("/api/sessions/{0}/scope/spectrum".format(sid), json={"window": "kaiser"}).status_code == 400

    def test_patch_bad_channel_is_400(self, client):
        sid = create_mock_session(client)["id"]
        assert client.patch("/api/sessions/{0}/scope/spectrum".format(sid), json={"channel": 9}).status_code == 400


class TestFilters:
    def test_get_returns_two_disabled_filters(self, client):
        sid = create_mock_session(client)["id"]
        body = client.get("/api/sessions/{0}/scope/filters".format(sid)).json()
        assert [f["n"] for f in body] == [1, 2]
        assert all(f["enabled"] is False and f["kind"] == "lowpass" and f["order"] == 5 for f in body)

    def test_patch_configures_and_enables(self, client):
        sid = create_mock_session(client)["id"]
        response = client.patch("/api/sessions/{0}/scope/filters/1".format(sid), json={"kind": "bandpass", "cutoff_low": 10, "cutoff_high": 100, "enabled": True})
        assert response.status_code == 200
        entry = [f for f in response.json() if f["n"] == 1][0]
        assert entry["kind"] == "bandpass" and entry["cutoff_low"] == 10 and entry["cutoff_high"] == 100 and entry["enabled"] is True

    def test_patch_bad_index_is_400(self, client):
        sid = create_mock_session(client)["id"]
        assert client.patch("/api/sessions/{0}/scope/filters/3".format(sid), json={"enabled": True}).status_code == 400

    def test_enabling_without_required_cutoff_is_400(self, client):
        sid = create_mock_session(client)["id"]
        assert client.patch("/api/sessions/{0}/scope/filters/1".format(sid), json={"enabled": True}).status_code == 400

    def test_bandpass_cutoff_order_is_400(self, client):
        sid = create_mock_session(client)["id"]
        body = {"kind": "bandpass", "cutoff_low": 100, "cutoff_high": 10, "enabled": True}
        assert client.patch("/api/sessions/{0}/scope/filters/1".format(sid), json=body).status_code == 400

    def test_nonpositive_cutoff_is_400(self, client):
        sid = create_mock_session(client)["id"]
        assert client.patch("/api/sessions/{0}/scope/filters/1".format(sid), json={"cutoff_high": 0}).status_code == 400

    def test_bad_kind_is_400(self, client):
        sid = create_mock_session(client)["id"]
        assert client.patch("/api/sessions/{0}/scope/filters/1".format(sid), json={"kind": "notch"}).status_code == 400

    def test_bad_order_is_400(self, client):
        sid = create_mock_session(client)["id"]
        assert client.patch("/api/sessions/{0}/scope/filters/1".format(sid), json={"order": 0}).status_code == 400

    def test_bad_source_is_400(self, client):
        sid = create_mock_session(client)["id"]
        assert client.patch("/api/sessions/{0}/scope/filters/1".format(sid), json={"source": 9}).status_code == 400


class TestReferences:
    def test_save_returns_the_list(self, ref_client):
        sid = create_mock_session(ref_client)["id"]
        response = ref_client.post("/api/sessions/{0}/scope/references".format(sid), json={"name": "golden", "channel": 1})
        assert response.status_code == 201
        refs = response.json()
        assert len(refs) == 1
        assert refs[0]["name"] == "golden" and refs[0]["channel"] == 1
        assert refs[0]["num_samples"] > 0

    def test_saving_an_existing_name_replaces_it(self, ref_client):
        sid = create_mock_session(ref_client)["id"]
        ref_client.post("/api/sessions/{0}/scope/references".format(sid), json={"name": "golden", "channel": 1})
        refs = ref_client.post("/api/sessions/{0}/scope/references".format(sid), json={"name": "golden", "channel": 1}).json()
        assert len(refs) == 1

    def test_activate_returns_overlay_and_get_matches(self, ref_client):
        sid = create_mock_session(ref_client)["id"]
        ref_client.post("/api/sessions/{0}/scope/references".format(sid), json={"name": "golden", "channel": 1})
        overlay = ref_client.put("/api/sessions/{0}/scope/reference".format(sid), json={"name": "golden"}).json()
        assert overlay["name"] == "golden" and overlay["channel"] == 1
        assert 0 < len(overlay["points"]) <= 2000
        assert ref_client.get("/api/sessions/{0}/scope/reference".format(sid)).json() == overlay

    def test_deactivate_clears_the_overlay(self, ref_client):
        sid = create_mock_session(ref_client)["id"]
        ref_client.post("/api/sessions/{0}/scope/references".format(sid), json={"name": "golden", "channel": 1})
        ref_client.put("/api/sessions/{0}/scope/reference".format(sid), json={"name": "golden"})
        overlay = ref_client.put("/api/sessions/{0}/scope/reference".format(sid), json={"name": None}).json()
        assert overlay["name"] is None and overlay["points"] == []

    def test_activate_unknown_is_404(self, ref_client):
        sid = create_mock_session(ref_client)["id"]
        assert ref_client.put("/api/sessions/{0}/scope/reference".format(sid), json={"name": "nope"}).status_code == 404

    def test_delete_removes_and_clears_active(self, ref_client):
        sid = create_mock_session(ref_client)["id"]
        ref_client.post("/api/sessions/{0}/scope/references".format(sid), json={"name": "golden", "channel": 1})
        ref_client.put("/api/sessions/{0}/scope/reference".format(sid), json={"name": "golden"})
        assert ref_client.delete("/api/sessions/{0}/scope/references/golden".format(sid)).status_code == 204
        assert ref_client.get("/api/sessions/{0}/scope/reference".format(sid)).json()["name"] is None
        assert ref_client.delete("/api/sessions/{0}/scope/references/golden".format(sid)).status_code == 404

    def test_empty_name_is_400(self, ref_client):
        sid = create_mock_session(ref_client)["id"]
        assert ref_client.post("/api/sessions/{0}/scope/references".format(sid), json={"name": "   ", "channel": 1}).status_code == 400

    def test_bad_channel_is_400(self, ref_client):
        sid = create_mock_session(ref_client)["id"]
        assert ref_client.post("/api/sessions/{0}/scope/references".format(sid), json={"name": "x", "channel": 9}).status_code == 400


@pytest.fixture()
def managed_client(gateway_auth):
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as test_client:
        test_client.headers.update(headers)
        yield test_client, manager
    manager.close_all()


class TestTrendLog:
    def test_start_requires_a_selection(self, client):
        sid = create_mock_session(client)["id"]
        assert client.post("/api/sessions/{0}/scope/log/start".format(sid)).status_code == 400

    def test_start_returns_status_and_double_start_conflicts(self, client):
        sid = create_mock_session(client)["id"]
        client.put("/api/sessions/{0}/scope/measurements".format(sid), json=[{"channel": 1, "mtype": "PKPK"}])
        response = client.post("/api/sessions/{0}/scope/log/start".format(sid))
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "recording"
        assert body["columns"] == [{"channel": 1, "mtype": "PKPK"}]
        assert body["row_count"] == 0 and body["max_rows"] == 86400
        assert client.post("/api/sessions/{0}/scope/log/start".format(sid)).status_code == 409

    def test_measurement_selection_is_locked_while_recording(self, client):
        sid = create_mock_session(client)["id"]
        client.put("/api/sessions/{0}/scope/measurements".format(sid), json=[{"channel": 1, "mtype": "PKPK"}])
        client.post("/api/sessions/{0}/scope/log/start".format(sid))
        assert client.put("/api/sessions/{0}/scope/measurements".format(sid), json=[]).status_code == 409
        client.post("/api/sessions/{0}/scope/log/stop".format(sid))
        assert client.put("/api/sessions/{0}/scope/measurements".format(sid), json=[]).status_code == 200

    def test_stop_is_idempotent(self, client):
        sid = create_mock_session(client)["id"]
        response = client.post("/api/sessions/{0}/scope/log/stop".format(sid))
        assert response.status_code == 200
        assert response.json()["state"] == "idle"

    def test_log_status_defaults(self, client):
        sid = create_mock_session(client)["id"]
        body = client.get("/api/sessions/{0}/scope/log".format(sid)).json()
        assert body == {"state": "idle", "started_at": None, "columns": [], "row_count": 0, "max_rows": 86400}

    def test_log_data_and_csv_from_recorded_rows(self, managed_client):
        client, manager = managed_client
        sid = create_mock_session(client)["id"]
        client.put("/api/sessions/{0}/scope/measurements".format(sid), json=[{"channel": 1, "mtype": "PKPK"}, {"channel": 2, "mtype": "FREQ"}])
        client.post("/api/sessions/{0}/scope/log/start".format(sid))
        session = manager.get(sid)
        started = session.recorder.started_at
        session.recorder.append(started + 1.0, [1.5, None])
        session.recorder.append(started + 2.0, [1.25, 50.0])

        data = client.get("/api/sessions/{0}/scope/log/data".format(sid)).json()
        assert data["columns"] == [{"channel": 1, "mtype": "PKPK"}, {"channel": 2, "mtype": "FREQ"}]
        assert len(data["rows"]) == 2
        assert data["rows"][0][1] == 1.5 and data["rows"][0][2] is None

        partial = client.get("/api/sessions/{0}/scope/log/data?since={1}".format(sid, started + 1.0)).json()
        assert len(partial["rows"]) == 1 and partial["rows"][0][2] == 50.0

        response = client.get("/api/sessions/{0}/scope/log.csv".format(sid))
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers.get("content-disposition", "")
        lines = response.text.strip().split("\n")
        assert lines[0] == "timestamp,elapsed_s,C1 PKPK,C2 FREQ"
        first = lines[1].split(",")
        assert first[1] == "1.000" and first[2] == "1.5" and first[3] == ""

    def test_csv_before_any_recording_is_404(self, client):
        sid = create_mock_session(client)["id"]
        assert client.get("/api/sessions/{0}/scope/log.csv".format(sid)).status_code == 404
