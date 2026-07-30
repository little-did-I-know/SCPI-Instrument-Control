# scpi_control/server/api/scope.py
import json
import logging
from dataclasses import replace
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse, Response, StreamingResponse

from scpi_control.exceptions import FeatureNotSupportedError, InvalidParameterError
from scpi_control.server.api.commands import send_command_for
from scpi_control.server.api.sessions import require_kind, require_session, run_job
from scpi_control.server.ownership import require_owner
from scpi_control.server.schemas import (
    ALLOWED_COUPLING,
    ALLOWED_FILTER_KINDS,
    ALLOWED_MEASUREMENTS,
    ALLOWED_WINDOWS,
    ChannelPatch,
    CommandIn,
    FilterPatch,
    MathPatch,
    MeasurementItem,
    ReferenceCreate,
    ReferencePut,
    SpectrumPatch,
    TimebasePatch,
    TriggerPatch,
)
from scpi_control.server.sessions import InstrumentSession, SessionError, read_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scope"])

# Safety rail against an export exhausting server memory, not a tuning knob --
# no CLI flag or config file for this. A record above it is refused with 413
# BEFORE it is fetched (see _export_stride); it is never silently decimated.
MAX_EXPORT_POINTS = 2_000_000


def _parse_channel_list(channels: str) -> List[int]:
    try:
        channel_list = sorted({int(c) for c in channels.split(",") if c.strip()})
    except ValueError:
        raise InvalidParameterError("channels must be a comma-separated list of integers")
    if not channel_list:
        raise InvalidParameterError("no channels requested")
    return channel_list


