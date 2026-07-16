"""The report waveform is the library waveform plus report concerns.

One model owns the physics. This pins the properties that make the subclass real:
substitutability, the required-field contract, the inherited validation, and the
str-coercion the loader used to do by hand.
"""

from dataclasses import fields

import numpy as np
import pytest

from scpi_control.report_generator.models.report_data import WaveformData as ReportWaveform
from scpi_control.waveform import WaveformData as CaptureWaveform


def make_report_waveform(channel="C1", n=100, rate=1e6):
    t = np.arange(n) / rate
    return ReportWaveform(
        time=t,
        voltage=np.sin(2 * np.pi * 10_000 * t),
        channel=channel,
        sample_rate=rate,
        record_length=n,
    )


def test_a_report_waveform_is_a_capture_waveform():
    assert isinstance(make_report_waveform(), CaptureWaveform)


def test_sample_rate_and_record_length_are_genuinely_required():
    """The bare-annotation trap: `sample_rate: float` would silently inherit the
    base's None default and this contract would weaken with nothing to catch it.
    Every other test passes sample_rate, so this is the only test that would fail."""
    t = np.arange(10) / 1e6
    with pytest.raises(TypeError):
        ReportWaveform(time=t, voltage=np.ones(10), channel="C1")


def test_channel_is_coerced_to_str():
    """The loader used to do this by hand at each construction site; it is now a
    property of the type. An int 1 and a str '1' are not equal, so the coercion
    point matters."""
    wf = make_report_waveform(channel=1)
    assert wf.channel == "1"
    assert wf.label == "1"


def test_shape_validation_is_inherited():
    """The report type never validated shapes. It does now -- a malformed file
    fails loudly instead of producing a quietly broken report."""
    with pytest.raises(ValueError):
        ReportWaveform(time=np.arange(10), voltage=np.ones(9), channel="C1", sample_rate=1e6, record_length=9)


def test_report_fields_still_work():
    wf = make_report_waveform()
    assert wf.color == "#1f77b4"
    assert wf.regions == []
    wf.regions.append("x")
    assert make_report_waveform().regions == [], "regions must not be a shared mutable default"


def test_explicit_label_wins_over_the_channel_default():
    t = np.arange(10) / 1e6
    wf = ReportWaveform(time=t, voltage=np.ones(10), channel="C1", sample_rate=1e6, record_length=10, label="Probe A")
    assert wf.label == "Probe A"


def test_no_invented_timebase_on_a_report_waveform():
    """The whole reason the fabrication had to die first: this object now runs the
    library's __post_init__, and a report renders whatever timebase it finds."""
    wf = make_report_waveform()
    assert wf.timebase is None
    assert wf.voltage_scale is None


def test_field_order_is_the_library_core_then_report_concerns():
    assert [f.name for f in fields(ReportWaveform)] == [
        "time",
        "voltage",
        "channel",
        "sample_rate",
        "record_length",
        "timebase",
        "voltage_scale",
        "voltage_offset",
        "probe_ratio",
        "coupling",
        "source_file",
        "capture_timestamp",
        "color",
        "label",
        "signal_type",
        "signal_type_confidence",
        "statistics",
        "regions",
    ]


def test_a_report_waveform_can_be_saved_by_the_library(tmp_path):
    """A consequence of the is-a relationship, not a goal of it -- but worth pinning,
    because it is the property a future direct-capture path would rely on."""
    from scpi_control.waveform import Waveform

    p = tmp_path / "cap.npz"
    object.__new__(Waveform)._save_npy(make_report_waveform(), str(p))
    assert p.exists()
