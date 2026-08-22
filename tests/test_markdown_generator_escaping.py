"""Free text in report data (technician/equipment metadata, measurement
names/units, comparison-table cells, manifest entries, waveform/region/
overlay labels) is interpolated raw into Markdown table and link/alt-text
syntax. An unescaped '|' truncates a table cell early and corrupts the row;
an unescaped ']' in link/alt text closes the link early and corrupts
everything after it in the rendered document (AUDIT.md theme #4 follow-up --
the Markdown-text sibling of H25).
"""

from datetime import datetime

import numpy as np
import pytest

from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.models.report_data import (
    MeasurementResult,
    ReportMetadata,
    TestReport,
    TestSection,
    WaveformData,
)
from scpi_control.report_generator.models.report_elements import (
    ComparisonTable,
    DataManifest,
    ManifestEntry,
    OverlayPlotSpec,
    OverlayTrace,
    TableCell,
)


def _report(section, metadata=None):
    metadata = metadata or ReportMetadata(title="T", technician="R", test_date=datetime(2026, 8, 21))
    return TestReport(metadata=metadata, sections=[section])


def _generate(tmp_path, report, include_plots=False):
    out = tmp_path / "report.md"
    assert MarkdownReportGenerator(include_plots=include_plots).generate(report, out)
    return out.read_text(encoding="utf-8")


def _make_waveform(**overrides):
    t = np.arange(100) / 1e6
    kwargs = dict(
        channel="C1",
        time=t,
        voltage=np.sin(2 * np.pi * 10_000 * t),
        sample_rate=1e6,
        record_length=100,
    )
    kwargs.update(overrides)
    return WaveformData(**kwargs)


# --- Escaping helpers, in isolation -----------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("a|b", "a\\|b"),
        ("a\\b", "a\\\\b"),
        ("a\\|b", "a\\\\\\|b"),
        ("plain text", "plain text"),
    ],
)
def test_escape_table_cell(raw, expected):
    assert MarkdownReportGenerator()._escape_table_cell(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("a]b", "a\\]b"),
        ("a[b", "a\\[b"),
        ("a[b]c", "a\\[b\\]c"),
        ("a\\b", "a\\\\b"),
        ("plain text", "plain text"),
    ],
)
def test_escape_link_text(raw, expected):
    assert MarkdownReportGenerator()._escape_link_text(raw) == expected


# --- Defect 1: table-cell escaping -------------------------------------


def test_metadata_table_escapes_free_text_fields(tmp_path):
    """A '|' in any free-text metadata field must not truncate its table
    cell and corrupt the row (AUDIT.md theme #4 follow-up)."""
    metadata = ReportMetadata(
        title="Bench Check",
        technician="Robin | Evil",
        test_date=datetime(2026, 8, 21),
        equipment_model="Model | X",
        equipment_id="ID | 1",
        test_procedure="Proc | A",
        project_name="Proj | B",
        customer="Cust | C",
        temperature="20 | C",
        humidity="50 | %",
        location="Lab | 1",
    )
    section = TestSection(title="S")
    text = _generate(tmp_path, _report(section, metadata))

    assert "| **Technician** | Robin \\| Evil |" in text
    assert "| **Equipment** | Model \\| X |" in text
    assert "| **Equipment ID** | ID \\| 1 |" in text
    assert "| **Test Procedure** | Proc \\| A |" in text
    assert "| **Project** | Proj \\| B |" in text
    assert "| **Customer** | Cust \\| C |" in text
    assert "| **Temperature** | 20 \\| C |" in text
    assert "| **Humidity** | 50 \\| % |" in text
    assert "| **Location** | Lab \\| 1 |" in text


def test_measurements_table_escapes_name_channel_unit_and_value(tmp_path):
    """meas.name, meas.channel, meas.unit, and format_value() (which embeds
    the unit) are all free text and must be escaped before landing in the
    measurements table."""
    meas = MeasurementResult(
        name="Vpp | evil",
        value=1.234,
        unit="V | evil",
        channel="C1 | evil",
        criteria_min=1.0,
        criteria_max=2.0,
    )
    section = TestSection(title="S", measurements=[meas])
    text = _generate(tmp_path, _report(section))

    assert "Vpp \\| evil (C1 \\| evil)" in text
    assert "1.234 V \\| evil" in text
    assert "min: 1 V \\| evil" in text
    assert "max: 2 V \\| evil" in text
    # No line should contain the raw, unescaped free text -- an unescaped
    # '|' would corrupt the row.
    assert "Vpp | evil" not in text
    assert "C1 | evil" not in text


def test_comparison_table_escapes_headers_and_cell_text(tmp_path):
    table = ComparisonTable(
        title="Cmp",
        headers=["Measurement", "before | after"],
        rows=[[TableCell("vpp"), TableCell("2.0 | evil")]],
    )
    section = TestSection(title="S")
    section.comparison_table = table
    text = _generate(tmp_path, _report(section))

    assert "| Measurement | before \\| after |" in text
    assert "| vpp | 2.0 \\| evil |" in text


