"""answer_question picks the tool path when the model supports it, and falls
back to the summarized-context path when it does not."""

from datetime import datetime
from unittest.mock import MagicMock

import numpy as np

from scpi_control.report_generator.llm.analyzer import ReportAnalyzer
from scpi_control.report_generator.llm.prompts import get_system_prompt
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
        metadata=ReportMetadata(title="Bench", technician="robin", test_date=datetime(2026, 7, 16)),
        sections=[TestSection(title="Captures", waveforms=[waveform])],
    )


def test_answer_question_uses_tools_when_the_model_supports_them():
    client = MagicMock()
    client.supports_tools.return_value = True
    client.chat_with_tools.return_value = "C1 is a sine."

    answer = ReportAnalyzer(client).answer_question(make_report(), "What is on C1?")

    assert answer == "C1 is a sine."
    client.complete.assert_not_called()
    tools = client.chat_with_tools.call_args.args[1]
    assert [fn.__name__ for fn in tools] == ["list_waveforms", "analyze_waveform", "detect_transients", "list_measurements"]


def test_the_tool_path_sends_the_question_and_a_tool_aware_system_prompt():
    client = MagicMock()
    client.supports_tools.return_value = True
    client.chat_with_tools.return_value = "ok"

    ReportAnalyzer(client).answer_question(make_report(), "What is on C1?")

    messages = client.chat_with_tools.call_args.args[0]
    assert messages[0]["role"] == "system"
    assert "list_waveforms" in messages[0]["content"], "the model is told nothing about the report; it must be told to discover it"
    assert messages[1] == {"role": "user", "content": "What is on C1?"}


def test_answer_question_falls_back_when_the_model_cannot_call_tools():
    """A model without tool support must still work exactly as it does today --
    no error, and no capability advertised that cannot be delivered."""
    client = MagicMock()
    client.supports_tools.return_value = False
    client.complete.return_value = "From the summary."

    answer = ReportAnalyzer(client).answer_question(make_report(), "What is on C1?")

    assert answer == "From the summary."
    client.chat_with_tools.assert_not_called()
    assert "C1" in client.complete.call_args.kwargs["prompt"], "the fallback must still send the summarized context"


def test_the_tool_aware_prompt_is_registered():
    prompt = get_system_prompt("chat_tools")
    assert "list_waveforms" in prompt
    assert prompt != get_system_prompt("chat")
