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


def test_capture_csv_runs_off_the_event_loop(capped_client, monkeypatch):
    calls = []
    import scpi_control.server.api.scope as scope_api

    original = scope_api.run_in_threadpool

    async def spy(fn, *args, **kwargs):
        calls.append(getattr(fn, "__name__", repr(fn)))
        return await original(fn, *args, **kwargs)

    monkeypatch.setattr(scope_api, "run_in_threadpool", spy)
    sid = capped_client.post("/api/sessions", json={"label": "s", "mock": True}).json()["id"]
    assert capped_client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid)).status_code == 200
    # Name the specific function: asserting the list is merely non-empty would
    # pass on any unrelated threadpool call in this module.
    assert "_build_csv" in calls, "CSV serialization still runs on the event loop"


def test_capture_waveform_runs_off_the_event_loop(capped_client, monkeypatch):
    # The waveform JSON route is the larger payload and the motivating
    # deep-memory scenario -- it deserves the same off-loop guarantee as CSV.
    calls = []
    import scpi_control.server.api.scope as scope_api

    original = scope_api.run_in_threadpool

    async def spy(fn, *args, **kwargs):
        calls.append(getattr(fn, "__name__", repr(fn)))
        return await original(fn, *args, **kwargs)

    monkeypatch.setattr(scope_api, "run_in_threadpool", spy)
    sid = capped_client.post("/api/sessions", json={"label": "s", "mock": True}).json()["id"]
    assert capped_client.get("/api/sessions/{0}/scope/waveform?channels=1".format(sid)).status_code == 200
    # Name the specific function: asserting the list is merely non-empty would
    # pass on any unrelated threadpool call in this module.
    assert "_build_waveform_response" in calls, "waveform serialization still runs on the event loop"


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
