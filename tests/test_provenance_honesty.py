"""Audit theme #7 — provenance honesty.

Each test here pins a place where the software used to assert a provenance fact
it did not know: a save time labelled as a capture time, a file mtime rendered as
an acquisition time, AI-written text presented as engineering judgement, a real
instrument identity stamped onto synthetic data, and a cause invented for missing
provenance.
"""

from datetime import datetime

import numpy as np
import pytest

from scpi_control.provenance import AcquisitionProvenance, InstrumentInfo
from scpi_control.waveform import Waveform, WaveformData

ACQUIRED = "2020-01-01T00:00:00+00:00"


def _waveform(with_provenance):
    wf = WaveformData(
        time=np.linspace(0, 1e-3, 16),
        voltage=np.zeros(16),
        channel=1,
        sample_rate=16_000.0,
    )
    if with_provenance:
        wf.provenance = AcquisitionProvenance(
            instrument=InstrumentInfo(manufacturer="Siglent", model="SDS824X HD"),
            acquired_at=ACQUIRED,
        )
    return wf


def _save_enhanced(tmp_path, wf, name="cap.csv"):
    from unittest.mock import Mock

    path = tmp_path / name
    Waveform(Mock()).save_waveform(wf, str(path), format="CSV_ENHANCED")
    return path.read_text()


def test_csv_header_labels_the_save_time_as_saved(tmp_path):
    """The old header said '# Captured: <now>' -- the SAVE time under a CAPTURE label."""
    text = _save_enhanced(tmp_path, _waveform(with_provenance=False))
    assert "# Saved:" in text


def test_csv_header_captured_line_carries_the_real_acquisition_time(tmp_path):
    text = _save_enhanced(tmp_path, _waveform(with_provenance=True))
    assert f"# Captured: {ACQUIRED}" in text
    # And it must not be the save time: this file was written today.
    assert f"# Captured: {datetime.now().year}" not in text


def test_csv_header_omits_captured_when_there_is_no_provenance(tmp_path):
    """No provenance means no known capture time. Say nothing rather than
    substituting the save time (the honesty rule: never a fabricated stand-in)."""
    text = _save_enhanced(tmp_path, _waveform(with_provenance=False))
    assert "# Captured:" not in text


def test_manifest_does_not_report_file_mtime_as_a_capture_time(tmp_path):
    """A capture copied off a scope's USB stick onto a NAS carries the COPY time as
    mtime. Rendering that under 'Captured' makes it indistinguishable from a real
    acquisition timestamp (audit M30)."""
    from scpi_control.report_generator.comparison_report_builder import build_manifest
    from scpi_control.report_generator.models.comparison import Run

    path = tmp_path / "legacy_capture.csv"
    path.write_text("0.0,0.0\n1e-3,1.0\n")

    manifest = build_manifest([Run(label="legacy", files=[path])])

    assert manifest.entries, "expected one manifest entry per source file"
    assert manifest.entries[0].capture_timestamp is None, "mtime must not stand in for an acquisition time"


def _stub_client(response_text):
    class _Client:
        def complete(self, prompt, system_prompt=None, temperature=None):
            return response_text

    return _Client()


def _minimal_report():
    """A minimal but complete TestReport (mirrors tests/test_report_generators.py)."""
    from datetime import datetime

    from scpi_control.report_generator.models.report_data import ReportMetadata, TestReport, TestSection, WaveformData

    t = np.arange(100) / 1e6
    waveform = WaveformData(channel="C1", time=t, voltage=np.sin(2 * np.pi * 10_000 * t), sample_rate=1e6, record_length=100)
    section = TestSection(title="Rise Time", content="Measured on C1.", waveforms=[waveform])
    metadata = ReportMetadata(title="Bench Check", technician="robin", test_date=datetime(2026, 7, 16))
    return TestReport(metadata=metadata, sections=[section])


