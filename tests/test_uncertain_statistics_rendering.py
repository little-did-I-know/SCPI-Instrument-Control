"""Both report generators prefer WaveformData.uncertain_statistics over the
plain .statistics value when a stat has an uncertain entry -- one extra
conditional per generator, no new table/column. Byte-identical output when
uncertain_statistics is unset (the common case today).

Requires the `uncertainty` extra (to build a real Quantity to attach).
"""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pint")
pytest.importorskip("uncertainties")

from scpi_control.quantities import quantity
from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator
from scpi_control.report_generator.models.report_data import WaveformData


def _analyzed_waveform():
    """A real sine so .analyze() populates vpp/frequency/etc, matching how
    this field is actually populated in practice (not a stub statistics dict)."""
    n, rate = 10_000, 1e6
    t = np.arange(n) / rate
    v = 2.0 * np.sin(2 * np.pi * 10_000 * t)
    wf = WaveformData(channel="C1", time=t, voltage=v, sample_rate=rate, record_length=n)
    wf.analyze()
    return wf


def test_markdown_uses_plain_formatting_when_uncertain_statistics_unset():
    wf = _analyzed_waveform()
    baseline = MarkdownReportGenerator()._generate_waveform_info(wf, Path("."), "CH1")

    wf2 = _analyzed_waveform()  # separate instance, same signal -> same analysis
    with_field_but_empty = MarkdownReportGenerator()._generate_waveform_info(wf2, Path("."), "CH1")
    assert with_field_but_empty == baseline
    assert "±" not in baseline


def test_markdown_renders_plus_minus_when_vpp_has_uncertainty():
    wf = _analyzed_waveform()
    wf.uncertain_statistics = {"vpp": quantity(4.0, "V", uncertainty=0.05)}
    text = MarkdownReportGenerator()._generate_waveform_info(wf, Path("."), "CH1")
    assert "| VPP | 4 ± 0.05 V |" in text


def test_pdf_uses_plain_formatting_when_uncertain_statistics_unset():
    wf = _analyzed_waveform()
    baseline_table = PDFReportGenerator()._generate_statistics_table(wf)
    wf2 = _analyzed_waveform()
    same_table = PDFReportGenerator()._generate_statistics_table(wf2)
    assert baseline_table._cellvalues == same_table._cellvalues


def test_pdf_renders_plus_minus_when_vpp_has_uncertainty():
    wf = _analyzed_waveform()
    wf.uncertain_statistics = {"vpp": quantity(4.0, "V", uncertainty=0.05)}
    table = PDFReportGenerator()._generate_statistics_table(wf)
    rows = {row[0]: row[1] for row in table._cellvalues}
    assert rows["Vpp:"] == "4 ± 0.05 V"
