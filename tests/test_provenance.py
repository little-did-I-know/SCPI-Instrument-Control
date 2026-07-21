"""Tests for acquisition provenance snapshots."""

from unittest.mock import Mock

from scpi_control.provenance import (
    SCHEMA_VERSION,
    AcquisitionProvenance,
    ChannelSettings,
    InstrumentInfo,
    TriggerSettings,
)


def _fake_scope():
    scope = Mock()
    scope.device_info = {"manufacturer": "Siglent Technologies", "model": "SDS824X HD", "serial": "SER123", "firmware": "1.0.0.0"}
    scope.host = "192.168.1.50"
    scope.port = 5025
    scope.dialect = "modern"
    scope.timebase = 1e-3
    scope.waveform._get_sample_rate.return_value = 1_000_000.0
    channel = Mock()
    channel.get_configuration.return_value = {
        "channel": 1,
        "enabled": True,
        "coupling": "DC",
        "voltage_scale": 0.5,
        "voltage_offset": 0.0,
        "probe_ratio": 10.0,
        "bandwidth_limit": "OFF",
        "unit": "V",
    }
    scope.get_channel.return_value = channel
    scope.trigger.get_configuration.return_value = {
        "mode": "AUTO",
        "type": "EDGE",
        "source": "C1",
        "level": 0.1,
        "slope": "RISING",
        "coupling": "DC",
        "holdoff": None,
    }
    return scope


class _BrokenScope:
    device_info = None
    host = None
    dialect = None

    @property
    def timebase(self):
        raise RuntimeError("no timebase")

    def get_channel(self, n):
        raise RuntimeError("boom")

    class _T:
        def get_configuration(self):
            raise NotImplementedError()

    trigger = _T()

    class _W:
        def _get_sample_rate(self):
            raise RuntimeError("boom")

    waveform = _W()


def test_from_scope_snapshots_everything():
    prov = AcquisitionProvenance.from_scope(_fake_scope(), channels=[1])
    assert prov.schema_version == SCHEMA_VERSION
    assert prov.instrument.model == "SDS824X HD"
    assert prov.channels[1].voltage_scale == 0.5
    assert prov.channels[1].probe_ratio == 10.0
    assert prov.trigger.source == "C1"
    assert prov.trigger.trigger_type == "EDGE"
    assert prov.timebase == 1e-3
    assert prov.sample_rate == 1_000_000.0
    assert prov.address == "192.168.1.50:5025"
    assert prov.dialect == "modern"
    assert prov.library_version
    assert prov.acquired_at  # ISO-8601 UTC string


def test_from_scope_tolerates_every_failure():
    scope = _BrokenScope()
    prov = AcquisitionProvenance.from_scope(scope, channels=[1])
    assert prov.instrument is None
    assert prov.channels[1] == ChannelSettings(channel=1)
    assert prov.trigger is None
    assert prov.timebase is None
    assert prov.sample_rate is None
    assert prov.address is None


def test_json_round_trip():
    prov = AcquisitionProvenance.from_scope(_fake_scope(), channels=[1])
    restored = AcquisitionProvenance.from_json(prov.to_json())
    assert restored == prov


def test_from_dict_tolerates_missing_keys():
    prov = AcquisitionProvenance.from_dict({"schema_version": 1})
    assert prov.instrument is None
    assert prov.channels == {}
    assert prov.trigger is None
