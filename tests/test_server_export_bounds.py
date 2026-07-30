"""Task 8: exports that cannot exhaust memory (scpi_control/server/api/scope.py).

capture.csv and /scope/waveform used to fetch a scope's ENTIRE record and
build the whole export body as one Python string/dict before ever writing a
byte to the client -- unbounded, on a deep record that is gigabytes in server
memory. This file covers the fix:

- a record above MAX_EXPORT_POINTS is refused with 413 BEFORE any waveform is
  fetched (never after a partial or full fetch);
- the 413 detail names the actual point count;
- an explicit max_points under the threshold bypasses the guard and succeeds,
  striding the fetch itself rather than pulling the oversized record anyway;
- capture.csv gained max_points, for parity with /scope/waveform;
- both responses stream rather than build their whole body in memory;
- a normal-sized CSV export is still byte-for-byte identical to the
  pre-streaming implementation.
"""

import numpy as np
import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # fastapi.testclient needs it
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.oscilloscope import Oscilloscope  # noqa: E402
from scpi_control.server.api import scope as scope_api  # noqa: E402
from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402
from scpi_control.waveform import WaveformData  # noqa: E402


@pytest.fixture()
def client(gateway_auth):
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as test_client:
        test_client.headers.update(headers)
        yield test_client
    manager.close_all()


def create_mock_session(client):
    # Default (mock=True, no model) is the legacy dialect (SDS1104X-E) --
    # deliberately unpatched, this is what exercises the record_length() is
    # None path (see TestUnknownRecordLengthProceedsUnguarded below).
    response = client.post("/api/sessions", json={"mock": True})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _fake_waveform(n=41, scale=1.0):
    """Deterministic WaveformData, independent of the mock synth's own
    nondeterminism (it evolves with elapsed time). The byte-identity proof
    below needs the exact same array fed to both the reference algorithm and
    the route under test, which a live capture cannot guarantee call to call.
    """
    t = np.arange(n, dtype=float) * 1e-6
    v = (np.sin(np.linspace(0, 6.28, n)) * scale).astype(float)
    return WaveformData(channel="C1", time=t, voltage=v, sample_rate=1e6, voltage_scale=0.5, voltage_offset=0.0)


def _reference_build_csv(captures) -> str:
    """Frozen copy of _build_csv exactly as it existed before Task 8 (a single
    string, not a generator). This is the golden reference the streaming
    rewrite must reproduce byte-for-byte for a normal-sized export -- proving
    the rewrite didn't change the transformation, not merely eyeballing it.
    """
    n = min(len(w.voltage) for _, w in captures)
    time_axis = captures[0][1].time
    header = "time_s," + ",".join("C{0}_V".format(c) for c, _ in captures)
    rows = [header]
    for i in range(n):
        rows.append("{0:.9g},{1}".format(float(time_axis[i]), ",".join("{0:.9g}".format(float(w.voltage[i])) for _, w in captures)))
    return "\n".join(rows) + "\n"


class TestByteIdentity:
    def test_normal_csv_export_is_byte_identical_to_the_pre_streaming_algorithm(self, client, monkeypatch):
        fixed = _fake_waveform(n=41)
        monkeypatch.setattr(Oscilloscope, "get_waveform", lambda self, channel, provenance=True, stride=None: fixed)
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: len(fixed.voltage))
        sid = create_mock_session(client)

        response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid))

        assert response.status_code == 200
        expected = _reference_build_csv([(1, fixed)])
        assert response.content.decode("utf-8") == expected


class TestStreamingResponseType:
    # StreamingResponse never populates Content-Length (Starlette's
    # Response.init_headers only derives it from a fully-built .body, which
    # StreamingResponse never sets) -- a black-box, client-visible signal
    # that the server did not build the whole response body in memory.

    def test_capture_csv_is_a_streaming_response(self, client):
        sid = create_mock_session(client)
        response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid))
        assert response.status_code == 200
        assert "content-length" not in response.headers

    def test_waveform_json_is_a_streaming_response(self, client):
        sid = create_mock_session(client)
        response = client.get("/api/sessions/{0}/scope/waveform?channels=1".format(sid))
        assert response.status_code == 200
        assert "content-length" not in response.headers


