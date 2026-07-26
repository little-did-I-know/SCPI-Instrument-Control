"""The mock's SCPI error queue.

Real instruments accept a bad command, ignore it, and queue an error for later
collection. The mock used to answer '+0,"No error"' unconditionally, so
FunctionGenerator.get_error() and DataLogger.get_error() could only ever report
perfect health and no caller-side error handling was reachable in tests.
"""

import pytest

from scpi_control.connection.mock import MockConnection

NO_ERROR = '+0,"No error"'


def _conn(**kwargs):
    conn = MockConnection(**kwargs)
    conn.connect()
    return conn


@pytest.mark.parametrize("mode", ["daq_mode", "awg_mode", "psu_mode"])
def test_empty_queue_reports_no_error(mode):
    """All three instrument classes that expose get_error() must be able to ask.
    Only daq_mode answered before -- awg_mode and psu_mode timed out, so
    FunctionGenerator.get_error() and PowerSupply.get_error() were unusable
    against the mock entirely."""
    assert _conn(**{mode: True}).query("SYST:ERR?") == NO_ERROR


def test_errors_pop_oldest_first_then_drain_to_no_error():
    conn = _conn(awg_mode=True)
    conn.push_error(-222, "Data out of range")
    conn.push_error(-113, "Undefined header")

    assert conn.query("SYST:ERR?") == '-222,"Data out of range"'
    assert conn.query("SYST:ERR?") == '-113,"Undefined header"'
    assert conn.query("SYST:ERR?") == NO_ERROR


def test_cls_clears_the_queue():
    """*CLS is the standard way to clear status; the mock ignored it entirely."""
    conn = _conn(awg_mode=True)
    conn.push_error(-222, "Data out of range")
    conn.write("*CLS")
    assert conn.query("SYST:ERR?") == NO_ERROR


def test_rst_also_clears_the_queue():
    """M7: real instruments clear the error queue on both *CLS and *RST --
    *RST used to fall through unmatched (a silent no-op), so a caller
    resetting after an error would still see it queued on the next
    SYST:ERR?."""
    conn = _conn(awg_mode=True)
    conn.push_error(-222, "Data out of range")
    conn.write("*RST")
    assert conn.query("SYST:ERR?") == NO_ERROR


def test_scope_mode_still_has_no_error_query():
    """Scopes deliberately have no get_error -- scope.get_error() raises
    NotImplementedError and test_scpi_command_tables.py:38 asserts the command's
    absence. Adding a wire-level accessor here would quietly undo that gating, so
    scope mode must keep timing out. The queue itself still works; it just has no
    SCPI accessor, which matches the library's model."""
    from scpi_control import exceptions

    conn = _conn()  # default = scope mode
    with pytest.raises(exceptions.SiglentTimeoutError):
        conn.query("SYST:ERR?")


import math

from scpi_control import exceptions

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"


@pytest.mark.parametrize(
    "value",
    [1e9, -5.0, 0.0, float("nan"), float("inf")],
    ids=["absurd", "negative", "zero", "nan", "inf"],
)
def test_invalid_voltage_scale_is_rejected_and_queued(value):
    conn = _conn(idn=LEGACY_IDN)
    before = conn._voltage_scales.get(1)

    conn.write("C1:VDIV {0}".format(value))

    assert conn._voltage_scales.get(1) == before, "a rejected command must not change state"
    # Scope mode has no SYST:ERR? accessor (scopes expose no get_error), so assert
    # on the queue attribute directly rather than over the wire.
    assert conn.error_queue == [(-222, "Data out of range (VDIV)")]


def test_valid_voltage_scale_is_accepted_and_queues_nothing():
    conn = _conn(idn=LEGACY_IDN)
    conn.write("C1:VDIV 0.5")
    assert conn._voltage_scales[1] == 0.5
    assert conn.error_queue == []


MODERN_IDN = "Siglent Technologies,SDS824X HD,MOCK0002,3.8.12"


@pytest.mark.parametrize(
    "value",
    [-5.0, 0.0, float("nan"), float("inf")],
    ids=["negative", "zero", "nan", "inf"],
)
def test_invalid_probe_attenuation_is_rejected_and_queued(value):
    conn = _conn(idn=LEGACY_IDN)
    before = conn.probe_ratios.get(1)

    conn.write("C1:ATTN {0}".format(value))

    assert conn.probe_ratios.get(1) == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (ATTN)")]