async def _export_stride(session, max_points: int) -> Tuple[Optional[int], bool]:
    """Decide the fetch stride for an export, refusing an unbounded one before any fetch happens.

    record_length() (:ACQuire:POINts?) is queried BEFORE get_waveform is ever
    called, so an oversized record is refused before a single sample crosses
    the wire -- never after building (or half-building) a response.

    Returns (stride, size_verified). size_verified is False when
    record_length() itself returned None -- dialects with no :ACQuire:POINts?
    mapping (the legacy dialect is one -- see scpi_commands.py's
    LEGACY_COMMANDS, which has no "get_acq_points" entry). There the record's
    size cannot be verified before the fetch at all. This proceeds unstrided
    and unguarded on those dialects, exactly as every export did before this
    task, rather than refusing every legacy-dialect export outright -- that
    would be a blanket regression for every user on those models, not a
    safety improvement, since they would have no way to learn their own
    record size to work around it. This is a disclosed, accepted gap, not a
    silent guess -- callers use size_verified to log a post-fetch warning
    when the eventual fetch turns out to have been oversized after all (see
    _warn_if_export_was_unverifiable_and_oversized below), since prevention
    is no longer possible once size_verified is False.

    When decimation IS needed (an explicit max_points below the actual record
    size), the stride is sized against whichever is smaller: the caller's own
    max_points, or the instrument's own per-transfer cap (:WAVeform:MAXPoint?,
    via waveform_max_points()) -- mirrors ScopeAdapter.poll's sizing
    (server/adapters.py) so a strided export cannot trip ModernTransfer's
    single-window ceiling (FeatureNotSupportedError) by construction for a
    *stable* record. record_length() and the later get_waveform() fetch are
    two separate run_job calls with nothing holding the record between them,
    so a record that grows in that window can still trip the real ceiling --
    callers must catch FeatureNotSupportedError around the fetch and turn it
    into a 413 rather than let it become an uncaught 500 (see
    _reraise_transfer_cap_trip_as_413 below).
    """
    cap = max_points if max_points and max_points > 0 else None
    total = await run_job(session, lambda scope: scope.record_length())
    if total is None:
        return None, False
    if total > MAX_EXPORT_POINTS and (cap is None or cap > MAX_EXPORT_POINTS):
        raise HTTPException(
            status_code=413,
            detail="record holds {0} points, exceeding MAX_EXPORT_POINTS ({1}); pass max_points={1} to proceed with a decimated export".format(total, MAX_EXPORT_POINTS),
        )
    if cap is None or total <= cap:
        return None, True
    transfer_cap = await run_job(session, lambda scope: scope.waveform_max_points())
    limit = min(cap, transfer_cap) if transfer_cap else cap
    return max(1, -(-total // limit)), True


def _warn_if_export_was_unverifiable_and_oversized(captures, size_verified: bool) -> None:
    """Log once the fetch's actual size is known, on a dialect that could not
    verify it in advance (record_length() returned None -- size_verified is
    False). Prevention is impossible at this point: the array is already in
    memory. But an operator whose gateway runs out of memory deserves a log
    line explaining why, not silence -- silent degradation on this branch has
    already cost an hour of diagnosis once (Task 6).
    """
    if size_verified:
        return
    for channel, data in captures:
        n = len(data.voltage)
        if n > MAX_EXPORT_POINTS:
            logger.warning(
                "export fetched %d points on channel %s, exceeding MAX_EXPORT_POINTS (%d); "
                "this dialect could not report record_length() in advance, so the size could not be checked before the fetch",
                n,
                channel,
                MAX_EXPORT_POINTS,
            )


def _reraise_transfer_cap_trip_as_413(exc: FeatureNotSupportedError) -> HTTPException:
    """Translate a strided fetch's single-window ceiling trip into a 413.

    FeatureNotSupportedError subclasses SiglentError, which the app-level
    handler maps to a plain 500 -- indistinguishable from an unrelated
    instrument fault, and not machine-actionable the way the oversized-record
    413 above is. This keeps both refusals on the same status: "this export
    is too big, here is what would work," not two different statuses for the
    same operator-facing problem.
    """
    return HTTPException(
        status_code=413,
        detail="export exceeded this instrument's per-transfer capability while fetching ({0}); pass a smaller max_points and retry".format(exc),
    )


async def mutate(session: InstrumentSession, fn: Callable) -> dict:
    """Run a mutation, then read + broadcast + return the fresh state."""
    await run_job(session, fn)
    state = await run_job(session, read_state)
    session.publish({"type": "state", "state": state})
    return state


@router.get("/sessions/{session_id}/scope/state")
async def get_state(session_id: str, request: Request):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    return await run_job(session, read_state)


@router.patch("/sessions/{session_id}/scope/channels/{channel}")
async def patch_channel(session_id: str, channel: int, body: ChannelPatch, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")
    if body.coupling is not None and body.coupling.upper() not in ALLOWED_COUPLING:
        raise InvalidParameterError("invalid coupling: {0}".format(body.coupling))

    def apply(scope):
        ch = scope.get_channel(channel)
        if ch is None:
            raise InvalidParameterError("channel {0} not available".format(channel))
        if body.enabled is not None:
            ch.enabled = body.enabled
        if body.voltage_scale is not None:
            ch.voltage_scale = body.voltage_scale
        if body.voltage_offset is not None:
            ch.voltage_offset = body.voltage_offset
        if body.coupling is not None:
            ch.coupling = body.coupling.upper()
        if body.probe_ratio is not None:
            ch.probe_ratio = body.probe_ratio

    return await mutate(session, apply)


@router.patch("/sessions/{session_id}/scope/timebase")
async def patch_timebase(session_id: str, body: TimebasePatch, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")

    def apply(scope):
        scope.timebase = body.timebase

    return await mutate(session, apply)


@router.patch("/sessions/{session_id}/scope/trigger")
async def patch_trigger(session_id: str, body: TriggerPatch, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")

    def apply(scope):
        trig = scope.trigger
        if body.mode is not None:
            trig.mode = body.mode.upper()
        if body.source is not None:
            trig.source = body.source
        if body.level is not None:
            trig.level = body.level
        if body.slope is not None:
            trig.slope = body.slope.upper()
        if body.coupling is not None:
            trig.coupling = body.coupling.upper()

    return await mutate(session, apply)


@router.post("/sessions/{session_id}/scope/command")
async def send_command(session_id: str, body: CommandIn, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")
    return await send_command_for(session, body.command)


@router.put("/sessions/{session_id}/scope/measurements")
async def put_measurements(session_id: str, body: List[MeasurementItem], request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")
    if session.adapter.recorder.state == "recording":
        raise SessionError("measurement selection is locked while recording")
    for item in body:
        if item.mtype.upper() not in ALLOWED_MEASUREMENTS:
            raise InvalidParameterError("unknown measurement type: {0}".format(item.mtype))
        if not 1 <= item.channel <= max(1, session.num_channels):
            raise InvalidParameterError("channel {0} out of range".format(item.channel))
    session.adapter.set_measurements([(item.channel, item.mtype.upper()) for item in body], session.publish)
    return {"measurements": [{"channel": c, "mtype": m} for c, m in session.adapter.measurements]}


@router.get("/sessions/{session_id}/scope/measurements")
async def get_measurements(session_id: str, request: Request):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    return {"measurements": [{"channel": c, "mtype": m} for c, m in session.adapter.measurements]}


CSV_ROWS_PER_CHUNK = 2000


def _build_csv(captures, max_points: Optional[int] = None):
    """Yield CSV lines lazily so the server never holds the whole body in memory.

    captures: list of (channel:int, WaveformData). Align to the shortest.
    max_points additionally decimates the emitted rows client-side, on top of
    whatever the fetch stride already achieved -- a safety net for dialects
    that ignore the stride argument outright (see _export_stride), so the
    row count is capped regardless of dialect.

    When max_points is None this reproduces the pre-streaming implementation's
    output byte-for-byte: joining the same rows with "\\n" and a single
    trailing newline is exactly what "\\n".join(rows) + "\\n" produced.

    Rows are yielded in batches of CSV_ROWS_PER_CHUNK, not one per row.
    Starlette wraps a sync iterator in iterate_in_threadpool, which awaits
    anyio.to_thread.run_sync PER ITEM, and StreamingResponse sends one
    http.response.body message PER ITEM -- so a 2,000,000-point export yielding
    row by row would do 2M thread round-trips and 2M chunked frames, where the
    pre-streaming code did one run_in_threadpool and one body. That is an
    enormous throughput cost on exactly the deep records this endpoint's
    memory bound exists for. Batching is byte-transparent: the concatenation
    of the emitted strings is unchanged, which
    tests/test_server_export_bounds.py::TestByteIdentity pins against a frozen
    copy of the pre-streaming algorithm.
    """
    n = min(len(w.voltage) for _, w in captures)
    time_axis = captures[0][1].time
    step = 1
    if max_points is not None and max_points > 0 and n > max_points:
        step = -(-n // max_points)  # ceiling division keeps row count <= max_points
    header = "time_s," + ",".join("C{0}_V".format(c) for c, _ in captures)
    yield header + "\n"
    buf: List[str] = []
    for i in range(0, n, step):
        buf.append("{0:.9g},{1}\n".format(float(time_axis[i]), ",".join("{0:.9g}".format(float(w.voltage[i])) for _, w in captures)))
        if len(buf) >= CSV_ROWS_PER_CHUNK:
            yield "".join(buf)
            buf = []
    if buf:
        yield "".join(buf)


@router.get("/sessions/{session_id}/scope/capture.csv")
async def capture_csv(session_id: str, request: Request, channels: str = "1", max_points: int = 0):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    channel_list = _parse_channel_list(channels)
    stride, size_verified = await _export_stride(session, max_points)
    cap = max_points if max_points > 0 else None

    def capture(scope):
        return [(c, scope.get_waveform(c, stride=stride)) for c in channel_list]

    try:
        captures = await run_job(session, capture)
    except FeatureNotSupportedError as exc:
        raise _reraise_transfer_cap_trip_as_413(exc) from exc
    _warn_if_export_was_unverifiable_and_oversized(captures, size_verified)
    filename = "capture_{0}_C{1}.csv".format(session.id, "-".join(str(c) for c in channel_list))
    return StreamingResponse(_build_csv(captures, cap), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="{0}"'.format(filename)})


@router.get("/sessions/{session_id}/scope/screenshot.png")
async def screenshot(session_id: str, request: Request):
    session = require_session(request, session_id)
    require_kind(session, "scope")

    def grab(scope):
        import io

        image = scope.screen_capture.get_screenshot_pil()
        buf = io.BytesIO()
        image.save(buf, "PNG")
        return buf.getvalue()

    png = await run_job(session, grab)
    filename = "screenshot_{0}.png".format(session.id)
    return Response(content=png, media_type="image/png", headers={"Content-Disposition": 'attachment; filename="{0}"'.format(filename)})


def _stream_waveform_json(captures, max_points):
    """Yield the waveform JSON body incrementally, one channel at a time.

    Each chunk's json.dumps() call covers exactly one channel's (already
    capped) point list, so the server never assembles the full multi-channel
    body as a single string. Content-equivalent to the pre-streaming dict
    response (same keys, same values); unlike the CSV export, byte-for-byte
    whitespace/order identity is not a requirement here.
    """
    yield '{"channels": ['
    for i, (channel, data) in enumerate(captures):
        if i:
            yield ", "
        yield json.dumps(_waveform_json(channel, data, max_points))
    yield "]}"


def _waveform_json(channel, data, max_points):
    voltage = data.voltage
    time_axis = data.time
    step = 1
    if max_points is not None and max_points > 0 and len(voltage) > max_points:
        step = -(-len(voltage) // max_points)  # ceiling division keeps len <= max_points
    points = [float(v) for v in voltage[::step]]
    t0 = float(time_axis[0]) if len(time_axis) else 0.0
    dt = float(time_axis[1] - time_axis[0]) * step if len(time_axis) > 1 else 1.0
    return {
        "channel": channel,
        "t0": t0,
        "dt": dt,
        "sample_rate": data.sample_rate,
        "voltage_scale": data.voltage_scale,
        "voltage_offset": data.voltage_offset,
        "points": points,
    }


@router.get("/sessions/{session_id}/scope/waveform")
async def waveform_json(session_id: str, request: Request, channels: str = "1", max_points: int = 0):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    channel_list = _parse_channel_list(channels)
    stride, size_verified = await _export_stride(session, max_points)
    cap = max_points if max_points > 0 else None

    def capture(scope):
        return [(c, scope.get_waveform(c, stride=stride)) for c in channel_list]

    try:
        captures = await run_job(session, capture)
    except FeatureNotSupportedError as exc:
        raise _reraise_transfer_cap_trip_as_413(exc) from exc
    _warn_if_export_was_unverifiable_and_oversized(captures, size_verified)
    return StreamingResponse(_stream_waveform_json(captures, cap), media_type="application/json")


def _math_state(scope):
    return [{"n": n, "expression": m.expression, "enabled": m.enabled} for n, m in ((1, scope.math1), (2, scope.math2))]


@router.get("/sessions/{session_id}/scope/math")
async def get_math(session_id: str, request: Request):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    return await run_job(session, _math_state)


@router.patch("/sessions/{session_id}/scope/math/{n}")
async def patch_math(session_id: str, n: int, body: MathPatch, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")
    if n not in (1, 2):
        raise InvalidParameterError("math channel must be 1 or 2")
    if body.expression is not None and not body.expression.strip():
        raise InvalidParameterError("expression must not be empty")

    def apply(scope):
        math = scope.math1 if n == 1 else scope.math2
        if body.expression is not None:
            math.set_expression(body.expression)
        if body.enabled is not None:
            math.enable() if body.enabled else math.disable()
        return _math_state(scope)

    return await run_job(session, apply)


@router.get("/sessions/{session_id}/scope/spectrum")
async def get_spectrum(session_id: str, request: Request):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    return dict(session.adapter.spectrum_config)


@router.patch("/sessions/{session_id}/scope/spectrum")
async def patch_spectrum(session_id: str, body: SpectrumPatch, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "window" in updates and updates["window"] not in ALLOWED_WINDOWS:
        raise InvalidParameterError("unknown window: {0}".format(updates["window"]))
    if "channel" in updates and not 1 <= updates["channel"] <= max(1, session.num_channels):
        raise InvalidParameterError("channel {0} out of range".format(updates["channel"]))
    session.adapter.spectrum_config = {**session.adapter.spectrum_config, **updates}
    return dict(session.adapter.spectrum_config)


def _filter_state(session):
    return [{"n": n, **session.adapter.filters[n]} for n in sorted(session.adapter.filters)]


@router.get("/sessions/{session_id}/scope/filters")
async def get_filters(session_id: str, request: Request):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    return _filter_state(session)


@router.patch("/sessions/{session_id}/scope/filters/{n}")
async def patch_filter(session_id: str, n: int, body: FilterPatch, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")
    if n not in (1, 2):
        raise InvalidParameterError("filter must be 1 or 2")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "kind" in updates and updates["kind"] not in ALLOWED_FILTER_KINDS:
        raise InvalidParameterError("unknown filter kind: {0}".format(updates["kind"]))
    if "source" in updates and not 1 <= updates["source"] <= max(1, session.num_channels):
        raise InvalidParameterError("channel {0} out of range".format(updates["source"]))
    if "order" in updates and not 1 <= updates["order"] <= 10:
        raise InvalidParameterError("order must be between 1 and 10")
    for key in ("cutoff_low", "cutoff_high"):
        if key in updates and updates[key] <= 0:
            raise InvalidParameterError("{0} must be positive".format(key))
    merged = {**session.adapter.filters[n], **updates}
    if merged["enabled"]:
        # completeness is only enforced when the merged config is enabled, so
        # partial configuration while disabled stays a valid workflow
        if merged["kind"] == "lowpass" and merged["cutoff_high"] is None:
            raise InvalidParameterError("lowpass requires cutoff_high")
        if merged["kind"] == "highpass" and merged["cutoff_low"] is None:
            raise InvalidParameterError("highpass requires cutoff_low")
        if merged["kind"] == "bandpass":
            if merged["cutoff_low"] is None or merged["cutoff_high"] is None:
                raise InvalidParameterError("bandpass requires cutoff_low and cutoff_high")
            if not merged["cutoff_low"] < merged["cutoff_high"]:
                raise InvalidParameterError("cutoff_low must be below cutoff_high")
    session.adapter.filters = {**session.adapter.filters, n: merged}
    return _filter_state(session)


def _reference_store(request: Request):
    if request.app.state.references is None:
        from scpi_control.reference_waveform import ReferenceWaveform

        request.app.state.references = ReferenceWaveform(request.app.state.references_dir)
    return request.app.state.references


def _ref_channel(value):
    """Normalize a stored channel value (int, '1', or 'C1') to an int, else None."""
    if isinstance(value, int):
        return value
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else None


def _reference_list(store):
    return [{"name": r["name"], "channel": _ref_channel(r["channel"]), "timestamp": r["timestamp"], "num_samples": r["num_samples"], "time_span": r["time_span"]} for r in store.list_references()]


@router.get("/sessions/{session_id}/scope/references")
async def list_references(session_id: str, request: Request):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    store = _reference_store(request)
    return await run_in_threadpool(_reference_list, store)


@router.post("/sessions/{session_id}/scope/references", status_code=201)
async def save_reference(session_id: str, body: ReferenceCreate, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")
    name = body.name.strip()
    if not name:
        raise InvalidParameterError("reference name must not be empty")
    if not 1 <= body.channel <= max(1, session.num_channels):
        raise InvalidParameterError("channel {0} out of range".format(body.channel))
    data = await run_job(session, lambda scope: scope.get_waveform(body.channel))
    data = replace(data, channel=body.channel)  # normalize: list/activate read the channel from NPZ metadata
    store = _reference_store(request)

    def persist():
        while store.delete_reference(name):  # replace-on-save, incl. legacy timestamped duplicates
            pass
        store.save_reference(data, name)
        return _reference_list(store)

    return await run_in_threadpool(persist)


@router.delete("/sessions/{session_id}/scope/references/{name}", status_code=204)
async def delete_reference(session_id: str, name: str, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")
    store = _reference_store(request)

    def remove():
        deleted = store.delete_reference(name)
        while store.delete_reference(name):
            pass
        return deleted

    if not await run_in_threadpool(remove):
        raise HTTPException(status_code=404, detail="unknown reference {0}".format(name))
    active = session.adapter.active_reference
    if active is not None and active["name"] == name:
        session.adapter.set_active_reference(None, None, None, session.publish)


@router.get("/sessions/{session_id}/scope/reference")
async def get_reference(session_id: str, request: Request):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    return session.adapter.reference_overlay()


@router.put("/sessions/{session_id}/scope/reference")
async def put_reference(session_id: str, body: ReferencePut, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")
    if body.name is None:
        session.adapter.set_active_reference(None, None, None, session.publish)
        return session.adapter.reference_overlay()
    store = _reference_store(request)
    loaded = await run_in_threadpool(store.load_reference, body.name)
    if loaded is None:
        raise HTTPException(status_code=404, detail="unknown reference {0}".format(body.name))
    metadata = loaded.get("metadata", {})
    session.adapter.set_active_reference(metadata.get("name", body.name), _ref_channel(metadata.get("channel")), loaded, session.publish)
    return session.adapter.reference_overlay()


@router.post("/sessions/{session_id}/scope/log/start")
async def log_start(session_id: str, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")
    return session.adapter.start_recording(session.publish)


@router.post("/sessions/{session_id}/scope/log/stop")
async def log_stop(session_id: str, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")
    return session.adapter.stop_recording(session.publish)


@router.get("/sessions/{session_id}/scope/log")
async def log_status(session_id: str, request: Request):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    return session.adapter.recorder.status()


@router.get("/sessions/{session_id}/scope/log/data")
async def log_data(session_id: str, request: Request, since: float = 0.0):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    status = session.adapter.recorder.status()
    return {"columns": status["columns"], "rows": session.adapter.recorder.rows_since(since)}


def _build_log_csv(status, rows) -> str:
    header = "timestamp,elapsed_s," + ",".join("C{0} {1}".format(c["channel"], c["mtype"]) for c in status["columns"])
    started = status["started_at"] or 0.0
    lines = [header]
    for row in rows:
        ts = row[0]
        cells = ["" if v is None else "{0:.9g}".format(float(v)) for v in row[1:]]
        lines.append("{0},{1:.3f},{2}".format(datetime.fromtimestamp(ts).isoformat(), ts - started, ",".join(cells)))
    return "\n".join(lines) + "\n"


@router.get("/sessions/{session_id}/scope/log.csv")
async def log_csv(session_id: str, request: Request):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    status = session.adapter.recorder.status()
    if status["started_at"] is None:
        raise HTTPException(status_code=404, detail="no recording exists")
    csv_text = _build_log_csv(status, session.adapter.recorder.rows_since())
    filename = "log_{0}.csv".format(session.id)
    return PlainTextResponse(csv_text, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="{0}"'.format(filename)})


# NOTE: run_op's {op} path is a catch-all for POST /scope/*; any new specific
# POST route under /scope must be registered ABOVE it or it will be shadowed.
_RUN_OPS = {
    "run": lambda scope: scope.run(),
    "stop": lambda scope: scope.stop(),
    "single": lambda scope: scope.trigger_single(),
    "auto": lambda scope: scope.auto_setup(),
}


@router.post("/sessions/{session_id}/scope/{op}")
async def run_op(session_id: str, op: str, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "scope")
    fn = _RUN_OPS.get(op)
    if fn is None:
        raise InvalidParameterError("unknown operation: {0}".format(op))
    return await mutate(session, fn)
