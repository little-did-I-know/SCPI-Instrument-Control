import pytest

from siglent.automation import DataCollector, TriggerWaitCollector
from siglent.connection.mock import MockConnection


class FakeTime:
    def __init__(self, step: float = 0.02):
        self.t = 0.0
        self.step = step

    def time(self):
        self.t += self.step
        return self.t

    def sleep(self, seconds: float):
        self.t += seconds


@pytest.fixture
def mock_connection():
    return MockConnection(
        channel_states={1: True, 2: False},
        sample_rate=1_000.0,
        timebase=1e-3,
    )


@pytest.fixture
def collector(mock_connection):
    dc = DataCollector("mock", connection=mock_connection)
    dc.connect()
    yield dc
    dc.disconnect()


def test_capture_single_uses_channel_enabled_and_waveform_acquire(monkeypatch, collector):
    fake_time = FakeTime()
    monkeypatch.setattr("siglent.automation.time", fake_time)

    waveforms = collector.capture_single([1, 2])

    assert list(waveforms.keys()) == [1]
    assert collector.scope._connection.waveform_requests == [1]
    assert collector.scope._connection.writes[:3] == ["TRIG_MODE SINGLE", "ARM", "C1:WF? DAT2"]


def test_batch_capture_applies_timebase_and_scale(monkeypatch, collector):
    fake_time = FakeTime()
    monkeypatch.setattr("siglent.automation.time", fake_time)

    progress_updates = []

    results = collector.batch_capture(
        channels=[1],
        timebase_scales=["1e-3", "2e-3"],
        voltage_scales={1: [0.5, 1.0]},
        triggers_per_config=2,
        progress_callback=lambda current, total, status: progress_updates.append((current, total, status)),
    )

    connection = collector.scope._connection
    assert len(results) == 8  # 4 configs * 2 triggers
    assert connection.timebase_updates == [0.001, 0.001, 0.002, 0.002]
    assert connection.scale_updates[1] == [0.5, 1.0, 0.5, 1.0]
    assert connection.waveform_requests == [1] * 8
    assert len(progress_updates) == 8


def test_start_continuous_capture_uses_trigger_mode(monkeypatch, collector):
    fake_time = FakeTime(step=0.01)
    monkeypatch.setattr("siglent.automation.time", fake_time)

    captures = collector.start_continuous_capture(
        channels=[1],
        duration=0.1,
        interval=0.02,
        output_dir=None,
        progress_callback=lambda *_: None,
    )

    connection = collector.scope._connection
    assert connection.trigger_mode == "AUTO"
    assert len(captures) > 1
    assert connection.waveform_requests == [1] * len(captures)


def test_trigger_wait_collector_waits_for_stop(monkeypatch):
    connection = MockConnection(
        channel_states={1: True},
        trigger_status=["Run", "Run", "Stop"],
        sample_rate=1_000.0,
    )
    collector = TriggerWaitCollector("mock", connection=connection)
    collector.collector.connect()

    fake_time = FakeTime()
    monkeypatch.setattr("siglent.automation.time", fake_time)

    waveforms = collector.wait_for_trigger([1], max_wait=0.5, save_on_trigger=False)

    collector.collector.disconnect()

    assert waveforms is not None
    assert connection.waveform_requests == [1]
    assert "ARM" in connection.writes
    assert connection.queries.count(":TRIG:STAT?") >= 1
