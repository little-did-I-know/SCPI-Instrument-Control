"""Acquisition provenance: which instrument produced a waveform, configured how.

Snapshots are taken at acquisition time so the recorded settings reflect the
state that actually produced the trace. Every field is Optional: a model that
cannot answer a query records None instead of failing the acquisition.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class InstrumentInfo:
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    firmware: Optional[str] = None


@dataclass(frozen=True)
class ChannelSettings:
    channel: Optional[int] = None
    enabled: Optional[bool] = None
    coupling: Optional[str] = None
    voltage_scale: Optional[float] = None
    voltage_offset: Optional[float] = None
    probe_ratio: Optional[float] = None
    bandwidth_limit: Optional[str] = None
    unit: Optional[str] = None


@dataclass(frozen=True)
class TriggerSettings:
    mode: Optional[str] = None
    trigger_type: Optional[str] = None
    source: Optional[str] = None
    level: Optional[float] = None
    slope: Optional[str] = None
    coupling: Optional[str] = None
    holdoff: Optional[float] = None


@dataclass(frozen=True)
class AcquisitionProvenance:
    schema_version: int = SCHEMA_VERSION
    instrument: Optional[InstrumentInfo] = None
    channels: Dict[int, ChannelSettings] = field(default_factory=dict)
    trigger: Optional[TriggerSettings] = None
    timebase: Optional[float] = None
    sample_rate: Optional[float] = None
    acquired_at: Optional[str] = None
    address: Optional[str] = None
    dialect: Optional[str] = None
    library_version: Optional[str] = None

    @classmethod
    def from_scope(cls, scope: Any, channels: Optional[List[int]] = None) -> "AcquisitionProvenance":
        """Snapshot the scope's current state. Never raises: unavailable settings become None."""
        instrument = None
        info = getattr(scope, "device_info", None)
        if info:
            instrument = InstrumentInfo(manufacturer=info.get("manufacturer"), model=info.get("model"), serial=info.get("serial"), firmware=info.get("firmware"))

        channel_settings: Dict[int, ChannelSettings] = {}
        for n in channels or []:
            config = None
            try:
                ch = scope.get_channel(n)
                if ch is not None:
                    config = ch.get_configuration()
            except Exception:
                logger.debug("Provenance: channel %s configuration unavailable", n, exc_info=True)
            if config is None:
                channel_settings[n] = ChannelSettings(channel=n)
            else:
                channel_settings[n] = ChannelSettings(
                    channel=n,
                    enabled=config.get("enabled"),
                    coupling=config.get("coupling"),
                    voltage_scale=config.get("voltage_scale"),
                    voltage_offset=config.get("voltage_offset"),
                    probe_ratio=config.get("probe_ratio"),
                    bandwidth_limit=config.get("bandwidth_limit"),
                    unit=config.get("unit"),
                )

        trigger = None
        try:
            tconf = scope.trigger.get_configuration()
            trigger = TriggerSettings(
                mode=tconf.get("mode"),
                trigger_type=tconf.get("type"),
                source=tconf.get("source"),
                level=tconf.get("level"),
                slope=tconf.get("slope"),
                coupling=tconf.get("coupling"),
                holdoff=tconf.get("holdoff"),
            )
        except Exception:
            logger.debug("Provenance: trigger configuration unavailable", exc_info=True)

        timebase = None
        try:
            timebase = scope.timebase
        except Exception:
            logger.debug("Provenance: timebase unavailable", exc_info=True)

        sample_rate = None
        try:
            sample_rate = scope.waveform._get_sample_rate()
        except Exception:
            logger.debug("Provenance: sample rate unavailable", exc_info=True)

        address = None
        host = getattr(scope, "host", None)
        if host:
            address = "{0}:{1}".format(host, getattr(scope, "port", ""))

        from scpi_control import __version__

        return cls(
            instrument=instrument,
            channels=channel_settings,
            trigger=trigger,
            timebase=timebase,
            sample_rate=sample_rate,
            acquired_at=datetime.now(timezone.utc).isoformat(),
            address=address,
            dialect=getattr(scope, "dialect", None),
            library_version=__version__,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "instrument": asdict(self.instrument) if self.instrument is not None else None,
            "channels": {str(n): asdict(cs) for n, cs in self.channels.items()},
            "trigger": asdict(self.trigger) if self.trigger is not None else None,
            "timebase": self.timebase,
            "sample_rate": self.sample_rate,
            "acquired_at": self.acquired_at,
            "address": self.address,
            "dialect": self.dialect,
            "library_version": self.library_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AcquisitionProvenance":
        instrument = InstrumentInfo(**data["instrument"]) if data.get("instrument") else None
        trigger = TriggerSettings(**data["trigger"]) if data.get("trigger") else None
        channels = {int(n): ChannelSettings(**cs) for n, cs in (data.get("channels") or {}).items()}
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            instrument=instrument,
            channels=channels,
            trigger=trigger,
            timebase=data.get("timebase"),
            sample_rate=data.get("sample_rate"),
            acquired_at=data.get("acquired_at"),
            address=data.get("address"),
            dialect=data.get("dialect"),
            library_version=data.get("library_version"),
        )

    @classmethod
    def from_json(cls, text: str) -> "AcquisitionProvenance":
        return cls.from_dict(json.loads(text))