def test_valid_probe_attenuation_is_accepted_and_queues_nothing():
    conn = _conn(idn=LEGACY_IDN)
    conn.write("C1:ATTN 10")
    assert conn.probe_ratios[1] == 10.0
    assert conn.error_queue == []


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf")],
    ids=["nan", "inf"],
)
def test_invalid_legacy_trigger_level_is_rejected_and_queued(value):
    conn = _conn(idn=LEGACY_IDN)
    before = conn.trigger_level.get(1)

    conn.write("C1:TRLV {0}".format(value))

    assert conn.trigger_level.get(1) == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (TRLV)")]


def test_valid_negative_legacy_trigger_level_is_accepted_and_queues_nothing():
    """positive=False must still be honored -- a legitimately negative trigger
    level must NOT be rejected. Getting this backwards would be a worse bug
    than the one being fixed."""
    conn = _conn(idn=LEGACY_IDN)
    conn.write("C1:TRLV -0.5")
    assert conn.trigger_level[1] == -0.5
    assert conn.error_queue == []


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf")],
    ids=["nan", "inf"],
)
def test_invalid_modern_trigger_level_is_rejected_and_queued(value):
    conn = _conn(idn=MODERN_IDN)
    before = conn.trigger_level.get(1)

    conn.write(":TRIGger:EDGE:LEVel {0}".format(value))

    assert conn.trigger_level.get(1) == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (TRIGger:EDGE:LEVel)")]


def test_valid_negative_modern_trigger_level_is_accepted_and_queues_nothing():
    """positive=False must still be honored -- a legitimately negative trigger
    level must NOT be rejected. Getting this backwards would be a worse bug
    than the one being fixed."""
    conn = _conn(idn=MODERN_IDN)
    conn.write(":TRIGger:EDGE:LEVel -0.5")
    assert conn.trigger_level[1] == -0.5
    assert conn.error_queue == []


def test_unimplemented_command_still_times_out_rather_than_queueing():
    """The strict-mode boundary. An UNIMPLEMENTED command must keep failing
    loudly -- that is what forces every new command to earn a wire-form corpus
    entry. Only IMPLEMENTED commands with bad parameters queue an error."""
    conn = _conn(idn=LEGACY_IDN)
    with pytest.raises(exceptions.SiglentTimeoutError):
        conn.query("C1:NOSUCHQUERY?")
    assert conn.error_queue == [], "a timeout must not also queue an error"


# ---------------------------------------------------------------------------
# Task 4: the queue becomes reachable through the public API (PowerSupply,
# FunctionGenerator, DataLogger all read SYST:ERR? via get_error()), plus
# validation for the PSU/AWG/DAQ numeric setters that feed that queue.
# ---------------------------------------------------------------------------


def test_awg_error_is_visible_through_the_public_api():
    """FunctionGenerator.get_error() reads SYST:ERR?. Before the queue existed it
    could only ever return '+0,"No error"', so no caller-side handling of a real
    instrument error was reachable in a test."""
    from scpi_control.function_generator import FunctionGenerator

    conn = _conn(awg_mode=True)
    awg = FunctionGenerator("mock", connection=conn)
    awg.connect()

    conn.push_error(-222, "Data out of range")
    assert awg.get_error() == '-222,"Data out of range"'
    assert awg.get_error() == NO_ERROR


def test_psu_error_is_visible_through_the_public_api():
    """PowerSupply.get_error() reads SYST:ERR? and used to time out entirely
    before Task 2 added the queue -- this is the first test that can exercise
    it at all."""
    from scpi_control.power_supply import PowerSupply

    conn = _conn(psu_mode=True)
    psu = PowerSupply("mock", connection=conn)
    psu.connect()

    conn.push_error(-222, "Data out of range")
    assert psu.get_error() == '-222,"Data out of range"'
    assert psu.get_error() == NO_ERROR


def test_daq_error_is_visible_through_the_public_api():
    """DataLogger.get_error() reads SYST:ERR?. daq_mode already answered
    SYST:ERR? before Task 2 (it never timed out), but this proves a real
    queued error -- not just the hardcoded '+0,"No error"' -- now surfaces
    through the public method."""
    from scpi_control.data_logger import DataLogger

    conn = _conn(daq_mode=True)
    daq = DataLogger("mock", connection=conn)
    daq.connect()

    conn.push_error(-222, "Data out of range")
    assert daq.get_error() == '-222,"Data out of range"'
    assert daq.get_error() == NO_ERROR


