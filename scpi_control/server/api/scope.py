# scpi_control/server/api/scope.py
import asyncio
from dataclasses import replace
from datetime import datetime
from typing import Any, Callable, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse, Response

from scpi_control.exceptions import InvalidParameterError
from scpi_control.server.api.sessions import require_kind, require_session
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

router = APIRouter(tags=["scope"])


async def run_job(session: InstrumentSession, fn: Callable) -> Any:
    return await asyncio.wrap_future(session.submit(fn))


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
    command = body.command.strip()
    if not command:
        raise InvalidParameterError("empty command")

    def run(scope):
        if command.endswith("?"):
            return scope.query(command)
        scope.write(command)
        return None

    response = await run_job(session, run)
    return {"command": command, "response": response}


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


def _build_csv(captures) -> str:
    """captures: list of (channel:int, WaveformData). Align to the shortest."""
    n = min(len(w.voltage) for _, w in captures)
    time_axis = captures[0][1].time
    header = "time_s," + ",".join("C{0}_V".format(c) for c, _ in captures)
    rows = [header]
    for i in range(n):
        rows.append("{0:.9g},{1}".format(float(time_axis[i]), ",".join("{0:.9g}".format(float(w.voltage[i])) for _, w in captures)))
    return "\n".join(rows) + "\n"


@router.get("/sessions/{session_id}/scope/capture.csv")
async def capture_csv(session_id: str, request: Request, channels: str = "1"):
    session = require_session(request, session_id)
    require_kind(session, "scope")
    try:
        channel_list = sorted({int(c) for c in channels.split(",") if c.strip()})
    except ValueError:
        raise InvalidParameterError("channels must be a comma-separated list of integers")
    if not channel_list:
        raise InvalidParameterError("no channels requested")

    def capture(scope):
        return [(c, scope.get_waveform(c)) for c in channel_list]

    captures = await run_job(session, capture)
    csv_text = await run_in_threadpool(_build_csv, captures)
    filename = "capture_{0}_C{1}.csv".format(session.id, "-".join(str(c) for c in channel_list))
    return PlainTextResponse(csv_text, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="{0}"'.format(filename)})


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


def _build_waveform_response(captures, max_points) -> dict:
    return {"channels": [_waveform_json(c, data, max_points) for c, data in captures]}


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
    try:
        channel_list = sorted({int(c) for c in channels.split(",") if c.strip()})
    except ValueError:
        raise InvalidParameterError("channels must be a comma-separated list of integers")
    if not channel_list:
        raise InvalidParameterError("no channels requested")

    def capture(scope):
        return [(c, scope.get_waveform(c)) for c in channel_list]

    captures = await run_job(session, capture)
    cap = max_points if max_points > 0 else None
    return await run_in_threadpool(_build_waveform_response, captures, cap)


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