def test_ai_findings_mark_themselves_as_ai_generated():
    """The producer marks its own output, so no caller can forget to (audit M31)."""
    from scpi_control.report_generator.llm.analyzer import ReportAnalyzer
    from scpi_control.report_generator.models.report_data import SUMMARY_SOURCE_AI

    report = _minimal_report()
    analyzer = ReportAnalyzer(_stub_client("1. First finding\n2. Second finding\n"))
    findings = analyzer.generate_key_findings(report)

    assert findings, "stub should parse into findings"
    assert report.findings_source == SUMMARY_SOURCE_AI


def _markdown_for(report, tmp_path):
    """Render a report to markdown and return the text.

    Note the generator writes to a FILE and returns a bool -- it does not return
    the rendered text -- so the test reads the file back.
    """
    from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator

    out = tmp_path / "report.md"
    assert MarkdownReportGenerator().generate(report, str(out)) is True
    return out.read_text(encoding="utf-8")


def test_markdown_labels_ai_findings(tmp_path):
    from scpi_control.report_generator.models.report_data import SUMMARY_SOURCE_AI

    report = _minimal_report()
    report.key_findings = ["Rise time of 3.2 ns is within specification"]
    report.findings_source = SUMMARY_SOURCE_AI

    assert "Key findings generated by AI" in _markdown_for(report, tmp_path)


def test_hand_authored_findings_are_not_labelled(tmp_path):
    """Attribution must distinguish, not decorate: a manual finding gets no label."""
    report = _minimal_report()
    report.key_findings = ["Checked by hand against the scope screen"]

    assert "generated by AI" not in _markdown_for(report, tmp_path)


def test_ai_recommendations_mark_themselves_as_ai_generated():
    """The producer marks its own output, so no caller can forget to (audit M31)."""
    from scpi_control.report_generator.llm.analyzer import ReportAnalyzer
    from scpi_control.report_generator.models.report_data import SUMMARY_SOURCE_AI

    report = _minimal_report()
    analyzer = ReportAnalyzer(_stub_client("1. First recommendation\n2. Second recommendation\n"))
    recommendations = analyzer.generate_recommendations(report)

    assert recommendations, "stub should parse into recommendations"
    assert report.recommendations_source == SUMMARY_SOURCE_AI


def test_markdown_labels_ai_recommendations(tmp_path):
    from scpi_control.report_generator.models.report_data import SUMMARY_SOURCE_AI

    report = _minimal_report()
    report.recommendations = ["Replace the probe compensation capacitor"]
    report.recommendations_source = SUMMARY_SOURCE_AI

    assert "Recommendations generated by AI" in _markdown_for(report, tmp_path)


def test_hand_authored_recommendations_are_not_labelled(tmp_path):
    """Attribution must distinguish, not decorate: a manual recommendation gets no label."""
    report = _minimal_report()
    report.recommendations = ["Re-run with a 10x probe"]

    assert "generated by AI" not in _markdown_for(report, tmp_path)


def test_ai_content_transfer_preserves_attribution(tmp_path):
    """Regression for main_window.py's _build_report(): it builds a BRAND-NEW
    TestReport and copies only the AI-generated TEXT out of a dict, discarding the
    object the producer set findings_source/recommendations_source on (Task 4
    review, C1). Pins the transfer shape without importing the GUI module (CI
    skips Qt): build report A, run the analyzer, build report B the way
    _build_report() does, copy only text plus the fix's flag, and check the
    rendered markdown."""
    from scpi_control.report_generator.llm.analyzer import ReportAnalyzer
    from scpi_control.report_generator.models.report_data import SUMMARY_SOURCE_AI, TestReport

    report_a = _minimal_report()
    analyzer = ReportAnalyzer(_stub_client("1. First finding\n2. Second finding\n"))
    findings = analyzer.generate_key_findings(report_a)
    assert report_a.findings_source == SUMMARY_SOURCE_AI

    ai_content = {"key_findings": findings}

    # Mirrors main_window.py's _build_report(): a fresh TestReport, only the
    # TEXT copied out of the dict -- plus the fix, setting the flag alongside it.
    report_b = TestReport(metadata=report_a.metadata)
    if ai_content.get("key_findings"):
        report_b.key_findings = ai_content["key_findings"]
        report_b.findings_source = SUMMARY_SOURCE_AI

    assert "Key findings generated by AI" in _markdown_for(report_b, tmp_path)