# --- PSU numeric setters ----------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [-5.0, 1e9, float("nan"), float("inf")],
    ids=["negative", "absurd", "nan", "inf"],
)
def test_invalid_psu_voltage_is_rejected_and_queued(value):
    """I1: the capture used to be `([\\d.]+)`, which cannot match a sign, nan,
    or inf -- these all fell straight through unmatched (no rejection, no
    state change, but also no error queued -- the guard was never reached at
    all). Brought up to the same negative/nan/inf coverage as the scope
    guards (test_invalid_voltage_scale_is_rejected_and_queued)."""
    conn = _conn(psu_mode=True)
    conn.write("CH1:VOLT {0}".format(value))
    assert conn.psu_outputs[1]["voltage"] == 0.0, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (VOLT)")]


def test_zero_psu_voltage_is_accepted_and_queues_nothing():
    """A PSU voltage setpoint of 0.0 (output at rest) is legitimate and must
    not be rejected -- power_supply_output.py's own real-driver validation
    allows `0 <= volts <= max_voltage`."""
    conn = _conn(psu_mode=True)
    conn.write("CH1:VOLT 0.0")
    assert conn.psu_outputs[1]["voltage"] == 0.0
    assert conn.error_queue == []


def test_psu_voltage_microvolt_setpoint_is_not_corrupted_by_the_regex():
    """I1 regression: `CH1:VOLT 2e-05` (what `"{0}".format(0.00002)` produces)
    used to match only the leading "2" under the old `([\\d.]+)` capture, so
    the mock silently stored 2.0V instead of 20 microvolts -- a 100000x error
    with nothing queued to reveal it."""
    conn = _conn(psu_mode=True)
    conn.write("CH1:VOLT {0}".format(0.00002))
    assert conn.psu_outputs[1]["voltage"] == 2e-05
    assert conn.error_queue == []


@pytest.mark.parametrize(
    "value",
    [-5.0, 1e9, float("nan"), float("inf")],
    ids=["negative", "absurd", "nan", "inf"],
)
def test_invalid_psu_current_is_rejected_and_queued(value):
    conn = _conn(psu_mode=True)
    conn.write("CH1:CURR {0}".format(value))
    assert conn.psu_outputs[1]["current"] == 0.0, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (CURR)")]


def test_zero_psu_current_is_accepted_and_queues_nothing():
    """A PSU current limit of 0.0 is legitimate for the same reason as
    voltage above and must not be rejected."""
    conn = _conn(psu_mode=True)
    conn.write("CH1:CURR 0.0")
    assert conn.psu_outputs[1]["current"] == 0.0
    assert conn.error_queue == []


def test_psu_current_microamp_setpoint_is_not_corrupted_by_the_regex():
    """I1 regression: `set_current(0.00005)` emits `CH1:CURR 5e-05`; the old
    `([\\d.]+)` capture matched only the leading "5" and stored 5.0A -- a
    100000x error, no error queued. Microamp-level current limits are entirely
    plausible, so this is reachable through normal public-API use."""
    conn = _conn(psu_mode=True)
    conn.write("CH1:CURR {0}".format(0.00005))
    assert conn.psu_outputs[1]["current"] == 5e-05
    assert conn.error_queue == []


@pytest.mark.parametrize(
    "value",
    [0.0, -5.0, 1e9, float("nan"), float("inf")],
    ids=["zero", "negative", "absurd", "nan", "inf"],
)
def test_invalid_psu_ovp_is_rejected_and_queued(value):
    """Unlike voltage/current setpoints, an over-voltage protection level of
    0V would trip immediately and is not a usable value, so OVP is gated on
    positivity. Negative/nan/inf coverage added alongside I1's regex widening,
    which is what makes the guard reachable for these values at all."""
    conn = _conn(psu_mode=True)
    before = conn.psu_ovp_levels[1]
    conn.write("CH1:VOLT:PROT {0}".format(value))
    assert conn.psu_ovp_levels[1] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (VOLT:PROT)")]


def test_valid_psu_ovp_is_accepted_and_queues_nothing():
    conn = _conn(psu_mode=True)
    conn.write("CH1:VOLT:PROT 25.0")
    assert conn.psu_ovp_levels[1] == 25.0
    assert conn.error_queue == []


