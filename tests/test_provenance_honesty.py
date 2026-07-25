"""Audit theme #7 — provenance honesty.

Each test here pins a place where the software used to assert a provenance fact
it did not know: a save time labelled as a capture time, a file mtime rendered as
an acquisition time, AI-written text presented as engineering judgement, a real
instrument identity stamped onto synthetic data, and a cause invented for missing
provenance.
"""

from datetime import datetime, timezone

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