def test_manifest_paths_are_not_mangled_by_the_markdown_converter():
    """The manifest exists to make provenance verifiable, so the path must survive
    verbatim. Underscores are markdown emphasis: scope_capture_ch1.npz was rendering
    as scope*capture*ch1.npz with 'capture' italicised (audit M34)."""
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator

    path = r"C:\data\scope_capture_ch1.npz"
    rendered = PDFReportGenerator()._literal_cell_text(path)
    assert "scope_capture_ch1.npz" in rendered
    assert "<i>" not in rendered


def test_manifest_literal_cells_escape_xml():
    """_markdown_to_reportlab converts underscores and asterisks as markdown
    emphasis, which corrupts file paths -- that is why paths need a renderer that
    escapes for reportlab's mini-XML without interpreting emphasis. Escaping is
    still required of that literal renderer: an unescaped & or < in a path would
    corrupt reportlab's mini-XML parse."""
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator

    rendered = PDFReportGenerator()._literal_cell_text("a&b<c.npz")
    assert "&amp;" in rendered and "&lt;" in rendered


def test_manifest_table_renders_paths_literally():
    """Regression for M34's actual integration point: _generate_manifest_table
    (via its _cell helper) must render the manifest's file path through the
    literal renderer, not through _markdown_to_reportlab. The two tests above
    only exercise _literal_cell_text directly -- they would keep passing even if
    a future refactor silently un-routed _cell back to the markdown converter.
    This test renders a real manifest table and inspects the Paragraph reportlab
    actually built, so it fails if that routing regresses."""
    pytest.importorskip("reportlab")
    from reportlab.platypus import Paragraph

    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator
    from scpi_control.report_generator.models.report_elements import DataManifest, ManifestEntry

    path = r"C:\data\scope_capture_ch1.npz"
    manifest = DataManifest(
        entries=[
            ManifestEntry(
                run_label="run-a",
                file_path=path,
                size_bytes=1024,
                sha256="deadbeef",
            )
        ]
    )

    table = PDFReportGenerator()._generate_manifest_table(manifest)

    # Row 0 is the header; row 1, column 1 ("File") is the path cell.
    file_cell = table._cellvalues[1][1]
    assert isinstance(file_cell, Paragraph)
    assert "scope_capture_ch1.npz" in file_cell.text
    assert "<i>" not in file_cell.text


def test_pdf_labels_ai_findings(tmp_path):
    """audit M32: AI-generated findings must not ship in a signed PDF unlabelled.
    No prior test in this repo exercised PDF attribution rendering (Task 4 review
    found this gap) -- this closes it by rendering a real PDF and reading the
    attribution note back out of it."""
    fitz = pytest.importorskip("fitz")
    pytest.importorskip("reportlab")
    pytest.importorskip("svglib")
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator
    from scpi_control.report_generator.models.report_data import SUMMARY_SOURCE_AI

    report = _minimal_report()
    report.key_findings = ["Rise time of 3.2 ns is within specification"]
    report.findings_source = SUMMARY_SOURCE_AI

    out = tmp_path / "ai_findings.pdf"
    assert PDFReportGenerator().generate(report, str(out)) is True

    doc = fitz.open(out)
    try:
        text = "".join(doc[i].get_text() for i in range(doc.page_count))
    finally:
        doc.close()
    assert "Key findings generated by AI" in text


def test_pdf_does_not_label_hand_authored_findings(tmp_path):
    """The negative case: a test that only checked for presence of the AI label
    would still pass if the code labelled everything, so this pins that a manual
    finding renders in the PDF with no attribution note."""
    fitz = pytest.importorskip("fitz")
    pytest.importorskip("reportlab")
    pytest.importorskip("svglib")
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator

    report = _minimal_report()
    report.key_findings = ["Checked by hand against the scope screen"]

    out = tmp_path / "manual_findings.pdf"
    assert PDFReportGenerator().generate(report, str(out)) is True

    doc = fitz.open(out)
    try:
        text = "".join(doc[i].get_text() for i in range(doc.page_count))
    finally:
        doc.close()
    assert "generated by AI" not in text