@pytest.mark.parametrize(
    "value",
    [0.0, -5.0, 1e9, float("nan"), float("inf")],
    ids=["zero", "negative", "absurd", "nan", "inf"],
)
def test_invalid_psu_ocp_is_rejected_and_queued(value):
    """Same reasoning as OVP: an over-current protection level of 0A is not
    a usable value, so OCP is gated on positivity."""
    conn = _conn(psu_mode=True)
    before = conn.psu_ocp_levels[1]
    conn.write("CH1:CURR:PROT {0}".format(value))
    assert conn.psu_ocp_levels[1] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (CURR:PROT)")]


def test_valid_psu_ocp_is_accepted_and_queues_nothing():
    conn = _conn(psu_mode=True)
    conn.write("CH1:CURR:PROT 2.5")
    assert conn.psu_ocp_levels[1] == 2.5
    assert conn.error_queue == []


# --- AWG numeric setters -----------------------------------------------------


@pytest.mark.parametrize("value", [-1000.0, 0.0], ids=["negative", "zero"])
def test_invalid_awg_frequency_is_rejected_and_queued(value):
    """awg_output.py's real-driver validation requires `0 < freq_hz`, so
    frequency is gated on positivity."""
    conn = _conn(awg_mode=True)
    before = conn.awg_channels[1]["frequency"]
    conn.write("SOUR1:FREQ {0}".format(value))
    assert conn.awg_channels[1]["frequency"] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (FREQ)")]


def test_valid_awg_frequency_is_accepted_and_queues_nothing():
    conn = _conn(awg_mode=True)
    conn.write("SOUR1:FREQ 2500.0")
    assert conn.awg_channels[1]["frequency"] == 2500.0
    assert conn.error_queue == []


def test_valid_high_awg_frequency_is_accepted_and_queues_nothing():
    """The generic _ABSURD_MAGNITUDE bound (1e6) is calibrated for scope V/div
    and timebase; registered AWG models go up to 120MHz (awg_models.py's
    SDG2122X ChannelSpec), so frequency must use a wider bound or this rejects
    a real, in-spec value. This regression was caught by
    test_function_generator.py::TestAWGOutput::test_frequency_limit_validation
    (30MHz) failing when the guard was first added with the scope-scaled bound."""
    conn = _conn(awg_mode=True)
    conn.write("SOUR1:FREQ 1.2E8")
    assert conn.awg_channels[1]["frequency"] == 1.2e8
    assert conn.error_queue == []


@pytest.mark.parametrize("value", [-1.0, 0.0], ids=["negative", "zero"])
def test_invalid_awg_amplitude_is_rejected_and_queued(value):
    """An amplitude of 0 or negative Vpp is not a usable waveform, so
    amplitude is gated on positivity, same as scope V/div."""
    conn = _conn(awg_mode=True)
    before = conn.awg_channels[1]["amplitude"]
    conn.write("SOUR1:VOLT {0}".format(value))
    assert conn.awg_channels[1]["amplitude"] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (VOLT)")]


def test_valid_awg_amplitude_is_accepted_and_queues_nothing():
    conn = _conn(awg_mode=True)
    conn.write("SOUR1:VOLT 3.0")
    assert conn.awg_channels[1]["amplitude"] == 3.0
    assert conn.error_queue == []


def test_invalid_awg_offset_is_rejected_and_queued():
    conn = _conn(awg_mode=True)
    before = conn.awg_channels[1]["offset"]
    conn.write("SOUR1:VOLT:OFFS {0}".format(1e9))
    assert conn.awg_channels[1]["offset"] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (VOLT:OFFS)")]


def test_valid_negative_awg_offset_is_accepted_and_queues_nothing():
    """positive=False must be honored -- an AWG DC offset may legitimately be
    negative (awg_output.py's real-driver validation only checks
    `abs(volts) > max_offset`, never sign). Getting this backwards would be a
    worse bug than the one being fixed."""
    conn = _conn(awg_mode=True)
    conn.write("SOUR1:VOLT:OFFS -0.5")
    assert conn.awg_channels[1]["offset"] == -0.5
    assert conn.error_queue == []


@pytest.mark.parametrize("value", [1e9], ids=["absurd"])
def test_invalid_awg_phase_is_rejected_and_queued(value):
    conn = _conn(awg_mode=True)
    before = conn.awg_channels[1]["phase"]
    conn.write("SOUR1:PHAS {0}".format(value))
    assert conn.awg_channels[1]["phase"] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (PHAS)")]


