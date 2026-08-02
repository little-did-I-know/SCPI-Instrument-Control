"""The per-point loop: ranging, capture, estimation, and what it refuses to invent."""

import csv

import pytest

from scpi_control import exceptions
from scpi_control.automation import DataCollector
from scpi_control.channel import Channel
from scpi_control.connection import MockConnection
from scpi_control.connection.mock.loopback import AwgLoopback
from scpi_control.dut import RCLowPass
from scpi_control.frequency_response.sweep import sweep
from scpi_control.function_generator import FunctionGenerator
from scpi_control.oscilloscope import Oscilloscope

CUTOFF_HZ = 1000.0


def _rig(sample_rate=1e6):
    """A mock AWG patched to scope CH1 directly and to CH2 through an RC low-pass."""
    awg_connection = MockConnection("mock", awg_mode=True)
    awg = FunctionGenerator("mock", connection=awg_connection)
    awg.connect()
    scope_connection = MockConnection(
        "mock",
        channel_states={1: True, 2: True, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=sample_rate,
        timebase=1e-3,
        signals={1: AwgLoopback(awg_connection, awg_channel=1), 2: AwgLoopback(awg_connection, awg_channel=1, dut=RCLowPass(CUTOFF_HZ))},
    )
    scope = Oscilloscope("mock", connection=scope_connection)
    scope.connect()
    return scope, awg


def test_a_measured_point_carries_gain_phase_and_geometry():
    scope, awg = _rig()
    try:
        result = sweep(scope, awg, reference_channel=1, response_channel=2, frequencies=[CUTOFF_HZ], amplitude_vpp=2.0, settle_s=0.0)
    finally:
        scope.disconnect()
        awg.disconnect()

    point = result.points[0]
    assert point.excluded_reason is None
    assert point.gain_db == pytest.approx(-3.01, abs=0.1)
    assert point.phase_deg == pytest.approx(-45.0, abs=2.5)
    assert point.cycles_in_window > 10
    assert point.samples_per_cycle == pytest.approx(1000.0, rel=0.01)


def test_autoranging_picks_a_scale_that_fits_the_response():
    scope, awg = _rig()
    try:
        result = sweep(scope, awg, reference_channel=1, response_channel=2, frequencies=[5000.0], amplitude_vpp=2.0, settle_s=0.0)
    finally:
        scope.disconnect()
        awg.disconnect()

    # A 2 Vpp drive attenuated ~5x at 5 kHz lands near 0.4 Vpp -> 0.1 V/div.
    assert result.points[0].volts_per_div == pytest.approx(0.1)


def test_autorange_off_leaves_the_scale_alone():
    scope, awg = _rig()
    try:
        scope.get_channel(2).voltage_scale = 1.0
        result = sweep(scope, awg, reference_channel=1, response_channel=2, frequencies=[5000.0], amplitude_vpp=2.0, settle_s=0.0, autorange=False)
    finally:
        scope.disconnect()
        awg.disconnect()

    assert result.points[0].volts_per_div == pytest.approx(1.0)


def test_an_off_screen_response_is_excluded_rather_than_reported():
    scope, awg = _rig()
    try:
        # 2 Vpp on 0.2 V/div reaches +/-5 divisions; autoranging would fix it,
        # so this must be measured with autoranging off.
        scope.get_channel(2).voltage_scale = 0.2
        result = sweep(scope, awg, reference_channel=1, response_channel=2, frequencies=[100.0], amplitude_vpp=2.0, settle_s=0.0, autorange=False)
    finally:
        scope.disconnect()
        awg.disconnect()

    point = result.points[0]
    assert point.gain_db is None
    assert "divisions" in point.excluded_reason


def test_on_point_sees_every_point_as_it_arrives():
    scope, awg = _rig()
    seen = []
    try:
        result = sweep(scope, awg, reference_channel=1, response_channel=2, frequencies=[500.0, 1000.0], amplitude_vpp=2.0, settle_s=0.0, on_point=seen.append)
    finally:
        scope.disconnect()
        awg.disconnect()

    assert [point.frequency_hz for point in seen] == [500.0, 1000.0]
    assert seen == result.points


def test_provenance_is_recorded_once():
    scope, awg = _rig()
    try:
        result = sweep(scope, awg, reference_channel=1, response_channel=2, frequencies=[1000.0, 2000.0], amplitude_vpp=2.0, settle_s=0.0)
    finally:
        scope.disconnect()
        awg.disconnect()

    assert result.provenance is not None
    assert result.provenance.library_version


def test_a_timeout_aborts_with_the_points_so_far(monkeypatch):
    """A mid-sweep timeout must abort with whatever was already measured.

    The brief's own version of this test patches `Oscilloscope.get_waveform`
    and counts calls to it, expecting the sweep to fail partway through.
    Neither premise holds: `DataCollector.capture_single` never calls
    `get_waveform` at all -- it calls `self.scope.waveform.acquire(ch)`
    directly (automation.py:232), so patching `get_waveform` has no effect on
    the sweep and the original test would simply complete without raising.

    Patching `DataCollector._wait_for_acquisition` (which does propagate,
    per the brief's own warning) fixes that, but a raw "fail on the Nth
    call" threshold is equally fragile here: with this rig's defaults
    (2 Vpp, 1 V/div default scale on both channels, CUTOFF_HZ=1000), the
    FIRST point alone costs 3 captures (initial + one response rescale + one
    reference rescale, since it is also the first point), so "fail on the
    3rd call" kills point 0 before it is ever appended and `partial.points`
    comes back empty -- exactly the kind of input that looks like it
    discriminates but doesn't. Instead, the failure is armed via `on_point`
    once the first point has genuinely landed, so the assertion holds
    regardless of how many captures ranging happens to spend per point.
    """
    scope, awg = _rig()
    state = {"fail_now": False}
    original_wait = DataCollector._wait_for_acquisition

    def fail_once_armed(self, max_wait):
        if state["fail_now"]:
            raise exceptions.SiglentTimeoutError("acquisition did not complete")
        return original_wait(self, max_wait)

    def arm_after_first_point(point):
        state["fail_now"] = True

    monkeypatch.setattr(DataCollector, "_wait_for_acquisition", fail_once_armed)

    try:
        with pytest.raises(exceptions.FrequencySweepError) as caught:
            sweep(scope, awg, reference_channel=1, response_channel=2, frequencies=[1000.0, 2000.0], amplitude_vpp=2.0, settle_s=0.0, on_point=arm_after_first_point)
        partial = caught.value.partial
    finally:
        scope.disconnect()
        awg.disconnect()

    assert partial is not None
    assert len(partial.points) >= 1


def test_a_capture_failure_leaves_diagnostics_unset_not_zero(tmp_path):
    """Amendment A: a point built from no captures must not fake its geometry.

    Forces `capture_single` into its real, documented failure mode -- a
    per-channel exception it catches and logs (automation.py:229-237) -- by
    making the response channel's acquire() raise. `_measure_point` must then
    build a capture-failed ResponsePoint with reference_vpp, response_vpp,
    cycles_in_window and samples_per_cycle all left None (not 0.0), and
    to_csv must serialize those as empty fields, not "0.0". A 0.0 there would
    read as "the reference measured flat" -- a wrong diagnosis, not a missing
    one.
    """
    scope, awg = _rig()
    original_acquire = scope.waveform.acquire

    def fail_for_response_channel(channel, *args, **kwargs):
        if channel == 2:
            raise RuntimeError("simulated capture failure")
        return original_acquire(channel, *args, **kwargs)

    scope.waveform.acquire = fail_for_response_channel
    try:
        result = sweep(scope, awg, reference_channel=1, response_channel=2, frequencies=[1000.0], amplitude_vpp=2.0, settle_s=0.0)
    finally:
        scope.disconnect()
        awg.disconnect()

    point = result.points[0]
    assert point.gain_db is None
    assert point.excluded_reason == "capture failed for channel 2"
    assert point.reference_vpp is None
    assert point.response_vpp is None
    assert point.cycles_in_window is None
    assert point.samples_per_cycle is None

    path = tmp_path / "sweep.csv"
    result.to_csv(path)
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(line for line in handle if not line.startswith("#")))
    row = rows[0]
    assert row["reference_vpp"] == ""
    assert row["response_vpp"] == ""
    assert row["cycles_in_window"] == ""
    assert row["samples_per_cycle"] == ""


