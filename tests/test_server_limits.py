"""Resource limits: session cap and off-loop serialization (audit M47/M48)."""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.auth import TokenStore  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


@pytest.fixture()
def capped_client(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    headers = {"Authorization": "Bearer {0}".format(store.mint("tester"))}
    manager = SessionManager(max_sessions=2)
    app = create_app(manager, token_store=store)
    with TestClient(app) as client:
        client.headers.update(headers)
        yield client
    manager.close_all()


def test_sessions_beyond_the_cap_are_refused(capped_client):
    for _ in range(2):
        assert capped_client.post("/api/sessions", json={"label": "s", "mock": True}).status_code == 201
    response = capped_client.post("/api/sessions", json={"label": "s", "mock": True})
    assert response.status_code == 409
    assert "limit" in response.json()["detail"].lower()


def test_closing_a_session_frees_a_slot(capped_client):
    first = capped_client.post("/api/sessions", json={"label": "s", "mock": True}).json()["id"]
    capped_client.post("/api/sessions", json={"label": "s", "mock": True})
    assert capped_client.delete("/api/sessions/{0}".format(first)).status_code == 204
    assert capped_client.post("/api/sessions", json={"label": "s", "mock": True}).status_code == 201


def test_capture_csv_runs_off_the_event_loop(capped_client):
    # Task 8: _build_csv became a generator streamed via StreamingResponse, so
    # the row-building work is no longer a single call routed through this
    # module's run_in_threadpool -- Starlette's iterate_in_threadpool now
    # drives each next() off the event loop instead (starlette.concurrency).
    # The observable, black-box guarantee that replaces the old spy: a
    # streaming response never carries a Content-Length header (Starlette only
    # populates it from a fully-built .body, which StreamingResponse never
    # sets -- see starlette.responses.Response.init_headers).
    sid = capped_client.post("/api/sessions", json={"label": "s", "mock": True}).json()["id"]
    response = capped_client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid))
    assert response.status_code == 200
    assert "content-length" not in response.headers, "CSV export is not a streaming response"


def test_capture_waveform_runs_off_the_event_loop(capped_client):
    # The waveform JSON route is the larger payload and the motivating
    # deep-memory scenario -- it deserves the same off-loop guarantee as CSV.
    # See test_capture_csv_runs_off_the_event_loop above: Task 8 replaced the
    # single run_in_threadpool(_build_waveform_response, ...) call with a
    # streamed, per-channel generator, so the same Content-Length absence
    # check is the black-box signal that the body is never fully built.
    sid = capped_client.post("/api/sessions", json={"label": "s", "mock": True}).json()["id"]
    response = capped_client.get("/api/sessions/{0}/scope/waveform?channels=1".format(sid))
    assert response.status_code == 200
    assert "content-length" not in response.headers, "waveform export is not a streaming response"


class TestCreateAppMutualExclusionGuard:
    # LOW 4: create_app() must refuse an explicit manager combined with
    # allowed_ports/max_sessions (the latter would be silently dropped or
    # ambiguously composed otherwise). Nothing previously asserted this
    # guard exists -- it could be deleted silently and all other tests would
    # stay green.
    def test_manager_with_allowed_ports_raises(self):
        manager = SessionManager()
        try:
            with pytest.raises(ValueError):
                create_app(manager, allowed_ports=frozenset({5025}))
        finally:
            manager.close_all()

    def test_manager_with_max_sessions_raises(self):
        manager = SessionManager()
        try:
            with pytest.raises(ValueError):
                create_app(manager, max_sessions=4)
        finally:
            manager.close_all()

    def test_manager_with_stream_options_raises(self):
        manager = SessionManager()
        try:
            with pytest.raises(ValueError):
                create_app(manager, stream_max_points=5000)
            with pytest.raises(ValueError):
                create_app(manager, stream_max_fps=4.0)
        finally:
            manager.close_all()

    def test_create_app_seeds_the_manager_stream_budget(self):
        app = create_app(stream_max_points=5000, stream_max_fps=4.0)
        manager = app.state.manager
        try:
            assert manager.stream_max_points == 5000 and manager.stream_max_fps == 4.0
        finally:
            manager.close_all()