def test_pdf_labels_ai_recommendations(tmp_path):
    """audit M32: AI-generated recommendations must not ship in a signed PDF
    unlabelled -- the mirror of test_pdf_labels_ai_findings above (I2)."""
    fitz = pytest.importorskip("fitz")
    pytest.importorskip("reportlab")
    pytest.importorskip("svglib")
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator
    from scpi_control.report_generator.models.report_data import SUMMARY_SOURCE_AI

    report = _minimal_report()
    report.recommendations = ["Replace the probe compensation capacitor"]
    report.recommendations_source = SUMMARY_SOURCE_AI

    out = tmp_path / "ai_recommendations.pdf"
    assert PDFReportGenerator().generate(report, str(out)) is True

    doc = fitz.open(out)
    try:
        text = "".join(doc[i].get_text() for i in range(doc.page_count))
    finally:
        doc.close()
    assert "Recommendations generated by AI" in text


def test_pdf_does_not_label_hand_authored_recommendations(tmp_path):
    """The negative case: a test that only checked for presence of the AI label
    would still pass if the code labelled everything, so this pins that a manual
    recommendation renders in the PDF with no attribution note."""
    fitz = pytest.importorskip("fitz")
    pytest.importorskip("reportlab")
    pytest.importorskip("svglib")
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator

    report = _minimal_report()
    report.recommendations = ["Re-run with a 10x probe"]

    out = tmp_path / "manual_recommendations.pdf"
    assert PDFReportGenerator().generate(report, str(out)) is True

    doc = fitz.open(out)
    try:
        text = "".join(doc[i].get_text() for i in range(doc.page_count))
    finally:
        doc.close()
    assert "generated by AI" not in text


def test_shipped_example_does_not_claim_a_real_instrument_for_synthetic_data():
    """examples/comparison_report.py synthesises its waveforms. Stamping them with
    a real Siglent identity produces a signed report attributing invented data to
    hardware that never ran -- and anyone copying _save_capture inherits it (audit M1)."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    source = (repo_root / "examples" / "comparison_report.py").read_text(encoding="utf-8")
    assert "SDS1104X-E" not in source
    assert 'manufacturer="Siglent"' not in source


def test_scpi_extract_does_not_invent_a_reason_for_missing_provenance():
    """A file saved yesterday with provenance=False, or one corrupted in transit,
    gets the same confident 'predates provenance capture' claim. The tool cannot
    know why the block is absent -- only that it is (audit L17)."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    source = (repo_root / "scpi_control" / "scpi_extract.py").read_text(encoding="utf-8")
    assert "predates provenance capture" not in source


def test_scpi_extract_reports_missing_provenance_without_claiming_reason(tmp_path):
    """Behavioral test: a file with no provenance block should report its absence
    without fabricating a cause. This exercises the real code path and verifies
    the fix actually works, not just that a string was deleted."""
    from scpi_control.scpi_extract import _info_lines
    from scpi_control.waveform_io import LoadedWaveform

    # Create a waveform file with no provenance
    wf = _waveform(with_provenance=False)

    loaded = LoadedWaveform(
        source_path="cap.csv",
        source_format="CSV_ENHANCED",
        time=wf.time,
        voltage=wf.voltage,
        channel=wf.channel,
        sample_rate=wf.sample_rate,
        provenance=None,
        metadata={},
    )

    # Call the function that builds the summary lines
    lines = _info_lines(loaded)
    full_output = "\n".join(lines)

    # Must report absence of provenance
    assert "Provenance:" in full_output, "provenance status must be reported"
    # Must NOT claim a cause
    assert "predates provenance capture" not in full_output, "must not invent a reason"
    # Should state that no provenance is recorded
    assert "none recorded" in full_output.lower(), "should state that no provenance is recorded"