def test_a_measured_point_keeps_real_diagnostics_in_csv(tmp_path):
    """Amendment A's counterpart: a real capture must still serialize real numbers."""
    scope, awg = _rig()
    try:
        result = sweep(scope, awg, reference_channel=1, response_channel=2, frequencies=[CUTOFF_HZ], amplitude_vpp=2.0, settle_s=0.0)
    finally:
        scope.disconnect()
        awg.disconnect()

    point = result.points[0]
    path = tmp_path / "sweep.csv"
    result.to_csv(path)
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(line for line in handle if not line.startswith("#")))
    row = rows[0]
    assert row["reference_vpp"] != ""
    assert row["response_vpp"] != ""
    assert row["cycles_in_window"] != ""
    assert row["samples_per_cycle"] != ""
    assert float(row["reference_vpp"]) == pytest.approx(point.reference_vpp)
    assert float(row["response_vpp"]) == pytest.approx(point.response_vpp)
    assert float(row["cycles_in_window"]) == pytest.approx(point.cycles_in_window)
    assert float(row["samples_per_cycle"]) == pytest.approx(point.samples_per_cycle)


def test_amendment_b_reference_is_ranged_only_at_the_first_occurrence(monkeypatch):
    """Amendment B: a duplicated first frequency must not re-range the reference.

    `sweep()` used to compute `first=frequency == resolved[0]`, which marks
    EVERY occurrence of a duplicated first frequency as "first". Under this
    rig's defaults that bug is invisible to a plain write-count assertion:
    the reference amplitude is constant by construction, so the second
    "first" visit recomputes the SAME target scale as the first, the
    equality guard in `_measure_point` sees no change, and no second write
    happens either way -- a test that just counts writes here would pass
    whether or not the index-based fix is applied.

    To actually discriminate the bug, the reference channel's scale is
    perturbed (bypassing the spy) between the second and third points, via
    `on_point`, so the second "first" visit's target genuinely differs from
    the current scale. The buggy formula would then issue a second write;
    the fixed, index-based `first=(index == 0)` must not.
    """
    scope, awg = _rig()
    reference = scope.get_channel(1)
    sets = []
    original_setter = Channel.voltage_scale.fset

    def spy_setter(self, value):
        if self._channel == 1:
            sets.append(value)
        original_setter(self, value)

    monkeypatch.setattr(Channel, "voltage_scale", property(Channel.voltage_scale.fget, spy_setter))

    def perturb_after_second_point(point):
        if point.frequency_hz == 2000.0:
            original_setter(reference, 2.0)  # bypasses the spy: simulates an external change, not a ranging decision

    try:
        sweep(
            scope,
            awg,
            reference_channel=1,
            response_channel=2,
            frequencies=[1000.0, 2000.0, 1000.0],
            amplitude_vpp=2.0,
            settle_s=0.0,
            on_point=perturb_after_second_point,
        )
    finally:
        scope.disconnect()
        awg.disconnect()

    assert len(sets) == 1
