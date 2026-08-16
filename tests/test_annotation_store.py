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


def test_save_preserves_a_sibling_channel_not_included_in_this_save(tmp_path):
    """Saving only one channel of a multi-channel capture must not erase the
    others -- exactly what the Task 9 annotation dialog does when it calls
    save_annotations([self.waveform]) for a single-channel edit."""
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    ch1 = make_waveform("C1", source)
    ch2 = make_waveform("C2", source)
    ch1.annotations = [PlotAnnotation(kind=KIND_VLINE, text="ch1 original", x=0.0)]
    ch2.annotations = [PlotAnnotation(kind=KIND_VLINE, text="ch2 original", x=1.0)]
    save_annotations([ch1, ch2])

    # Re-save only C1, as a single-waveform save would.
    ch1_updated = make_waveform("C1", source)
    ch1_updated.annotations = [PlotAnnotation(kind=KIND_VLINE, text="ch1 updated", x=2.0)]
    save_annotations([ch1_updated])

    fresh1 = make_waveform("C1", source)
    fresh2 = make_waveform("C2", source)
    load_annotations_into([fresh1, fresh2])
    assert [a.text for a in fresh1.annotations] == ["ch1 updated"]
    assert [a.text for a in fresh2.annotations] == ["ch2 original"]


def test_corrupt_sidecar_with_invalid_utf8_bytes_warns_and_applies_nothing(tmp_path, caplog):
    """A truncated write or a genuinely binary file raises UnicodeDecodeError
    from read_text(), which is a ValueError subclass -- not an OSError or a
    json.JSONDecodeError. It must still be treated as a corrupt sidecar."""
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    sidecar_path_for(source).write_bytes(b"\xff\xfe\x00 not utf-8")
    waveform = make_waveform("C1", source)

    assert load_annotations_into([waveform]) == 0
    assert waveform.annotations == []
    assert "capture.csv.annotations.json" in caplog.text


def test_load_annotations_into_is_idempotent(tmp_path):
    """Calling the loader twice on the same waveform objects -- a reload, or a
    rebuilt section -- must not duplicate the saved annotations."""
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    waveform = make_waveform("C1", source)
    waveform.annotations = [PlotAnnotation(kind=KIND_VLINE, text="saved", x=0.0)]
    save_annotations([waveform])

    fresh = make_waveform("C1", source)
    load_annotations_into([fresh])
    first_count = len(fresh.annotations)
    load_annotations_into([fresh])
    assert len(fresh.annotations) == first_count


def test_load_fft_annotations_into_is_idempotent(tmp_path):
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    waveform = make_waveform("C1", source)
    save_annotations([waveform], fft={"C1": ("Figure 2", [PlotAnnotation(kind=KIND_VLINE, text="carrier", x=1e6)])})

    section = TestSection(title="Spectrum")
    section.fft_channel = "C1"
    load_fft_annotations_into(section, [waveform])
    first_count = len(section.fft_annotations)
    load_fft_annotations_into(section, [waveform])
    assert len(section.fft_annotations) == first_count


def test_save_without_fft_kwarg_preserves_previously_saved_fft_data(tmp_path):
    """Absence of the fft kwarg means "no opinion about FFT", not "clear the
    FFT data" -- the Task 9 annotation dialog only ever holds a WaveformData
    and never supplies fft, so every dialog save must not delete a channel's
    FFT caption/annotations saved by an earlier call that did supply them."""
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    ch1 = make_waveform("C1", source)
    fft_annotation = PlotAnnotation(kind=KIND_VLINE, text="carrier", x=1e6)
    save_annotations([ch1], fft={"C1": ("cap", [fft_annotation])})

    # A later save with no fft kwarg at all -- as the annotation dialog does.
    ch1_again = make_waveform("C1", source)
    ch1_again.annotations = [PlotAnnotation(kind=KIND_VLINE, text="new time annotation", x=0.0)]
    save_annotations([ch1_again])

    data = json.loads(sidecar_path_for(source).read_text(encoding="utf-8"))
    assert data["waveforms"]["C1"]["fft"]["caption"] == "cap"
    assert data["waveforms"]["C1"]["fft"]["annotations"][0]["text"] == "carrier"

    section = TestSection(title="Spectrum")
    section.fft_channel = "C1"
    assert load_fft_annotations_into(section, [ch1_again]) == 1
    assert section.fft_annotations == [fft_annotation]
    assert section.fft_caption == "cap"


def test_two_identical_sidecar_annotations_both_load_into_an_empty_waveform(tmp_path):
    """save_annotations does no dedup, so a sidecar can legitimately hold two
    structurally identical PlotAnnotation entries -- both must load, not just
    one, even though PlotAnnotation equality has no identity field."""
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    ch1 = make_waveform("C1", source)
    ch1.annotations = [
        PlotAnnotation(kind=KIND_VLINE, text="same", x=0.0),
        PlotAnnotation(kind=KIND_VLINE, text="same", x=0.0),
    ]
    save_annotations([ch1])

    fresh = make_waveform("C1", source)
    assert load_annotations_into([fresh]) == 2
    assert len(fresh.annotations) == 2


def test_loading_a_sidecar_with_duplicate_annotations_twice_still_leaves_exactly_two(tmp_path):
    """Pins both properties of the multiset-aware idempotency guard at once: a
    first load must apply both identical annotations (not silently drop the
    second as a false "duplicate" of the first), and a second load of the
    same sidecar must not duplicate them further. Fails under a plain
    membership guard (first load already collapses to one) and fails under no
    guard at all (second load doubles to four)."""
    source = tmp_path / "capture.csv"
    source.write_text("placeholder")
    ch1 = make_waveform("C1", source)
    ch1.annotations = [
        PlotAnnotation(kind=KIND_VLINE, text="same", x=0.0),
        PlotAnnotation(kind=KIND_VLINE, text="same", x=0.0),
    ]
    save_annotations([ch1])

    fresh = make_waveform("C1", source)
    load_annotations_into([fresh])
    assert len(fresh.annotations) == 2

    load_annotations_into([fresh])
    assert len(fresh.annotations) == 2