def test_manifest_escapes_free_text_fields_but_not_sha256(tmp_path):
    """run_label, file_path, instrument, and capture_timestamp are free
    text; sha256 is a computed hex digest already inside a code span and
    must be left untouched."""
    full_hash = "ab" * 32
    entry = ManifestEntry(
        run_label="run | evil",
        file_path="a | evil.csv",
        size_bytes=10,
        sha256=full_hash,
        capture_timestamp="2026 | evil",
        instrument="Scope | evil",
    )
    section = TestSection(title="S")
    section.manifest = DataManifest(entries=[entry])
    text = _generate(tmp_path, _report(section))

    expected_row = f"| run \\| evil | a \\| evil.csv | 10 | `{full_hash}` | 2026 \\| evil | Scope \\| evil |"
    assert expected_row in text


# --- Defect 2: link/alt-text escaping -----------------------------------


def test_waveform_alt_text_escapes_label(tmp_path):
    """An unescaped ']' in waveform.label would close the '![...]' alt
    text early and corrupt the rest of the rendered line."""
    waveform = _make_waveform(label="Trace ] evil")
    section = TestSection(title="S", waveforms=[waveform])
    text = _generate(tmp_path, _report(section), include_plots=True)

    assert "![Trace \\] evil](plots/" in text
    assert "![Trace ] evil](plots/" not in text


def test_region_alt_text_escapes_label(tmp_path):
    waveform = _make_waveform()
    waveform.add_region(start_time=0.0, end_time=50e-6, label="Region ] evil")
    section = TestSection(title="S", waveforms=[waveform])
    text = _generate(tmp_path, _report(section), include_plots=True)

    assert "![Region \\] evil - Zoomed View](plots/" in text
    assert "![Region ] evil - Zoomed View](plots/" not in text


def test_overlay_alt_text_escapes_channel_label(tmp_path):
    waveform = _make_waveform()
    section = TestSection(title="S")
    section.overlay_plots = [
        OverlayPlotSpec(channel_label="1 ] evil", traces=[OverlayTrace("before", waveform, "#1f77b4")])
    ]
    text = _generate(tmp_path, _report(section), include_plots=True)

    assert "![Overlay: 1 \\] evil](plots/" in text
    assert "![Overlay: 1 ] evil](plots/" not in text


# --- Defect 3: Windows reserved device names ----------------------------


@pytest.mark.parametrize(
    "name",
    [
        "NUL",
        "nul",
        "CON",
        "con",
        "PRN",
        "AUX",
        "COM1",
        "com9",
        "LPT1",
        "lpt9",
    ],
)
def test_sanitize_plot_name_avoids_reserved_device_names(name):
    """A bare reserved device name (case-insensitive) must not survive
    sanitization -- 'NUL.png' refers to the NUL device on Windows
    regardless of the .png extension the caller appends."""
    sanitized = MarkdownReportGenerator()._sanitize_plot_name(name)
    assert sanitized.split(".", 1)[0].upper() not in MarkdownReportGenerator._RESERVED_DEVICE_NAMES


def test_sanitize_plot_name_avoids_reserved_device_name_with_suffix():
    """A reserved name followed by a dot-suffix ('NUL.something') is still
    reserved for the segment before the first dot -- appending the caller's
    .png afterwards would still land on 'NUL....png'."""
    sanitized = MarkdownReportGenerator()._sanitize_plot_name("NUL.something")
    assert sanitized.split(".", 1)[0].upper() not in MarkdownReportGenerator._RESERVED_DEVICE_NAMES


@pytest.mark.parametrize("name", ["COM10", "LPT10", "NULL", "console"])
def test_sanitize_plot_name_does_not_over_match_non_reserved_names(name):
    """Names that merely resemble a reserved device name (COM10, NULL,
    console, ...) must not be mangled."""
    sanitized = MarkdownReportGenerator()._sanitize_plot_name(name)
    assert sanitized == name


def test_a_reserved_device_name_section_title_does_not_collide_on_disk(tmp_path):
    """End-to-end: a section titled 'NUL' must not produce a plot filename
    that Windows treats as the NUL device."""
    waveform = _make_waveform()
    section = TestSection(title="NUL", waveforms=[waveform])
    out = tmp_path / "r.md"
    report = _report(section)
    assert MarkdownReportGenerator(include_plots=True).generate(report, out) is True
    plots_path = out.parent / "plots"
    written = list(plots_path.glob("*.png"))
    assert len(written) == 1
    assert written[0].stem.split(".", 1)[0].upper() not in MarkdownReportGenerator._RESERVED_DEVICE_NAMES


# --- Defect 4: overlay plot filename collision --------------------------


def test_overlay_plots_with_colliding_sanitized_names_do_not_overwrite_each_other(tmp_path):
    """Two overlay specs in the same section whose channel labels differ
    only in characters _sanitize_plot_name collapses together ('A/B' and
    'A:B' both become 'A_B') must not silently overwrite each other's PNG."""
    waveform = _make_waveform()
    section = TestSection(title="S")
    section.overlay_plots = [
        OverlayPlotSpec(channel_label="A/B", traces=[OverlayTrace("before", waveform, "#1f77b4")]),
        OverlayPlotSpec(channel_label="A:B", traces=[OverlayTrace("before", waveform, "#1f77b4")]),
    ]
    out = tmp_path / "r.md"
    report = _report(section)
    assert MarkdownReportGenerator(include_plots=True).generate(report, out) is True

    plots_path = out.parent / "plots"
    written = list(plots_path.glob("*.png"))
    assert len(written) == 2
