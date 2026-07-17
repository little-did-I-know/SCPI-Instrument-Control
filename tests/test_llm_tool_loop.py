"""The tool-calling loop: dispatch, feedback, recovery, termination.

The fixture patches the ollama SDK class -- see tests/conftest.py's ollama_sdk
docstring for why nothing else works for the SDK path.
"""

from unittest.mock import MagicMock

from scpi_control.report_generator.llm.client import LLMClient, LLMConfig

from tests.conftest import ollama_sdk


def reply(content=None, tool_calls=None):
    """A fake ChatResponse: .message.content and .message.tool_calls."""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls or []
    return MagicMock(message=message)


def tool_call(tool_name, **arguments):
    """Build a fake ToolCall.

    The parameter is `tool_name`, not `name`, because several tools under
    test (greet, explode) themselves take a `name` argument -- `tool_call(
    "greet", name="robin")` would otherwise collide: the positional tool name
    and the keyword argument would both bind to a parameter called `name`,
    raising "got multiple values for argument 'name'". All call sites below
    pass the tool name positionally, so this rename is invisible to them.
    """
    call = MagicMock()
    call.function.name = tool_name
    call.function.arguments = arguments
    return call


def client():
    return LLMClient(LLMConfig(endpoint="http://localhost:11434/api", model="llama3.2"))


def greet(name: str) -> str:
    """Greet someone.

    Args:
        name: Who to greet.
    """
    return f"hello {name}"


def explode(name: str) -> str:
    """Always fails.

    Args:
        name: Ignored.
    """
    raise ValueError("no such channel 'C9'")


def test_returns_the_answer_when_the_model_calls_no_tools():
    with ollama_sdk() as (fake, _):
        fake.chat.side_effect = [reply(content="42")]
        assert client().chat_with_tools([{"role": "user", "content": "hi"}], [greet]) == "42"


def test_dispatches_a_tool_call_and_feeds_the_result_back():
    with ollama_sdk() as (fake, _):
        fake.chat.side_effect = [reply(tool_calls=[tool_call("greet", name="robin")]), reply(content="done")]
        answer = client().chat_with_tools([{"role": "user", "content": "hi"}], [greet])

    assert answer == "done"
    sent = fake.chat.call_args_list[1].kwargs["messages"]
    result = sent[-1]
    assert result["role"] == "tool"
    assert result["tool_name"] == "greet"
    assert result["content"] == "hello robin"


def test_tools_are_passed_to_the_sdk():
    with ollama_sdk() as (fake, _):
        fake.chat.side_effect = [reply(content="ok")]
        client().chat_with_tools([{"role": "user", "content": "hi"}], [greet])
    assert fake.chat.call_args.kwargs["tools"] == [greet]


def test_a_failing_tool_becomes_a_tool_result_not_an_exception():
    """A tool error is data for the model, not an exception for the user: given
    the message it can retry with a valid argument. That recovery is the loop
    earning its keep."""
    with ollama_sdk() as (fake, _):
        fake.chat.side_effect = [reply(tool_calls=[tool_call("explode", name="C9")]), reply(content="recovered")]
        answer = client().chat_with_tools([{"role": "user", "content": "hi"}], [explode])

    assert answer == "recovered"
    result = fake.chat.call_args_list[1].kwargs["messages"][-1]
    assert result["role"] == "tool"
    assert "no such channel 'C9'" in result["content"]


def test_an_unexpected_keyword_argument_becomes_a_tool_result_not_an_exception():
    """Task 1's tool docstrings can nudge the model into inventing a keyword
    argument no tool accepts (e.g. section=). That raises TypeError inside
    function(**arguments); _run_tool's `except Exception` must catch it exactly
    like any other tool failure -- a readable tool-result message, not a crash
    that propagates out of the loop."""
    with ollama_sdk() as (fake, _):
        fake.chat.side_effect = [
            reply(tool_calls=[tool_call("greet", name="robin", section="intro")]),
            reply(content="recovered"),
        ]
        answer = client().chat_with_tools([{"role": "user", "content": "hi"}], [greet])

    assert answer == "recovered"
    result = fake.chat.call_args_list[1].kwargs["messages"][-1]
    assert result["role"] == "tool"
    assert "unexpected keyword argument" in result["content"]
    assert "section" in result["content"]


def test_an_unknown_tool_name_becomes_a_tool_result():
    """The model can hallucinate a tool. Tell it what actually exists."""
    with ollama_sdk() as (fake, _):
        fake.chat.side_effect = [reply(tool_calls=[tool_call("teleport")]), reply(content="ok")]
        client().chat_with_tools([{"role": "user", "content": "hi"}], [greet])

    result = fake.chat.call_args_list[1].kwargs["messages"][-1]
    assert "teleport" in result["content"]
    assert "greet" in result["content"]


def test_max_rounds_terminates_a_model_that_never_stops_calling_tools():
    """Without this bound the loop is an infinite hang. Nothing else in the
    suite would catch it."""
    with ollama_sdk() as (fake, _):
        fake.chat.side_effect = [reply(tool_calls=[tool_call("greet", name="x")]) for _ in range(20)]
        answer = client().chat_with_tools([{"role": "user", "content": "hi"}], [greet], max_rounds=3)

    assert answer is None, "an exhausted loop must fail honestly, not return a half-answer"
    assert fake.chat.call_count == 3


def test_without_an_sdk_client_it_returns_none():
    c = LLMClient(LLMConfig(endpoint="http://localhost:11434/v1", model="llama3.2"))
    assert c._ollama_client is None
    assert c.chat_with_tools([{"role": "user", "content": "hi"}], [greet]) is None
