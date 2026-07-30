"""Per-kind adapters: what differs between instrument kinds in a session.

InstrumentSession owns everything shared -- the worker thread, the job queue,
pub/sub, viewers, ownership, the error state machine. An adapter owns the four
things that actually vary by kind, plus any state only that kind needs.

Keeping the lifecycle in ONE implementation is deliberate. It is threading code,
and a subclass that overrides part of a thread or error path by accident is a
much worse failure than a little indirection.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from scpi_control import FunctionGenerator, Oscilloscope, PowerSupply
from scpi_control.connection.mock import MockConnection
from scpi_control.exceptions import InvalidParameterError, SiglentError
from scpi_control.server import compute
from scpi_control.server.netpolicy import validate_target
from scpi_control.server.recorder import TrendRecorder

logger = logging.getLogger(__name__)

MAX_FRAME_POINTS = 2000
MEASUREMENT_EVERY_N_POLLS = 4

DEFAULT_MOCK_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
DEFAULT_MOCK_PSU_IDN = "Siglent Technologies,SPD3303X,SPD123456,1.0"
DEFAULT_MOCK_AWG_IDN = "Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1"


def _safe(fn, default=None, label=None, state=None):
    """Run `fn`, degrading to `default` on the exceptions a poll tick must
    survive. `label`/`state` are both optional and BOTH must be given to opt
    into logging -- every existing call site that passes neither behaves
    exactly as before, which is what keeps this signature backward compatible
    for the many callers that just want the swallow.

    `state` is a dict the caller owns (an adapter's `self._poll_health`,
    typically), keyed by `label`, holding the last-known-good (True) or
    last-known-bad (False) status of that one named operation. Passing the
    SAME dict across calls with DIFFERENT labels is what lets, e.g., a failing
    channel 1 query and a healthy channel 2 query be tracked independently --
    otherwise the two would overwrite one shared "is it failing" flag and
    flap each other's state.

    Logging is once per transition, not once per call: at a 0.25s poll
    interval, logging every tick of a persistent failure would write four
    lines a second and bury everything else in the log. A success->failure
    transition logs one WARNING naming the operation; a failure->success
    transition logs one recovery WARNING (same level, deliberately -- an
    operator or alert filtering at WARNING must see the outage both begin
    and end, or the log is exactly as ambiguous as before this fix for that
    reader), with distinguishable wording so the two can be told apart at a
    glance. Steady state -- repeated failures, or repeated successes -- logs
    nothing.
    """
    try:
        result = fn()
    except SiglentError:
        # SiglentError only, deliberately: the one caller that could raise a
        # ValueError through here (Oscilloscope.record_length(), which parses
        # its reply with int(float(...))) now swallows that itself, like
        # waveform_max_points() always did. Widening this to ValueError as
        # well would silently absorb one from the three unlabelled read_state
        # call sites too, turning probe_ratio/trigger.source into null instead
        # of surfacing a genuine bug.
        if label is not None and state is not None and state.get(label) is not False:
            logger.warning("poll query failed, degrading to a default: %s", label)
            state[label] = False
        return default
    if label is not None and state is not None:
        if state.get(label) is False:
            # Also WARNING, not a quieter level: this is the other half of a
            # matched pair with the failure log above, not "good news" logged
            # for its own sake. An operator or alert filtering at WARNING --
            # which is the level the failure logs at -- must see the outage
            # both begin AND end, or the log is exactly as ambiguous as before
            # this fix for anyone reading at that level.
            logger.warning("poll query recovered, no longer degrading to a default: %s", label)
        state[label] = True
    return result


def _quiet(fn, default=None):
    """Like _safe, but for analysis compute: ANY exception degrades to default.

    The poll tick is the session heartbeat; a numpy edge case in analysis
    must never kill the worker thread.
    """
    try:
        return fn()
    except Exception:
        return default


def read_state(scope: Oscilloscope) -> Dict[str, Any]:
    channels: Dict[int, Dict[str, Any]] = {}
    for n in scope.supported_channels:
        ch = scope.get_channel(n)
        channels[n] = {
            "enabled": ch.enabled,
            "voltage_scale": ch.voltage_scale,
            "voltage_offset": ch.voltage_offset,
            "coupling": ch.coupling,
            "probe_ratio": _safe(lambda: ch.probe_ratio),
        }
    trig = scope.trigger
    return {
        "run_state": scope.acquisition_status(),
        "timebase": scope.timebase,
        "channels": channels,
        "trigger": {
            "mode": trig.mode,
            "source": _safe(lambda: trig.source),
            "level": _safe(lambda: trig.level),
            "slope": _safe(lambda: trig.slope),
            "coupling": _safe(lambda: trig.coupling),
        },
    }


def _decimate_frame(channel, time_axis, voltage) -> Dict[str, Any]:
    step = max(1, -(-len(voltage) // MAX_FRAME_POINTS))  # ceiling division keeps len(points) <= cap
    points = voltage[::step]
    t0 = float(time_axis[0]) if len(time_axis) else 0.0
    dt = float(time_axis[1] - time_axis[0]) * step if len(time_axis) > 1 else 1.0
    return {"type": "waveform", "channel": channel, "t0": t0, "dt": dt, "points": [float(v) for v in points]}


def _waveform_frame(scope: Oscilloscope, channel: int) -> Dict[str, Any]:
    data = scope.get_waveform(channel, provenance=False)
    return _decimate_frame(channel, data.time, data.voltage)


def make_mock_scope_connection(model: Optional[str]) -> MockConnection:
    idn = DEFAULT_MOCK_IDN if model is None else "Siglent Technologies,{0},MOCK0001,1.0.0.0".format(model)
    # No explicit waveform_payloads: channels serve state-coupled synthesized
    # signals (connection/mock/synth.py). 1 MSa/s x 14 div x 1 ms/div = 14k points.
    return MockConnection("mock", idn=idn, channel_states={1: True, 2: False, 3: False, 4: False}, trigger_status=["Stop"], sample_rate=1_000_000.0, timebase=1e-3)


def make_mock_psu_connection(model: Optional[str]) -> MockConnection:
    idn = DEFAULT_MOCK_PSU_IDN if model is None else "Siglent Technologies,{0},MOCK0001,1.0.0.0".format(model)
    return MockConnection("mock", psu_mode=True, psu_idn=idn)


def make_mock_awg_connection(model: Optional[str]) -> MockConnection:
    idn = DEFAULT_MOCK_AWG_IDN if model is None else "Siglent Technologies,{0},MOCK0001,1.0.0.0".format(model)
    return MockConnection("mock", awg_mode=True, awg_idn=idn)


class InstrumentAdapter:
    """What a session needs to know about one kind of instrument."""

    kind = ""

    def build(self, address, port, mock, model, allowed_ports, connection) -> Any:
        raise NotImplementedError

    def connect(self, instrument) -> Dict[str, Any]:
        """Connect, then return {"idn", "model", "dialect", "num_channels"}."""
        raise NotImplementedError

    def poll(self, instrument, publish: Callable[[Dict[str, Any]], None], tick: int) -> None:
        """Publish whatever this kind emits per tick. Called on the worker thread."""
        raise NotImplementedError

    def initial_frame(self, instrument) -> Dict[str, Any]:
        """The first frame a newly-opened live stream receives.

        It must have the same shape this kind publishes on every subsequent
        tick, otherwise a client that discriminates on the frame shape sees
        one thing at connect and another a quarter-second later. Declared
        here (rather than branched on ``session.kind`` in the stream handler)
        so a new kind cannot be wired up while quietly inheriting some other
        kind's frame -- NotImplementedError is loud, and the stream handler
        turns it into an error frame plus a distinct close code.
        """
        raise NotImplementedError

    def close(self, instrument) -> None:
        raise NotImplementedError


class ScopeAdapter(InstrumentAdapter):
    kind = "scope"

    def __init__(self) -> None:
        self.measurements: List[Tuple[int, str]] = []
        # Server-owned analysis config. Request coroutines swap these whole
        # dicts atomically (never mutate in place); the worker thread only reads.
        self.spectrum_config: Dict[str, Any] = {"enabled": False, "channel": 1, "window": "hanning", "db": True}
        self.filters: Dict[int, Dict[str, Any]] = {n: {"source": 1, "kind": "lowpass", "cutoff_low": None, "cutoff_high": None, "order": 5, "enabled": False} for n in (1, 2)}
        self.active_reference: Optional[Dict[str, Any]] = None  # {"name", "channel", "data": {"time","voltage",...}}
        self._shown: set = set()  # trace keys (M1/M2/F1/F2/SPEC) live on subscribers' canvases; worker-thread-only
        self.recorder = TrendRecorder()  # internally locked: worker appends, request threads control/read
        # Whether a waveform frame has ever been published on this session.
        # False lets the very first tick fetch unconditionally even when the
        # gate below says "nothing new" -- a scope sitting in Stop mode never
        # produces a new acquisition, and without this exemption it would show
        # an empty canvas forever instead of its perfectly good last frame.
        self._published_a_frame = False
        # Last-known-good/bad status per poll-path query, keyed by an
        # operation label -- see _safe()'s docstring. Worker-thread-only, like
        # self._shown: nothing else reads or writes it.
        self._poll_health: Dict[str, bool] = {}

    def build(self, address, port, mock, model, allowed_ports, connection):
        if mock:
            conn = connection if connection is not None else make_mock_scope_connection(model)
            return Oscilloscope("mock", connection=conn)
        if not address:
            raise ValueError("address is required for a non-mock session")
        validate_target(address, port, allowed_ports=allowed_ports)
        return Oscilloscope(address, port=port)

    def connect(self, instrument):
        instrument.connect()
        info = instrument.device_info or {}
        return {
            "idn": instrument.identify(),
            "model": info.get("model", ""),
            "dialect": instrument.dialect or "",
            "num_channels": len(instrument.supported_channels),
        }

    def poll(self, instrument, publish, tick):
        scope = instrument
        shown = self._shown
        # A read the scope cannot answer yet blocks this worker, and the worker
        # is also the only thing servicing user commands -- so an unanswerable
        # read freezes the whole UI for the length of the acquisition. Ask
        # first, and ask at most once: the underlying register is
        # read-and-clear, so a second read in this tick would consume a real
        # event and get a meaningless answer. None (dialect has no gate) must
        # never be treated as False, or the live view dies on every
        # non-Siglent scope.
        health = self._poll_health
        # No label/state on the next three _safe calls, unlike the per-channel
        # reads below: new_acquisition_ready()/record_length()/
        # waveform_max_points() each catch their own query failure and return
        # None (see oscilloscope.py), so _safe never sees an exception from
        # them and its logging branch is unreachable. A label here would only
        # promise a log line that can never be written. The bare _safe stays as
        # the last-resort swallow that keeps the session heartbeat alive if one
        # of them ever raises something unexpected.
        ready = _safe(lambda: scope.new_acquisition_ready(), default=None)
        if ready is False and self._published_a_frame:
            return
        # Size the stride from the full record length, capped by whichever is
        # smaller: our own per-frame budget, or the instrument's own
        # per-transfer limit (:WAVeform:MAXPoint?, via waveform_max_points()).
        # Sizing against MAX_FRAME_POINTS alone can still overflow a low cap
        # and turn ModernTransfer's strided-read guard (FeatureNotSupportedError)
        # into a total live-view outage -- capping here makes that guard
        # unreachable by construction.
        points = _safe(lambda: scope.record_length(), default=None)
        stride = None
        if points:
            cap = _safe(lambda: scope.waveform_max_points(), default=None)
            limit = min(MAX_FRAME_POINTS, cap) if cap else MAX_FRAME_POINTS
            stride = max(1, -(-points // limit))
        acquired = {}
        for n in scope.supported_channels:
            ch = scope.get_channel(n)
            if ch is not None and _safe(lambda: ch.enabled, default=False, label="channel {0} enabled".format(n), state=health):
                data = scope.get_waveform(n, provenance=False, stride=stride)
                acquired["C{0}".format(n)] = data
                publish(_decimate_frame(n, data.time, data.voltage))
                self._published_a_frame = True
        shown_now = set()
        for label, math in (("M1", scope.math1), ("M2", scope.math2)):
            result = None
            if math is not None and _safe(lambda: math.enabled, default=False, label="math {0} enabled".format(label), state=health):
                result = _safe(lambda: math.compute(acquired), label="math {0} compute".format(label), state=health)
            if result is not None:
                publish(_decimate_frame(label, result.time, result.voltage))
                shown_now.add(label)
            elif label in shown:
                publish(_decimate_frame(label, [], []))  # one-shot clear on transition
        filters = self.filters
        for n in sorted(filters):
            config = filters[n]
            label = "F{0}".format(n)
            result = _quiet(lambda: compute.filtered_waveform(config, acquired)) if config["enabled"] else None
            if result is not None:
                publish(_decimate_frame(label, result.time, result.voltage))
                shown_now.add(label)
            elif label in shown:
                publish(_decimate_frame(label, [], []))
        spectrum_config = self.spectrum_config
        frame = _quiet(lambda: compute.spectrum_frame(spectrum_config, acquired)) if spectrum_config["enabled"] else None
        if frame is not None:
            publish(frame)
            shown_now.add("SPEC")
        elif "SPEC" in shown:
            publish(compute.empty_spectrum_frame(spectrum_config))
        self._shown = shown_now
        if tick % MEASUREMENT_EVERY_N_POLLS == 0:
            if self.measurements:
                now = time.time()
                values = []
                for channel, mtype in self.measurements:
                    value = _safe(lambda: scope.measurement.measure(mtype, channel), label="measurement {0} channel {1}".format(mtype, channel), state=health)
                    values.append({"channel": channel, "mtype": mtype, "value": value})
                publish({"type": "measurements", "values": values, "timestamp": now})
                self.recorder.append(now, [entry["value"] for entry in values])
            reference = self.active_reference  # snapshot for thread safety
            if reference is not None:
                publish(compute.reference_stats(reference, acquired))

    def initial_frame(self, instrument):
        return {"type": "state", "state": read_state(instrument)}

    def close(self, instrument):
        instrument.disconnect()

    def set_measurements(self, items: List[Tuple[int, str]], publish: Callable[[Dict[str, Any]], None]) -> None:
        self.measurements = list(items)
        publish({"type": "measurements_config", "items": [{"channel": c, "mtype": m} for c, m in self.measurements]})

    def start_recording(self, publish: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        # Local import: sessions.py imports this module at top level, so a
        # module-level import of SessionError back from sessions.py here would
        # be circular. By call time sessions.py is fully loaded.
        from scpi_control.server.sessions import SessionError

        if self.recorder.state == "recording":
            raise SessionError("already recording")
        if not self.measurements:
            raise InvalidParameterError("no measurements selected")
        self.recorder.start(list(self.measurements), time.time())
        self._publish_log_status(publish)
        return self.recorder.status()

    def stop_recording(self, publish: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        self.recorder.stop()
        self._publish_log_status(publish)
        return self.recorder.status()

    def _publish_log_status(self, publish: Callable[[Dict[str, Any]], None]) -> None:
        status = self.recorder.status()
        publish({"type": "log_status", "state": status["state"], "started_at": status["started_at"], "row_count": status["row_count"], "columns": status["columns"]})

    def reference_overlay(self) -> Dict[str, Any]:
        active = self.active_reference
        if active is None:
            return {"name": None, "channel": None, "t0": 0.0, "dt": 1.0, "points": []}
        frame = _decimate_frame(active["channel"], active["data"]["time"], active["data"]["voltage"])
        return {"name": active["name"], "channel": active["channel"], "t0": frame["t0"], "dt": frame["dt"], "points": frame["points"]}

    def set_active_reference(self, name: Optional[str], channel: Optional[int], data: Optional[Dict[str, Any]], publish: Callable[[Dict[str, Any]], None]) -> None:
        self.active_reference = None if name is None else {"name": name, "channel": channel, "data": data}
        publish({"type": "reference", **self.reference_overlay()})


MEASURED_KEYS = ("measured_voltage", "measured_current", "measured_power")
UNKNOWN_MEASURED: Dict[str, Any] = {key: None for key in MEASURED_KEYS}


def read_psu_outputs(psu: PowerSupply, measure: bool = True) -> List[Dict[str, Any]]:
    """One dict per output. Shared by PsuAdapter.poll and GET /psu/state so the
    streamed shape and the fetched shape cannot drift apart.

    ``measure=False`` skips the three measured readings (leaving them None) so
    a caller that only needs setpoints and enable state can do it in half the
    queries; PsuAdapter.poll uses that to throttle the measured triplet.

    Every field is read through _safe, so a query the model does not implement
    or a timeout yields None rather than a fabricated value. ``enabled`` in
    particular MUST NOT default to False: an SPD3303X's CH3 has no documented
    status bit and falls through to an OUTP3? that the model does not answer,
    so a False default would render an energised output as a confident "off".
    None means "unknown", and the UI is required to show it as unknown.
    """
    outputs = []
    for n in psu.supported_outputs:
        out = psu.get_output(n)
        if out is None:
            continue
        row = {
            "output": n,
            "voltage": _safe(lambda: out.voltage),
            "current": _safe(lambda: out.current),
            "enabled": _safe(lambda: out.enabled),
        }
        if measure:
            row["measured_voltage"] = _safe(lambda: out.measure_voltage())
            row["measured_current"] = _safe(lambda: out.measure_current())
            row["measured_power"] = _safe(lambda: out.measure_power())
        else:
            row.update(UNKNOWN_MEASURED)
        outputs.append(row)
    return outputs


def read_awg_channels(awg: FunctionGenerator) -> List[Dict[str, Any]]:
    """One dict per channel. Shared by AwgAdapter.poll and GET /awg/state so the
    streamed shape and the fetched shape cannot drift apart.

    Unlike the PSU reader there is nothing to throttle: an AWG measures nothing,
    every field is a setting. Those settings still change without the UI asking
    -- someone can turn a knob on the instrument's front panel -- so reading the
    full set every tick is what keeps the panel honest about the instrument's
    actual state.

    duty_cycle and symmetry are read ONLY for the function they belong to.
    AWGOutput.pulse_duty_cycle logs a warning and reads DUTY anyway when the
    current function is not PULSE (awg_output.py:281); at four polls a second
    that is a warning flood for a value the UI would not show.

    Every field goes through _safe, so a query the model does not implement or a
    timeout yields None rather than a fabricated value. ``enabled`` in
    particular MUST NOT default to False -- AWGOutput.enabled raises
    CommandError when an SDG's OUTPut? response carries no STATE field
    (awg_output.py:249), and a False default would render a live output driving
    a circuit as a confident "off". None means "unknown", and the UI is required
    to show it as unknown.
    """
    channels = []
    for n in awg.supported_channels:
        channel = awg.get_channel(n)
        if channel is None:
            continue
        function = _safe(lambda: channel.function)
        channels.append(
            {
                "channel": n,
                "function": function,
                "frequency": _safe(lambda: channel.frequency),
                "amplitude": _safe(lambda: channel.amplitude),
                "offset": _safe(lambda: channel.offset),
                "phase": _safe(lambda: channel.phase),
                "enabled": _safe(lambda: channel.enabled),
                "duty_cycle": _safe(lambda: channel.pulse_duty_cycle) if function == "PULSE" else None,
                "symmetry": _safe(lambda: channel.ramp_symmetry) if function == "RAMP" else None,
            }
        )
    return channels


class AwgAdapter(InstrumentAdapter):
    kind = "awg"

    def build(self, address, port, mock, model, allowed_ports, connection):
        if mock:
            conn = connection if connection is not None else make_mock_awg_connection(model)
            return FunctionGenerator("mock", connection=conn)
        if not address:
            raise ValueError("address is required for a non-mock session")
        validate_target(address, port, allowed_ports=allowed_ports)
        return FunctionGenerator(address, port=port)

    def connect(self, instrument):
        instrument.connect()
        info = instrument.device_info or {}
        return {
            "idn": instrument.identify(),
            "model": info.get("model", ""),
            "dialect": "",  # an AWG has no scope-style dialect; the field stays for payload compatibility
            "num_channels": len(instrument.supported_channels),
        }

    def poll(self, instrument, publish, tick):
        publish({"type": "state", "kind": "awg", "channels": read_awg_channels(instrument)})

    def initial_frame(self, instrument):
        return {"type": "state", "kind": "awg", "channels": read_awg_channels(instrument)}

    def close(self, instrument):
        instrument.disconnect()


class PsuAdapter(InstrumentAdapter):
    kind = "psu"

    def __init__(self) -> None:
        # Last known measured triplet per output, so the throttled ticks can
        # still emit the full frame shape instead of blanking the readings
        # three ticks out of four. Worker-thread-only, like ScopeAdapter._shown.
        self._measured: Dict[int, Dict[str, Any]] = {}

    def build(self, address, port, mock, model, allowed_ports, connection):
        if mock:
            conn = connection if connection is not None else make_mock_psu_connection(model)
            return PowerSupply("mock", connection=conn)
        if not address:
            raise ValueError("address is required for a non-mock session")
        validate_target(address, port, allowed_ports=allowed_ports)
        return PowerSupply(address, port=port)

    def connect(self, instrument):
        instrument.connect()
        info = instrument.device_info or {}
        return {
            "idn": instrument.identify(),
            "model": info.get("model", ""),
            "dialect": "",  # a PSU has no scope-style dialect; the field stays for payload compatibility
            "num_channels": len(instrument.supported_outputs),
        }

    def poll(self, instrument, publish, tick):
        # The measured triplet is 3 of the ~6 queries an output costs, and on a
        # 3-output SPD3303X that is 18 queries every 250 ms. Setpoints and the
        # enable state stay live on every tick (they are what a user is
        # watching when they flip a switch); the measurements ride the same
        # every-Nth-tick budget the scope's measurements do. The first tick
        # always measures so a fresh stream is never briefly blank.
        measure = tick % MEASUREMENT_EVERY_N_POLLS == 0 or not self._measured
        outputs = read_psu_outputs(instrument, measure=measure)
        for row in outputs:
            if measure:
                self._measured[row["output"]] = {key: row[key] for key in MEASURED_KEYS}
            else:
                row.update(self._measured.get(row["output"], UNKNOWN_MEASURED))
        publish({"type": "state", "kind": "psu", "outputs": outputs})

    def initial_frame(self, instrument):
        return {"type": "state", "kind": "psu", "outputs": read_psu_outputs(instrument)}

    def close(self, instrument):
        instrument.disconnect()


ADAPTERS: Dict[str, type] = {"scope": ScopeAdapter, "psu": PsuAdapter, "awg": AwgAdapter}
