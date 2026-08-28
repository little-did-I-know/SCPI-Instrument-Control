"""Model tool-capability gating, and the SDK client's timeout.

READ THE FIXTURE'S DOCSTRING (tests/conftest.py:ollama_sdk). LLMClient.__init__
probes a live Ollama server, and there is one running on the dev machine.
"""

import pytest

from scpi_control.report_generator.llm.client import LLMClient, LLMConfig

from tests.conftest import ollama_sdk

pytestmark = pytest.mark.llm


def ollama_config(model="llama3.2", timeout=60):
    """A config that routes to the SDK path: /api, no /v1."""
    return LLMConfig(endpoint="http://localhost:11434/api", model=model, timeout=timeout)


def test_supports_tools_reads_the_model_capabilities():
    with ollama_sdk(capabilities=("completion", "tools")) as (fake, _):
        client = LLMClient(ollama_config())
        assert client.supports_tools() is True
    fake.show.assert_called_with("llama3.2")


def test_supports_tools_is_false_when_the_model_lacks_them():
    """deepseek-coder-v2 is a real example: ['completion', 'insert'], no tools.
    Passing tools to it would advertise a capability we cannot deliver."""
    with ollama_sdk(capabilities=("completion", "insert")) as (fake, _):
        assert LLMClient(ollama_config(model="deepseek-coder-v2")).supports_tools() is False
        # Prove the capability parse ran, not a no-SDK-client short-circuit.
        assert fake.show.called


def test_supports_tools_is_false_when_the_probe_raises():
    with ollama_sdk() as (fake, _):
        fake.show.side_effect = RuntimeError("server gone")
        assert LLMClient(ollama_config()).supports_tools() is False
        # Prove the exception path ran, not a no-SDK-client short-circuit.
        assert fake.show.called


def test_supports_tools_retries_after_a_probe_that_raised():
    """A raised probe is undecided, not a decided False -- the client is
    long-lived, so a transient outage must not disable tools for the whole
    session. The failure is not cached: a later call retries and can succeed."""
    with ollama_sdk() as (fake, _):
        fake.show.side_effect = RuntimeError("server briefly gone")
        client = LLMClient(ollama_config())
        assert client.supports_tools() is False  # could not decide
        assert client._supports_tools is None  # deliberately not cached
        fake.show.side_effect = None  # server recovers, falls back to return_value
        assert client.supports_tools() is True  # retried, now decided
    assert fake.show.call_count == 2


def test_supports_tools_is_false_without_an_sdk_client():
    """A /v1 endpoint never constructs the SDK client, so tools cannot be sent."""
    client = LLMClient(LLMConfig(endpoint="http://localhost:11434/v1", model="llama3.2"))
    assert client._ollama_client is None
    assert client.supports_tools() is False


def test_supports_tools_caches_the_no_sdk_client_false():
    """No SDK client is a DECIDED False -- a /v1 endpoint never grows one, so
    there is nothing to retry. It must be cached, not re-evaluated every call."""
    client = LLMClient(LLMConfig(endpoint="http://localhost:11434/v1", model="llama3.2"))
    assert client.supports_tools() is False
    assert client._supports_tools is False  # decided and cached, not left None


def test_supports_tools_is_cached():
    with ollama_sdk() as (fake, _):
        client = LLMClient(ollama_config())
        assert client.supports_tools() is True
        assert client.supports_tools() is True
    assert fake.show.call_count == 1


def test_the_sdk_client_receives_the_configured_timeout():
    """config.timeout was silently dead on this path: ollama.Client(host=host)
    took no timeout, so a stalled server hung the worker forever -- while the
    OpenAI path honoured it. A tool loop is multi-turn, so this bites harder."""
    with ollama_sdk() as (_, cls):
        LLMClient(ollama_config(timeout=17))
    assert cls.call_args.kwargs["timeout"] == 17
