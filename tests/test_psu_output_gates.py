"""SPD3303X CH3 gates (capability-honesty Task 3)."""

import pytest

from scpi_control import exceptions
from scpi_control.connection.mock import MockConnection
from scpi_control.power_supply import PowerSupply
from scpi_control.power_supply_output import PowerSupplyOutput
from scpi_control.psu_models import OutputSpec

SPD3303X_IDN = "Siglent Technologies,SPD3303X,SPD00001130025,1.01.01.01.02,V3.0"


def make_psu():
    # MockConnection's `idn` kwarg configures the scope identity; PSU mode
    # needs psu_mode=True with psu_idn set instead (see test_power_supply.py's
    # mock_psu fixture) or the mock falls back to legacy-scope emulation and
    # every PSU query above times out regardless of the gates under test.
    conn = MockConnection(psu_mode=True, psu_idn=SPD3303X_IDN)
    psu = PowerSupply("mock", connection=conn)
    psu.connect()
    return psu, conn


class TestCh3Gated:
    @pytest.mark.parametrize("action", [
        lambda o: o.voltage,
        lambda o: setattr(o, "voltage", 3.3),
        lambda o: o.current,
        lambda o: setattr(o, "current", 1.0),
        lambda o: o.enabled,
        lambda o: o.measure_voltage(),
        lambda o: o.measure_current(),
        lambda o: o.measure_power(),
        lambda o: o.get_mode(),
        lambda o: o.timer_enabled,
        lambda o: setattr(o, "timer_enabled", True),
        lambda o: o.waveform_enabled,
        lambda o: setattr(o, "waveform_enabled", True),
    ])
    def test_unsupported_ch3_operations_raise_before_the_wire(self, action):
        psu, conn = make_psu()
        conn.command_log.clear()
        with pytest.raises(exceptions.FeatureNotSupportedError):
            action(psu.output3)
        assert conn.command_log == []

    def test_the_gate_is_also_a_not_implemented_error(self):
        psu, _ = make_psu()
        with pytest.raises(NotImplementedError):
            psu.output3.voltage = 3.3


class TestCh3StillSwitchable:
    def test_enable_and_disable_reach_the_wire(self):
        # OUTPut {CH1|CH2|CH3},{ON|OFF} -- QS0503X-E01B p.40.
        psu, conn = make_psu()
        conn.command_log.clear()
        psu.output3.enable()
        psu.output3.disable()
        assert any("CH3" in c and "ON" in c.upper() for c in conn.command_log)
        assert any("CH3" in c and "OFF" in c.upper() for c in conn.command_log)


class TestEnabledSetterIsActuallyGated:
    def test_switchable_false_blocks_the_setter_before_the_wire(self):
        # TestCh3StillSwitchable proves the setter works when switchable is
        # True; this proves it is actually gated, by using an output whose
        # spec turns switchable OFF (a hypothetical output, not CH3, so this
        # can't be satisfied by any other flag CH3 happens to have set).
        psu, conn = make_psu()
        spec = OutputSpec(1, 30.0, 3.0, 90.0, 0.001, 0.001, switchable=False)
        output = PowerSupplyOutput(psu, spec)
        conn.command_log.clear()
        with pytest.raises(exceptions.FeatureNotSupportedError):
            output.enabled = True
        assert conn.command_log == []


class TestOtherOutputsUnaffected:
    def test_ch1_and_ch2_are_untouched(self):
        psu, _ = make_psu()
        for output in (psu.output1, psu.output2):
            output.voltage = 5.0
            assert output.voltage == pytest.approx(5.0)
            output.enable()
            assert output.measure_voltage() is not None


class TestGetConfigurationDegrades:
    def test_ch3_configuration_reports_what_it_can_without_raising(self):
        psu, _ = make_psu()
        config = psu.output3.get_configuration()
        assert config["output"] == 3
        # Unsupported readings are absent, not fabricated:
        assert "voltage_setpoint" not in config
        assert "measured_voltage" not in config
        # ...and the flags explain why:
        assert config["capabilities"]["programmable"] is False
        assert config["capabilities"]["switchable"] is True

    def test_ch1_configuration_still_has_the_full_set(self):
        psu, _ = make_psu()
        config = psu.output1.get_configuration()
        assert "voltage_setpoint" in config and "measured_voltage" in config


class TestMockRefusesUndocumentedCh3Commands:
    """Without this the gate is untested: the driver simply stops sending, and
    nothing proves the firmware would have refused."""

    @pytest.mark.parametrize("command,get_state,baseline", [
        # Baselines read from MockConnection.__init__ (mock/base.py:263-271):
        # psu_outputs[3] = {"voltage": 0.0, "current": 0.0, "enabled": False},
        # psu_timer_enabled[3] = False, psu_waveform_enabled[3] = False.
        ("CH3:VOLTage 3.3", lambda conn: conn.psu_outputs[3]["voltage"], 0.0),
        ("CH3:CURRent 1.0", lambda conn: conn.psu_outputs[3]["current"], 0.0),
        ("TIMEr CH3,ON", lambda conn: conn.psu_timer_enabled[3], False),
        ("OUTPut:WAVE CH3,ON", lambda conn: conn.psu_waveform_enabled[3], False),
    ])
    def test_undocumented_ch3_writes_queue_minus_224(self, command, get_state, baseline):
        _, conn = make_psu()
        conn.error_queue.clear()
        conn.write(command)  # bypass the driver gate
        assert conn.error_queue == [(-224, "Illegal parameter value")]
        # The established mock contract is "error queued, state unchanged,
        # command consumed" -- a bypassed guard that both wrote the value
        # AND queued an error would still pass an error_queue-only check.
        assert get_state(conn) == baseline

    def test_output_switching_on_ch3_is_accepted(self):
        # QS0503X-E01B p.40 documents CH3 here, so the mock must NOT reject it.
        _, conn = make_psu()
        conn.error_queue.clear()
        conn.write("OUTPut CH3,ON")
        assert conn.error_queue == []

    @pytest.mark.parametrize("command", ["CH1:VOLTage 5.0", "CH2:CURRent 1.0", "TIMEr CH1,ON"])
    def test_documented_ch1_ch2_commands_still_accepted(self, command):
        _, conn = make_psu()
        conn.error_queue.clear()
        conn.write(command)
        assert conn.error_queue == []

    @pytest.mark.parametrize("command,get_state", [
        # A generic multi-output PSU is not an SPD3303X: the guard only
        # fires when the matched prefix is CH, so SOUR<n>: must stay
        # unrestricted for any channel number, including out-of-range ones
        # for the SPD3303X specifically (mock/base.py capture-and-compare
        # `prefix == "CH"` guard).
        ("SOUR3:VOLT 5.0", lambda conn: conn.psu_outputs[3]["voltage"]),
        ("SOUR3:CURR 1.0", lambda conn: conn.psu_outputs[3]["current"]),
    ])
    def test_generic_source_spelling_on_ch3_is_not_rejected(self, command, get_state):
        _, conn = make_psu()
        conn.error_queue.clear()
        conn.write(command)
        assert conn.error_queue == []
        # Also confirm it's genuinely accepted (state changed), not just
        # silently dropped -- CH3 is already a key in psu_outputs by
        # default, so a bypassed write would land here.
        assert get_state(conn) == pytest.approx(5.0 if "VOLT" in command else 1.0)