class TestSizeGuard:
    def test_oversized_record_is_refused_before_any_fetch(self, client, monkeypatch):
        fetched = []
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: scope_api.MAX_EXPORT_POINTS + 1)

        def spy_get_waveform(self, channel, provenance=True, stride=None):
            fetched.append(channel)
            return _fake_waveform()

        monkeypatch.setattr(Oscilloscope, "get_waveform", spy_get_waveform)
        sid = create_mock_session(client)

        response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid))

        assert response.status_code == 413
        assert fetched == [], "get_waveform ran despite the record being known to exceed MAX_EXPORT_POINTS"

    def test_413_detail_names_the_actual_point_count(self, client, monkeypatch):
        total = scope_api.MAX_EXPORT_POINTS + 12345
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: total)
        sid = create_mock_session(client)

        response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid))

        assert response.status_code == 413
        detail = response.json()["detail"]
        assert str(total) in detail
        assert "max_points={0}".format(scope_api.MAX_EXPORT_POINTS) in detail

    def test_waveform_json_also_refuses_an_oversized_record(self, client, monkeypatch):
        total = scope_api.MAX_EXPORT_POINTS + 1
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: total)
        sid = create_mock_session(client)

        response = client.get("/api/sessions/{0}/scope/waveform?channels=1".format(sid))

        assert response.status_code == 413
        assert str(total) in response.json()["detail"]


class TestExplicitMaxPointsBypassesTheGuard:
    def test_explicit_max_points_under_threshold_succeeds_on_an_oversized_record(self, client, monkeypatch):
        # The record is well above MAX_EXPORT_POINTS, but the caller has
        # explicitly bounded the export -- the 413's own suggested escape
        # hatch ("pass max_points=<n>") must actually work, and must not
        # fetch the oversized record and decimate it afterwards: the stride
        # passed to get_waveform must already reflect the requested cap.
        total = scope_api.MAX_EXPORT_POINTS + 5_000_000
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: total)
        seen_strides = []

        def fake_get_waveform(self, channel, provenance=True, stride=None):
            seen_strides.append(stride)
            return _fake_waveform(n=50)

        monkeypatch.setattr(Oscilloscope, "get_waveform", fake_get_waveform)
        sid = create_mock_session(client)

        response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1&max_points=50".format(sid))

        assert response.status_code == 200
        rows = response.text.strip().splitlines()
        assert len(rows) - 1 <= 50  # minus the header row
        assert seen_strides and seen_strides[0] is not None and seen_strides[0] > 1, "the export did not stride the fetch -- it would have pulled the full oversized record"

    def test_capture_csv_accepts_max_points(self, client, monkeypatch):
        fixed = _fake_waveform(n=200)
        monkeypatch.setattr(Oscilloscope, "get_waveform", lambda self, channel, provenance=True, stride=None: fixed)
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: len(fixed.voltage))
        sid = create_mock_session(client)

        full = client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid)).text.strip().splitlines()
        capped = client.get("/api/sessions/{0}/scope/capture.csv?channels=1&max_points=10".format(sid)).text.strip().splitlines()

        assert len(capped) - 1 <= 10
        assert len(capped) < len(full)

    def test_waveform_json_max_points_under_threshold_returns_that_many_points(self, client, monkeypatch):
        fixed = _fake_waveform(n=200)
        monkeypatch.setattr(Oscilloscope, "get_waveform", lambda self, channel, provenance=True, stride=None: fixed)
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: len(fixed.voltage))
        sid = create_mock_session(client)

        body = client.get("/api/sessions/{0}/scope/waveform?channels=1&max_points=10".format(sid)).json()

        assert len(body["channels"][0]["points"]) <= 10


class TestUnknownRecordLengthProceedsUnguarded:
    def test_default_legacy_dialect_cannot_report_record_length_and_still_exports(self, client):
        # Documented decision (see _export_stride's docstring in scope.py):
        # record_length() is None on the legacy dialect (no :ACQuire:POINts?
        # mapping in LEGACY_COMMANDS) -- the record's size cannot be verified
        # before the fetch on this dialect at all. This proceeds unstrided
        # and unguarded exactly as every export did before this task, rather
        # than refusing every legacy-dialect export outright.
        sid = create_mock_session(client)

        response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid))

        assert response.status_code == 200

    def test_record_length_is_none_for_the_default_mock_dialect(self):
        # Pins the assumption the test above relies on: if this ever stops
        # being true (e.g. legacy grows an :ACQuire:POINts? mapping), that
        # test would silently stop exercising the record_length()-is-None
        # path it claims to.
        from scpi_control.connection.mock.base import MockConnection

        instrument = Oscilloscope("mock", connection=MockConnection("mock"))
        instrument.connect()
        assert instrument.dialect == "legacy"
        assert instrument.record_length() is None
