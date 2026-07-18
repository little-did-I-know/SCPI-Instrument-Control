"""The six oscilloscope system prompts carry the shared grounding rule, and
chat_tools keeps its tool-loop specifics on top of it."""

import pytest

from scpi_control.report_generator.llm.prompts import _GROUNDING, get_system_prompt

ALL_PROMPTS = ["expert", "summary", "analysis", "interpretation", "chat", "chat_tools"]


@pytest.mark.parametrize("prompt_type", ALL_PROMPTS)
def test_every_prompt_carries_the_shared_grounding_rule(prompt_type):
    assert _GROUNDING, "the grounding constant must be non-empty"
    assert _GROUNDING in get_system_prompt(prompt_type)


def test_chat_tools_keeps_its_tool_loop_specifics():
    prompt = get_system_prompt("chat_tools")
    assert "list_waveforms" in prompt
    assert prompt.index("list_waveforms") < prompt.index("analyze_waveform"), "discover-first ordering must survive"
    assert "returns an error" in prompt, "the retry guidance unique to the tool loop must survive"


def test_summary_forbids_preamble_and_closing_remarks():
    assert "Write only the summary itself" in get_system_prompt("summary")
