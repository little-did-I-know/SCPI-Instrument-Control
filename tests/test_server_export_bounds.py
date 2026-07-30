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

from scpi_control.exceptions import FeatureNotSupportedError, SiglentError  # noqa: E402
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


MODERN_MODEL = "SDS824X HD"  # the modern-dialect model the rest of this branch's server tests use


def create_mock_session(client):
    # Default (mock=True, no model) is the legacy dialect (SDS1104X-E) --
    # deliberately unpatched, this is what exercises the record_length() is
    # None path (see TestUnknownRecordLengthProceedsUnguarded below).
    response = client.post("/api/sessions", json={"mock": True})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_modern_mock_session(client):
    """A MODERN-dialect mock session. Every other test in this file uses the
    default legacy mock, which is exactly the coverage gap that let a
    modern-dialect 504 through: legacy has no "get_acq_points" mapping at all,
    so record_length() returns early on _has_command and the query is never
    sent. Modern DOES map :ACQuire:POINts? -- and the mock has no response for
    it -- so this is the configuration where the query actually runs and fails.
    """
    response = client.post("/api/sessions", json={"mock": True, "model": MODERN_MODEL})
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


class TestCsvChunksAreBatched:
    # Final-review fix (Important 3): Starlette wraps a sync iterator in
    # iterate_in_threadpool, which awaits anyio.to_thread.run_sync PER ITEM,
    # and StreamingResponse sends one http.response.body message PER ITEM. One
    # row per yield therefore meant one thread round-trip and one chunked frame
    # PER SAMPLE -- 2M of each on the deep records this endpoint's memory bound
    # exists for, where the pre-streaming code did one of each in total.

    def test_rows_are_emitted_in_batches_not_one_chunk_per_row(self):
        rows = 5000
        captures = [(1, _fake_waveform(n=rows))]

        chunks = list(scope_api._build_csv(captures))

        # 1 header + ceil(5000 / CSV_ROWS_PER_CHUNK) row batches.
        assert len(chunks) == 1 + -(-rows // scope_api.CSV_ROWS_PER_CHUNK)
        assert len(chunks) < rows, "one chunk per row costs a threadpool hop and an ASGI body message per sample"

    def test_batching_changes_no_bytes(self):
        # The batch boundary must not land inside a row, or between rows
        # without its newline: the concatenation has to be identical to the
        # unbatched one, whatever the row count does modulo the batch size.
        captures = [(1, _fake_waveform(n=scope_api.CSV_ROWS_PER_CHUNK * 2 + 7))]

        assert "".join(scope_api._build_csv(captures)) == _reference_build_csv(captures)


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


class TestAFailingRecordLengthQueryDoesNotFailTheExport:
    # Final-review fix (Critical 1): _export_stride calls record_length()
    # bare, and record_length() only guarded _has_command -- it did not catch a
    # FAILING query. On a modern-dialect session whose instrument (or the mock)
    # has no answer for :ACQuire:POINts?, the query raised, run_job re-raised,
    # and the app-level handler turned it into a 504 for BOTH exports. Both
    # returned 200 before this branch. record_length() now swallows like its
    # sibling waveform_max_points() already did, so _export_stride falls into
    # its designed size_verified=False branch instead.

    def test_capture_csv_returns_200_on_a_modern_dialect_session(self, client):
        sid = create_modern_mock_session(client)

        response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid))

        assert response.status_code == 200, response.text

    def test_waveform_json_returns_200_on_a_modern_dialect_session(self, client):
        sid = create_modern_mock_session(client)

        response = client.get("/api/sessions/{0}/scope/waveform?channels=1".format(sid))

        assert response.status_code == 200, response.text

    def test_the_modern_mock_really_cannot_answer_the_record_length_query(self):
        # Pins what makes the two tests above meaningful: modern MAPS
        # :ACQuire:POINts? (unlike legacy) and the mock cannot answer it, so
        # the query is genuinely attempted and genuinely fails. If the mock
        # ever grows a handler, those tests would silently stop covering the
        # failing-query path and this one fails loudly instead.
        from scpi_control.connection.mock.base import MockConnection

        instrument = Oscilloscope("mock", connection=MockConnection("mock", idn="Siglent Technologies,{0},MOCK0001,1.0.0.0".format(MODERN_MODEL)))
        instrument.connect()
        assert instrument.dialect == "modern"
        assert instrument._has_command("get_acq_points"), "modern must map :ACQuire:POINts? -- otherwise record_length() short-circuits and no query is sent"
        with pytest.raises(SiglentError):
            instrument.query(instrument._get_command("get_acq_points"))
        assert instrument.record_length() is None, "record_length() must degrade to None on a failing query, not raise"