def test_invalid_negative_awg_phase_is_rejected_and_queued():
    """I2: `SOUR1:PHAS -1000` used to be accepted and stored as -1000.0
    because `positive=False` alone allows any sign. awg_output.py's
    real-driver validation is `0 <= degrees <= 360`, so a negative phase must
    now be rejected via `non_negative=True` while zero (tested below) still
    passes."""
    conn = _conn(awg_mode=True)
    before = conn.awg_channels[1]["phase"]
    conn.write("SOUR1:PHAS -1000")
    assert conn.awg_channels[1]["phase"] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (PHAS)")]


def test_valid_zero_awg_phase_is_accepted_and_queues_nothing():
    """positive=False must be honored -- phase 0 degrees is the default and
    entirely legitimate (awg_output.py's real-driver validation allows
    `0 <= degrees <= 360`)."""
    conn = _conn(awg_mode=True)
    conn.write("SOUR1:PHAS 0.0")
    assert conn.awg_channels[1]["phase"] == 0.0
    assert conn.error_queue == []


def test_awg_phase_above_360_is_rejected_and_queued():
    """M5: a phase angle never legitimately exceeds 360 degrees, but the
    generic 1e6 scope-calibrated bound let PHAS 999999 through -- below 1e6,
    above any usable phase. Now caught by max_magnitude=360."""
    conn = _conn(awg_mode=True)
    before = conn.awg_channels[1]["phase"]
    conn.write("SOUR1:PHAS 999999")
    assert conn.awg_channels[1]["phase"] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (PHAS)")]


@pytest.mark.parametrize("value", [-10.0, 0.0], ids=["negative", "zero"])
def test_invalid_awg_pulse_duty_is_rejected_and_queued(value):
    """awg_output.py's real-driver validation requires `0 < percent < 100`
    (strictly exclusive), so duty cycle is gated on positivity -- unlike ramp
    symmetry below, 0% is not a value the real driver ever allows either."""
    conn = _conn(awg_mode=True)
    before = conn.awg_channels[1]["pulse_duty"]
    conn.write("SOUR1:FUNC:PULS:DCYC {0}".format(value))
    assert conn.awg_channels[1]["pulse_duty"] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (FUNC:PULS:DCYC)")]


def test_valid_awg_pulse_duty_is_accepted_and_queues_nothing():
    conn = _conn(awg_mode=True)
    conn.write("SOUR1:FUNC:PULS:DCYC 25.0")
    assert conn.awg_channels[1]["pulse_duty"] == 25.0
    assert conn.error_queue == []


def test_awg_pulse_duty_above_100_is_rejected_and_queued():
    """M5: a percentage never legitimately exceeds 100, but the generic 1e6
    scope-calibrated bound let FUNC:PULS:DCYC 500000 through -- below 1e6,
    nonsense for a duty cycle. Now caught by max_magnitude=100."""
    conn = _conn(awg_mode=True)
    before = conn.awg_channels[1]["pulse_duty"]
    conn.write("SOUR1:FUNC:PULS:DCYC 500000")
    assert conn.awg_channels[1]["pulse_duty"] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (FUNC:PULS:DCYC)")]


@pytest.mark.parametrize("value", [1e9], ids=["absurd"])
def test_invalid_awg_ramp_symmetry_is_rejected_and_queued(value):
    conn = _conn(awg_mode=True)
    before = conn.awg_channels[1]["ramp_symmetry"]
    conn.write("SOUR1:FUNC:RAMP:SYMM {0}".format(value))
    assert conn.awg_channels[1]["ramp_symmetry"] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (FUNC:RAMP:SYMM)")]


def test_invalid_negative_awg_ramp_symmetry_is_rejected_and_queued():
    """I2: `SOUR1:FUNC:RAMP:SYMM -50` used to be accepted and stored as -50.0
    because `positive=False` alone allows any sign. awg_output.py's
    real-driver validation is `0 <= percent <= 100`, so a negative symmetry
    must now be rejected via `non_negative=True` while zero (tested below)
    still passes."""
    conn = _conn(awg_mode=True)
    before = conn.awg_channels[1]["ramp_symmetry"]
    conn.write("SOUR1:FUNC:RAMP:SYMM -50")
    assert conn.awg_channels[1]["ramp_symmetry"] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (FUNC:RAMP:SYMM)")]


