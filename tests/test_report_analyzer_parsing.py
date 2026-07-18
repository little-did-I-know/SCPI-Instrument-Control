"""_parse_numbered_list tolerates the list shapes a small local model actually
emits, and the two parsed analyzer methods run it end-to-end."""

from datetime import datetime
from unittest.mock import MagicMock

import numpy as np

from scpi_control.report_generator.llm.analyzer import ReportAnalyzer, _parse_numbered_list
from scpi_control.report_generator.models.report_data import (
    ReportMetadata,
    TestReport,
    TestSection,
    WaveformData,
)


def make_report():
    t = np.arange(100) / 1e6
    waveform = WaveformData(channel="C1", time=t, voltage=np.sin(2 * np.pi * 10_000 * t), sample_rate=1e6, record_length=100)
    return TestReport(
        metadata=ReportMetadata(title="Bench", technician="robin", test_date=datetime(2026, 7, 18)),
        sections=[TestSection(title="Captures", waveforms=[waveform])],
    )


def test_plain_numbered_list():
    assert _parse_numbered_list("1. First\n2. Second\n3. Third", 5) == ["First", "Second", "Third"]


def test_multi_digit_prefixes_survive():
    text = "\n".join(f"{i}. item{i}" for i in range(1, 13))
    assert _parse_numbered_list(text, 20)[9:] == ["item10", "item11", "item12"]


def test_paren_delimiter_and_bullets():
    assert _parse_numbered_list("1) a\n2) b", 5) == ["a", "b"]
    assert _parse_numbered_list("- a\n* b\n• c", 5) == ["a", "b", "c"]


def test_markdown_bold_numbering():
    assert _parse_numbered_list("**1.** First\n**2.** Second", 5) == ["First", "Second"]


def test_bold_wrapped_item_is_unwrapped():
    assert _parse_numbered_list("1. **Rise time slow**", 5) == ["Rise time slow"]


def test_italic_wrapped_item_is_unwrapped():
    assert _parse_numbered_list("1. *emphasis*", 5) == ["emphasis"]


def test_partial_bold_leaves_valid_markdown():
    # Only the leading keyword is bolded: the item is NOT symmetrically wrapped,
    # so it must be left intact rather than losing its leading ** and stranding
    # the interior one (which produced "Clipping** detected on CH1" before).
    assert _parse_numbered_list("1. **Clipping** detected on CH1", 5) == ["**Clipping** detected on CH1"]


def test_leading_glob_star_is_preserved():
    assert _parse_numbered_list("1. *.tmp files should be deleted", 5) == ["*.tmp files should be deleted"]


def test_preamble_line_is_dropped_when_markers_exist():
    assert _parse_numbered_list("Here are the findings:\n1. First\n2. Second", 5) == ["First", "Second"]


def test_no_marker_salvage_returns_plain_lines():
    assert _parse_numbered_list("First finding\nSecond finding", 5) == ["First finding", "Second finding"]


def test_no_marker_salvage_drops_trailing_colon_preamble():
    assert _parse_numbered_list("Findings:\nFirst\nSecond", 5) == ["First", "Second"]


def test_max_items_truncates():
    assert _parse_numbered_list("1. a\n2. b\n3. c", 2) == ["a", "b"]


def test_empty_input_returns_none():
    assert _parse_numbered_list("", 5) is None
    assert _parse_numbered_list("   \n  ", 5) is None
    assert _parse_numbered_list(None, 5) is None


def test_generate_key_findings_parses_a_messy_model_reply():
    client = MagicMock()
    client.complete.return_value = "Here are the findings:\n1. Clipping on C1\n2. **Noise high**"
    assert ReportAnalyzer(client).generate_key_findings(make_report(), max_findings=5) == ["Clipping on C1", "Noise high"]


def test_generate_recommendations_parses_a_messy_model_reply():
    client = MagicMock()
    client.complete.return_value = "1. Re-run with 50 ohm termination\n2. Check probe compensation"
    assert ReportAnalyzer(client).generate_recommendations(make_report(), max_recommendations=5) == [
        "Re-run with 50 ohm termination",
        "Check probe compensation",
    ]
