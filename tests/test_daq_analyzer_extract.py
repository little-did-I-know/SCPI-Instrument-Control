"""Threshold extraction must bind the number to its label, not grab the list ordinal."""

from scpi_control.report_generator.llm.daq_analyzer import DAQAnalyzer


def test_ignores_leading_list_ordinal():
    assert DAQAnalyzer._extract_number("1. warning high: 5.2 v") == 5.2
    assert DAQAnalyzer._extract_number("2. warning low: 4.8 v") == 4.8


def test_plain_labelled_value():
    assert DAQAnalyzer._extract_number("critical high alarm at 10.5") == 10.5


def test_no_number_returns_none():
    assert DAQAnalyzer._extract_number("no numbers here") is None


def test_bare_leading_decimal_value_not_truncated():
    # A line that leads with the value itself must not have its integer part
    # eaten as a list ordinal (regression: "10.5" -> 5.0).
    assert DAQAnalyzer._extract_number("10.5 is critical high") == 10.5
    assert DAQAnalyzer._extract_number("5.2 is the warning high threshold") == 5.2