def test_valid_zero_awg_ramp_symmetry_is_accepted_and_queues_nothing():
    """positive=False must be honored -- ramp symmetry of 0% (a pure downward
    sawtooth) is entirely legitimate (awg_output.py's real-driver validation
    allows `0 <= percent <= 100` inclusive, unlike duty cycle above). Getting
    this backwards would be a worse bug than the one being fixed."""
    conn = _conn(awg_mode=True)
    conn.write("SOUR1:FUNC:RAMP:SYMM 0.0")
    assert conn.awg_channels[1]["ramp_symmetry"] == 0.0
    assert conn.error_queue == []


def test_awg_ramp_symmetry_above_100_is_rejected_and_queued():
    """M5: a percentage never legitimately exceeds 100, but the generic 1e6
    scope-calibrated bound let FUNC:RAMP:SYMM 999999 through -- below 1e6,
    nonsense for a symmetry percentage. Now caught by max_magnitude=100."""
    conn = _conn(awg_mode=True)
    before = conn.awg_channels[1]["ramp_symmetry"]
    conn.write("SOUR1:FUNC:RAMP:SYMM 999999")
    assert conn.awg_channels[1]["ramp_symmetry"] == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (FUNC:RAMP:SYMM)")]


# --- Tektronix dialect: same guard, mirrored per the Task 3 review ---------

TEK_IDN = "TEKTRONIX,TBS1102C,MOCK0101,CF:91.1CT FV:1.10"


@pytest.mark.parametrize("value", [-5.0, 0.0], ids=["negative", "zero"])
def test_invalid_tek_channel_scale_is_rejected_and_queued(value):
    conn = _conn(idn=TEK_IDN)
    before = conn._voltage_scales.get(1)
    conn.write("CH1:SCALE {0}".format(value))
    assert conn._voltage_scales.get(1) == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (SCALE)")]


def test_valid_tek_channel_scale_is_accepted_and_queues_nothing():
    conn = _conn(idn=TEK_IDN)
    conn.write("CH1:SCALE 0.5")
    assert conn._voltage_scales[1] == 0.5
    assert conn.error_queue == []


def test_invalid_tek_channel_offset_is_rejected_and_queued():
    conn = _conn(idn=TEK_IDN)
    before = conn._voltage_offsets.get(1)
    conn.write("CH1:OFFSET {0}".format(1e9))
    assert conn._voltage_offsets.get(1) == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (OFFSET)")]


def test_valid_negative_tek_channel_offset_is_accepted_and_queues_nothing():
    """positive=False must be honored -- channel offset may legitimately be
    negative. Getting this backwards would be a worse bug than the one being
    fixed."""
    conn = _conn(idn=TEK_IDN)
    conn.write("CH1:OFFSET -1.5")
    assert conn._voltage_offsets[1] == -1.5
    assert conn.error_queue == []


@pytest.mark.parametrize("value", [-5.0, 0.0], ids=["negative", "zero"])
def test_invalid_tek_tbs_probe_gain_is_rejected_and_queued(value):
    """tek_tbs spelling: CH<n>:PROBE:GAIN."""
    conn = _conn(idn=TEK_IDN)
    before = conn.probe_gains.get(1)
    conn.write("CH1:PROBE:GAIN {0}".format(value))
    assert conn.probe_gains.get(1) == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (PROBE:GAIN)")]


def test_valid_tek_tbs_probe_gain_is_accepted_and_queues_nothing():
    conn = _conn(idn=TEK_IDN)
    conn.write("CH1:PROBE:GAIN 0.01")
    assert conn.probe_gains[1] == 0.01
    assert conn.error_queue == []


@pytest.mark.parametrize("value", [-5.0, 0.0], ids=["negative", "zero"])
def test_invalid_tek_mso_probe_gain_is_rejected_and_queued(value):
    """tek_mso spelling for the same probe-gain state: CH<n>:PROBEFUNC:EXTATTEN."""
    conn = _conn(idn=TEK_IDN)
    before = conn.probe_gains.get(1)
    conn.write("CH1:PROBEFUNC:EXTATTEN {0}".format(value))
    assert conn.probe_gains.get(1) == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (PROBEFUNC:EXTATTEN)")]


def test_valid_tek_mso_probe_gain_is_accepted_and_queues_nothing():
    conn = _conn(idn=TEK_IDN)
    conn.write("CH1:PROBEFUNC:EXTATTEN 0.1")
    assert conn.probe_gains[1] == 0.1
    assert conn.error_queue == []


