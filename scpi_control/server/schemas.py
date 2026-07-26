"""Pydantic wire models (requires the [web] extra; Python >= 3.9)."""

from typing import Any, Dict, Optional

from pydantic import BaseModel

ALLOWED_MEASUREMENTS = frozenset({"PKPK", "MAX", "MIN", "AMPL", "TOP", "BASE", "CMEAN", "MEAN", "RMS", "CRMS", "FREQ", "PER", "RISE", "FALL", "WID", "NWID", "DUTY"})
ALLOWED_COUPLING = frozenset({"DC", "AC", "GND"})
ALLOWED_WINDOWS = frozenset({"rectangular", "hanning", "hamming", "blackman", "bartlett", "flattop"})
ALLOWED_FILTER_KINDS = frozenset({"lowpass", "highpass", "bandpass"})


class SessionCreate(BaseModel):
    label: str = ""
    kind: str = "scope"
    address: Optional[str] = None
    port: int = 5025
    mock: bool = False
    model: Optional[str] = None


class SessionOut(BaseModel):
    id: str
    label: str
    kind: str
    mock: bool
    address: Optional[str]
    state: str
    idn: str
    model: str
    dialect: str
    num_channels: int
    viewers: int = 0
    owner: str = ""


class ChannelPatch(BaseModel):
    enabled: Optional[bool] = None
    voltage_scale: Optional[float] = None
    voltage_offset: Optional[float] = None
    coupling: Optional[str] = None
    probe_ratio: Optional[float] = None


class TimebasePatch(BaseModel):
    timebase: float


class TriggerPatch(BaseModel):
    mode: Optional[str] = None
    source: Optional[str] = None
    level: Optional[float] = None
    slope: Optional[str] = None
    coupling: Optional[str] = None


class MeasurementItem(BaseModel):
    channel: int
    mtype: str


class CommandIn(BaseModel):
    command: str


class MathPatch(BaseModel):
    expression: Optional[str] = None
    enabled: Optional[bool] = None


class SpectrumPatch(BaseModel):
    enabled: Optional[bool] = None
    channel: Optional[int] = None
    window: Optional[str] = None
    db: Optional[bool] = None


class FilterPatch(BaseModel):
    enabled: Optional[bool] = None
    source: Optional[int] = None
    kind: Optional[str] = None
    cutoff_low: Optional[float] = None
    cutoff_high: Optional[float] = None
    order: Optional[int] = None


class ReferenceCreate(BaseModel):
    name: str
    channel: int


class ReferencePut(BaseModel):
    name: Optional[str] = None


class OwnerPut(BaseModel):
    name: str


class PsuOutputPatch(BaseModel):
    voltage: Optional[float] = None
    current: Optional[float] = None


class PsuEnablePatch(BaseModel):
    enabled: bool


class ModelOut(BaseModel):
    model_name: str
    series: str
    num_channels: int
    bandwidth_mhz: int
    dialect: str


def session_out(session) -> Dict[str, Any]:
    return SessionOut(
        id=session.id,
        label=session.label,
        kind=session.kind,
        mock=session.mock,
        address=session.address,
        state=session.state,
        idn=session.idn,
        model=session.model,
        dialect=session.dialect,
        num_channels=session.num_channels,
        viewers=session.viewers,
        owner=session.owner,
    ).model_dump()
