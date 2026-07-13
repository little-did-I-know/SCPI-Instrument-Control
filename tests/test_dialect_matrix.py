"""The same public-API scenarios drive both SCPI dialects with the correct wire traffic."""

import pytest

from scpi_control import Oscilloscope
from scpi_control.automation import TriggerWaitCollector
from scpi_control.connection.mock import MockConnection

IDN = {
    "legacy": "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0",
    "modern": "Siglent Technologies,SDS824X HD,MOCK0002,3.8.12",
}

WIRE = {
    "legacy": {
        "chdr": True,
        "mode_norm": "TRIG_MODE NORM",
        "source": "TRIG_SELECT EDGE,SR,C2",
        "vdiv": "C1:VDIV 0.5",
        "coupling_ac": "C1:CPL A1M",
        "tdiv": "TDIV 0.002",
        "run": "TRIG_MODE AUTO",
        "stop": "STOP",
        "status_q": "SAST?",
    },
    "modern": {
        "chdr": False,
        "mode_norm": ":TRIGger:MODE NORMal",
        "source": ":TRIGger:EDGE:SOURce C2",
        "vdiv": ":CHANnel1:SCALe 0.5",
        "coupling_ac": ":CHANnel1:COUPling AC",
        "tdiv": ":TIMebase:SCALe 0.002",
        "run": ":TRIGger:RUN",
        "stop": ":TRIGger:STOP",
        "status_q": ":TRIGger:STATus?",
    },
}


@pytest.fixture(params=["legacy", "modern"])
def rig(request):
    dialect = request.param
    conn = MockConnection("mock", idn=IDN[dialect], channel_states={1: True, 2: True}, trigger_status=["Ready", "Trig'd", "Stop"], sample_rate=1_000.0, timebase=1e-3)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    yield dialect, scope, conn
    scope.disconnect()


def test_chdr_only_on_legacy(rig):
    dialect, scope, conn = rig
    assert ("CHDR OFF" in conn.writes) == WIRE[dialect]["chdr"]


def test_trigger_config_wire(rig):
    dialect, scope, conn = rig
    scope.trigger.mode = "NORM"
    scope.trigger.source = "C2"
    assert WIRE[dialect]["mode_norm"] in conn.writes
    assert WIRE[dialect]["source"] in conn.writes


def test_channel_config_wire(rig):
    dialect, scope, conn = rig
    scope.channel1.voltage_scale = 0.5
    scope.channel1.coupling = "AC"
    assert WIRE[dialect]["vdiv"] in conn.writes
    assert WIRE[dialect]["coupling_ac"] in conn.writes
    assert scope.channel1.coupling == "AC"  # reads back through the mapper


def test_timebase_run_stop_status(rig):
    dialect, scope, conn = rig
    scope.timebase = 0.002
    scope.run()
    scope.stop()
    status = scope.acquisition_status()
    assert WIRE[dialect]["tdiv"] in conn.writes
    assert WIRE[dialect]["run"] in conn.writes
    assert WIRE[dialect]["stop"] in conn.writes
    assert status in {"ARM", "READY", "AUTO", "TRIGD", "STOP", "ROLL"}
    assert WIRE[dialect]["status_q"] in conn.queries


def test_get_waveform_wire_and_value(rig):
    # Regression check for the modern-dialect bare-NR3 parsing gap found via
    # this task's end-to-end smoke test: get_waveform() used to raise
    # CommandError on modern scopes because :CHANnel:SCALe? / :TIMebase:SCALe?
    # etc. return unit-less values (guide pp.46,56,58,476).
    dialect, scope, conn = rig
    scope.channel1.voltage_scale = 0.5
    waveform = scope.get_waveform(1)
    assert waveform.voltage_scale == pytest.approx(0.5)
    assert len(waveform.voltage) > 0


@pytest.mark.parametrize("dialect", ["legacy", "modern"])
def test_wait_for_trigger_normal_mode_both_dialects(monkeypatch, dialect):
    conn = MockConnection("mock", idn=IDN[dialect], channel_states={1: True}, trigger_status=["Ready", "Ready", "Trig'd"], sample_rate=1_000.0)
    tc = TriggerWaitCollector("mock", connection=conn)
    tc.collector.connect()

    from tests.test_automation import FakeTime

    fake_time = FakeTime()
    monkeypatch.setattr("scpi_control.automation.time", fake_time)

    tc.collector.scope.trigger.set_mode("NORMAL")
    waveforms = tc.wait_for_trigger([1], max_wait=0.5, save_on_trigger=False)

    tc.collector.disconnect()

    assert waveforms is not None
    assert WIRE[dialect]["status_q"] in conn.queries