@pytest.mark.parametrize("value", [-5.0, 0.0], ids=["negative", "zero"])
def test_invalid_tek_horizontal_scale_is_rejected_and_queued(value):
    conn = _conn(idn=TEK_IDN)
    before = conn.timebase
    conn.write("HORIZONTAL:SCALE {0}".format(value))
    assert conn.timebase == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (HORIZONTAL:SCALE)")]


def test_valid_tek_horizontal_scale_is_accepted_and_queues_nothing():
    conn = _conn(idn=TEK_IDN)
    conn.write("HORIZONTAL:SCALE 0.001")
    assert conn.timebase == 0.001
    assert conn.error_queue == []


def test_invalid_tek_trigger_level_is_rejected_and_queued():
    conn = _conn(idn=TEK_IDN)
    before = conn.trigger_level.get(1)
    conn.write("TRIGGER:A:LEVEL:CH1 {0}".format(1e9))
    assert conn.trigger_level.get(1) == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (TRIGGER:A:LEVEL)")]


def test_valid_negative_tek_trigger_level_is_accepted_and_queues_nothing():
    """positive=False must be honored -- a legitimately negative trigger
    level must NOT be rejected. Getting this backwards would be a worse bug
    than the one being fixed."""
    conn = _conn(idn=TEK_IDN)
    conn.write("TRIGGER:A:LEVEL:CH1 -0.5")
    assert conn.trigger_level[1] == -0.5
    assert conn.error_queue == []


def test_invalid_tek_holdoff_time_is_rejected_and_queued():
    conn = _conn(idn=TEK_IDN)
    before = conn.holdoff_time
    conn.write("TRIGGER:A:HOLDOFF:TIME {0}".format(1e9))
    assert conn.holdoff_time == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (TRIGGER:A:HOLDOFF:TIME)")]


def test_invalid_negative_tek_holdoff_time_is_rejected_and_queued():
    """I2: `TRIGGER:A:HOLDOFF:TIME -5.0` used to be accepted and stored as
    -5.0 because `positive=False` alone allows any sign, even though
    trigger.py's own real-driver validation is `if time_seconds < 0: raise`.
    Now gated on `non_negative=True` instead: negative is rejected, zero
    (tested below) still passes."""
    conn = _conn(idn=TEK_IDN)
    before = conn.holdoff_time
    conn.write("TRIGGER:A:HOLDOFF:TIME -5.0")
    assert conn.holdoff_time == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (TRIGGER:A:HOLDOFF:TIME)")]


def test_valid_zero_tek_holdoff_time_is_accepted_and_queues_nothing():
    """positive=False must be honored -- trigger.py's own real-driver
    validation only rejects a NEGATIVE holdoff (`if time_seconds < 0: raise`),
    so 0 is a legitimate holdoff (no extra delay) and must NOT be rejected."""
    conn = _conn(idn=TEK_IDN)
    conn.write("TRIGGER:A:HOLDOFF:TIME 0.0")
    assert conn.holdoff_time == 0.0
    assert conn.error_queue == []


# --- LeCroy dialect: writes delegate entirely to the Siglent legacy handler,
# which Task 3 already guarded -- these tests prove that guard is actually
# reached when dispatched through lecroy.handle_write, not just siglent's own
# dialect. LeCroy's personality module defines no numeric setters of its own.

LECROY_IDN = "LECROY,WAVESURFER3024Z,MOCK0200,8.5.0"


def test_invalid_lecroy_voltage_scale_is_rejected_and_queued():
    conn = _conn(idn=LECROY_IDN)
    before = conn._voltage_scales.get(1)
    conn.write("C1:VDIV {0}".format(1e9))
    assert conn._voltage_scales.get(1) == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range (VDIV)")]


def test_valid_lecroy_voltage_scale_is_accepted_and_queues_nothing():
    conn = _conn(idn=LECROY_IDN)
    conn.write("C1:VDIV 0.5")
    assert conn._voltage_scales[1] == 0.5
    assert conn.error_queue == []


def test_valid_negative_lecroy_trigger_level_is_accepted_and_queues_nothing():
    """positive=False must be honored through the LeCroy dispatch path too --
    a legitimately negative trigger level must NOT be rejected. Getting this
    backwards would be a worse bug than the one being fixed."""
    conn = _conn(idn=LECROY_IDN)
    conn.write("C1:TRLV -0.5")
    assert conn.trigger_level[1] == -0.5
    assert conn.error_queue == []
