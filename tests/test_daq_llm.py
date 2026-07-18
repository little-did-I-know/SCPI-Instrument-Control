"""Characterization tests for the DAQ LLM surface (previously untested).

Lean by design: pins the behaviors the prompt-helper refactor could break --
prompt lookup, context assembly structure, the empty-buffer guards, and the
deliberate low temperature on threshold suggestions. Uses a mock client (no
network).
"""

from datetime import datetime
from unittest.mock import MagicMock

import numpy as np

from scpi_control.report_generator.llm.context_builder import ContextBuilder
from scpi_control.report_generator.llm.daq_analyzer import DAQAnalyzer
from scpi_control.report_generator.llm.daq_context_builder import DAQContextBuilder
from scpi_control.report_generator.llm.daq_prompts import get_daq_system_prompt
from scpi_control.report_generator.models.report_data import ReportMetadata, TestReport, TestSection, WaveformData

_KEYS = ["expert", "trends", "thresholds", "summary", "chat"]

_BUFFER = [
    {"timestamp": 0.0, "readings": {1: 1.00, 2: 20.0}},
    {"timestamp": 1.0, "readings": {1: 1.02, 2: 20.5}},
    {"timestamp": 2.0, "readings": {1: 1.04, 2: 21.0}},
]
_CHANNELS = [1, 2]
_CONFIGS = {1: {"function": "VOLT:DC", "function_display": "DC Voltage"}, 2: {"function": "TEMP:TC:K", "function_display": "Temperature"}}


def test_get_daq_system_prompt_returns_each_prompt_and_defaults():
    for key in _KEYS:
        assert isinstance(get_daq_system_prompt(key), str) and get_daq_system_prompt(key).strip()
    assert get_daq_system_prompt("nonexistent") == get_daq_system_prompt("expert")


def test_build_session_context_structure():
    ctx = DAQContextBuilder.build_session_context(_BUFFER, _CHANNELS, _CONFIGS)
    assert "# DAQ Session Data" in ctx
    assert "Total Scans: 3" in ctx
    assert "## Channel Statistics" in ctx
    assert "### Channel 1 (DC Voltage)" in ctx


def test_build_chat_context_has_markers_and_question():
    ctx = DAQContextBuilder.build_chat_context(_BUFFER, _CHANNELS, "What is the trend on channel 1?", _CONFIGS)
    assert "=== DAQ SESSION DATA ===" in ctx
    assert ctx.rstrip().endswith("What is the trend on channel 1?")
    assert "=== USER QUESTION ===" in ctx


def _osc_report():
    t = np.arange(100) / 1e6
    wf = WaveformData(channel="C1", time=t, voltage=np.sin(2 * np.pi * 1000 * t), sample_rate=1e6, record_length=100)
    return TestReport(metadata=ReportMetadata(title="B", technician="r", test_date=datetime(2026, 7, 18)), sections=[TestSection(title="Captures", waveforms=[wf])])


def test_osc_build_chat_context_has_markers_and_question():
    # Safety net for the shared build_chat_prompt refactor: the oscilloscope chat
    # builder is otherwise untested (the analyzer tests take the tool-calling path).
    ctx = ContextBuilder.build_chat_context(_osc_report(), "Is C1 clean?")
    assert "=== TEST REPORT DATA ===" in ctx
    assert "=== USER QUESTION ===" in ctx
    assert ctx.rstrip().endswith("Is C1 clean?")


def test_analyze_trends_calls_client_with_trends_prompt():
    client = MagicMock()
    client.complete.return_value = "trend analysis"
    out = DAQAnalyzer(client).analyze_trends(_BUFFER, _CHANNELS, _CONFIGS)
    assert out == "trend analysis"
    kwargs = client.complete.call_args.kwargs
    assert kwargs["system_prompt"] == get_daq_system_prompt("trends")
    assert kwargs["temperature"] == 0.7


def test_empty_buffer_guards_do_not_call_the_model():
    client = MagicMock()
    analyzer = DAQAnalyzer(client)
    assert analyzer.analyze_trends([], _CHANNELS) == "No data available for trend analysis."
    assert analyzer.answer_question([], _CHANNELS, "q?") == "No data available. Please start a logging session first."
    assert analyzer.suggest_thresholds([], 1) is None
    client.complete.assert_not_called()


def test_suggest_thresholds_uses_low_temperature():
    client = MagicMock()
    client.complete.return_value = "warning high 1.1"
    DAQAnalyzer(client).suggest_thresholds(_BUFFER, 1, _CONFIGS[1])
    assert client.complete.call_args.kwargs["temperature"] == 0.5