class TestUnverifiableOversizedExportLogsAWarning:
    # Review fix (Important 1): the unguarded legacy path had no runtime
    # signal at all when the eventual fetch turned out to be oversized after
    # the fact -- only a docstring. Prevention is impossible once the array
    # is already in memory, but the operator deserves a log line, not silence.

    def test_logs_a_warning_naming_the_actual_count_when_size_could_not_be_verified(self, client, monkeypatch, caplog):
        # MAX_EXPORT_POINTS is shrunk to keep this test fast/light -- the
        # array itself doesn't need to be huge, only larger than whatever
        # the threshold is, to reach the "turned out oversized" branch.
        monkeypatch.setattr(scope_api, "MAX_EXPORT_POINTS", 100)
        oversized = _fake_waveform(n=107)
        monkeypatch.setattr(Oscilloscope, "get_waveform", lambda self, channel, provenance=True, stride=None: oversized)
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: None)  # unverifiable dialect
        sid = create_mock_session(client)

        with caplog.at_level("WARNING", logger="scpi_control.server.api.scope"):
            response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid))

        assert response.status_code == 200  # prevention is impossible after the fact -- this still succeeds
        warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert any("107" in w and "record_length" in w for w in warnings), warnings

    def test_no_warning_when_the_unverifiable_fetch_is_actually_small(self, client, monkeypatch, caplog):
        # The warning is specifically about turning out to be oversized, not
        # about record_length() being unknown per se -- most legacy exports
        # are small and must stay silent.
        small = _fake_waveform(n=41)
        monkeypatch.setattr(Oscilloscope, "get_waveform", lambda self, channel, provenance=True, stride=None: small)
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: None)
        sid = create_mock_session(client)

        with caplog.at_level("WARNING", logger="scpi_control.server.api.scope"):
            response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid))

        assert response.status_code == 200
        assert not [r for r in caplog.records if r.levelname == "WARNING"]

    def test_no_warning_when_size_was_verified_in_advance(self, client, monkeypatch, caplog):
        # size_verified True (record_length() answered) must never trigger
        # this specific warning, even if -- hypothetically -- the fetch
        # somehow returned more than the recorded length.
        fixed = _fake_waveform(n=41)
        monkeypatch.setattr(Oscilloscope, "get_waveform", lambda self, channel, provenance=True, stride=None: fixed)
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: len(fixed.voltage))
        sid = create_mock_session(client)

        with caplog.at_level("WARNING", logger="scpi_control.server.api.scope"):
            response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid))

        assert response.status_code == 200
        assert not [r for r in caplog.records if r.levelname == "WARNING"]


class TestTransferCapTripBecomes413:
    # Review fix (Important 2): record_length() and the fetch are two
    # separate run_job calls with nothing holding the record between them, so
    # a record that changes in that window -- or an instrument whose real
    # transfer cap is smaller than assumed -- can still trip
    # ModernTransfer's single-window ceiling (FeatureNotSupportedError),
    # which subclasses SiglentError and would otherwise surface as an
    # uncaught 500. It must become a 413 instead, consistent with the
    # oversized-record refusal.

    def test_capture_csv_turns_a_transfer_cap_trip_into_413(self, client, monkeypatch):
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: 10_000)

        def raising_get_waveform(self, channel, provenance=True, stride=None):
            raise FeatureNotSupportedError(
                "Strided read of 10000 points (stride=200) exceeds this instrument's per-transfer cap of 50 points " "(:WAVeform:MAXPoint?); multi-window strided reads are not supported (test)"
            )

        monkeypatch.setattr(Oscilloscope, "get_waveform", raising_get_waveform)
        sid = create_mock_session(client)

        response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1&max_points=50".format(sid))

        assert response.status_code == 413
        detail = response.json()["detail"]
        assert "max_points" in detail
        assert "per-transfer" in detail

    def test_waveform_json_turns_a_transfer_cap_trip_into_413(self, client, monkeypatch):
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: 10_000)

        def raising_get_waveform(self, channel, provenance=True, stride=None):
            raise FeatureNotSupportedError(
                "Strided read of 10000 points (stride=200) exceeds this instrument's per-transfer cap of 50 points " "(:WAVeform:MAXPoint?); multi-window strided reads are not supported (test)"
            )

        monkeypatch.setattr(Oscilloscope, "get_waveform", raising_get_waveform)
        sid = create_mock_session(client)

        response = client.get("/api/sessions/{0}/scope/waveform?channels=1&max_points=50".format(sid))

        assert response.status_code == 413
        assert "max_points" in response.json()["detail"]


class TestDefaultPathNeverStrides:
    # Minor (export-side twin of the Task 7 guard): the guarantee that a
    # default (no max_points) export is never silently decimated currently
    # holds only by construction. Pin it directly, so a future change to the
    # `cap is None` short-circuit in _export_stride cannot regress silently.

    def test_default_path_passes_no_stride(self, client, monkeypatch):
        fixed = _fake_waveform(n=41)
        seen_strides = []

        def fake_get_waveform(self, channel, provenance=True, stride=None):
            seen_strides.append(stride)
            return fixed

        monkeypatch.setattr(Oscilloscope, "get_waveform", fake_get_waveform)
        monkeypatch.setattr(Oscilloscope, "record_length", lambda self: len(fixed.voltage))
        sid = create_mock_session(client)

        response = client.get("/api/sessions/{0}/scope/capture.csv?channels=1".format(sid))

        assert response.status_code == 200
        assert seen_strides == [None], "the default (no max_points) path must never pass a stride -- an export decimated without being asked is the failure this task must not create"
