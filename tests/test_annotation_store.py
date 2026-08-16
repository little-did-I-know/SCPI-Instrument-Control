"""Per-waveform sidecar JSON: <source>.annotations.json."""

import json

import numpy as np
import pytest

from scpi_control.report_generator.models.annotations import KIND_LABEL, KIND_VLINE, PlotAnnotation
from scpi_control.report_generator.models.report_data import TestSection, WaveformData
from scpi_control.report_generator.utils.annotation_store import (
    load_annotations_into,
    load_fft_annotations_into,
    save_annotations,
    sidecar_path_for,
)


def make_waveform(channel, source_file):
    t = np.arange(50) / 1e6
    return WaveformData(
        channel=channel,
        time=t,
        voltage=np.sin(t),
        sample_rate=1e6,
        record_length=50,
        source_file=source_file,
    )


def test_sidecar_path_appends_rather_than_replaces_the_suffix(tmp_path):
    """capture.csv and capture.npz in one directory must not collide."""
    assert sidecar_path_for(tmp_path / "capture.csv").name == "capture.csv.annotations.json"
    assert sidecar_path_for(tmp_path / "capture.npz").name == "capture.npz.annotations.json"


def test_save_then_load_round_trips_a_two_channel_file(tmp_path):
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    ch1 = make_waveform("C1", source)
    ch2 = make_waveform("C2", source)
    ch1.annotations = [PlotAnnotation(kind=KIND_LABEL, text="ringing", x=1.2e-5, y=0.5)]
    ch1.caption = "Figure 1"
    ch2.annotations = [PlotAnnotation(kind=KIND_VLINE, text="trigger", x=0.0)]

    written = save_annotations([ch1, ch2])
    assert written == sidecar_path_for(source)

    fresh1 = make_waveform("C1", source)
    fresh2 = make_waveform("C2", source)
    assert load_annotations_into([fresh1, fresh2]) == 2
    assert fresh1.annotations == ch1.annotations
    assert fresh1.caption == "Figure 1"
    assert fresh2.annotations == ch2.annotations


def test_saved_file_declares_its_schema_version(tmp_path):
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    waveform = make_waveform("C1", source)
    waveform.annotations = [PlotAnnotation(kind=KIND_VLINE, text="t", x=0.0)]

    data = json.loads(save_annotations([waveform]).read_text(encoding="utf-8"))
    assert data["schema"] == 1
    assert data["waveforms"]["C1"]["annotations"][0]["kind"] == "vline"


def test_saving_a_waveform_with_no_source_file_raises(tmp_path):
    t = np.arange(10) / 1e6
    orphan = WaveformData(channel="C1", time=t, voltage=np.sin(t), sample_rate=1e6, record_length=10)
    orphan.annotations = [PlotAnnotation(kind=KIND_VLINE, text="t", x=0.0)]

    with pytest.raises(ValueError, match="source_file"):
        save_annotations([orphan])


def test_corrupt_sidecar_warns_and_applies_nothing(tmp_path, caplog):
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    sidecar_path_for(source).write_text("{not valid json", encoding="utf-8")
    waveform = make_waveform("C1", source)

    assert load_annotations_into([waveform]) == 0
    assert waveform.annotations == []
    assert "capture.csv.annotations.json" in caplog.text


def test_missing_sidecar_is_silent_and_applies_nothing(tmp_path):
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    waveform = make_waveform("C1", source)
    assert load_annotations_into([waveform]) == 0


def test_load_merges_rather_than_clears(tmp_path):
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    waveform = make_waveform("C1", source)
    waveform.annotations = [PlotAnnotation(kind=KIND_VLINE, text="saved", x=0.0)]
    save_annotations([waveform])

    fresh = make_waveform("C1", source)
    fresh.annotations = [PlotAnnotation(kind=KIND_LABEL, text="in memory", x=1e-6, y=0.1)]
    load_annotations_into([fresh])

    texts = {a.text for a in fresh.annotations}
    assert texts == {"in memory", "saved"}


def test_fft_annotations_route_back_to_the_section_by_channel(tmp_path):
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    waveform = make_waveform("C1", source)
    fft_annotation = PlotAnnotation(kind=KIND_VLINE, text="carrier", x=1e6)
    save_annotations([waveform], fft={"C1": ("Figure 2", [fft_annotation])})

    section = TestSection(title="Spectrum")
    section.fft_channel = "C1"
    assert load_fft_annotations_into(section, [waveform]) == 1
    assert section.fft_annotations == [fft_annotation]
    assert section.fft_caption == "Figure 2"


def test_fft_load_is_a_no_op_without_a_matching_channel(tmp_path):
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    waveform = make_waveform("C1", source)
    save_annotations([waveform], fft={"C1": ("Figure 2", [PlotAnnotation(kind=KIND_VLINE, text="c", x=1e6)])})

    no_channel = TestSection(title="Spectrum")
    assert load_fft_annotations_into(no_channel, [waveform]) == 0
    assert no_channel.fft_annotations == []

    wrong_channel = TestSection(title="Spectrum")
    wrong_channel.fft_channel = "C4"
    assert load_fft_annotations_into(wrong_channel, [waveform]) == 0
