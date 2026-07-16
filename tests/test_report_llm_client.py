"""The LLM client and DAQ analyzer, against a mocked transport. No network."""

from unittest.mock import MagicMock, patch

import pytest

from scpi_control.report_generator.llm.client import LLMClient, LLMConfig


def test_create_daq_analyzer_constructs():
    """It raised TypeError on every call: LLMClient takes a config, not kwargs.

    Its only caller (the GUI DAQ panel) wrapped it in a catch-all, so the
    feature was entirely dead and reported itself as 'Connection failed'.
    """
    from scpi_control.report_generator.llm.daq_analyzer import create_daq_analyzer

    # The "ollama" provider builds a native-API endpoint, which makes
    # LLMClient.__init__ probe for a live Ollama server via the ollama
    # Python SDK if it's installed. Disable that probe so this test is a
    # pure construction check, not a real network call to localhost.
    with patch("scpi_control.report_generator.llm.client.OLLAMA_CLIENT_AVAILABLE", False):
        analyzer = create_daq_analyzer(provider="ollama", model="llama3.2")

    assert analyzer is not None
    assert analyzer.client.config.model == "llama3.2"


def test_create_daq_analyzer_openai_provider_carries_the_key():
    from scpi_control.report_generator.llm.daq_analyzer import create_daq_analyzer

    analyzer = create_daq_analyzer(provider="openai", model="gpt-4", api_key="sk-test")

    assert analyzer.client.config.api_key == "sk-test"
    assert "openai.com" in analyzer.client.config.endpoint


def test_create_daq_analyzer_rejects_an_unknown_provider():
    from scpi_control.report_generator.llm.daq_analyzer import create_daq_analyzer

    with pytest.raises(ValueError, match="Unknown provider"):
        create_daq_analyzer(provider="nonesuch", model="x")


def test_chat_posts_to_the_openai_compatible_endpoint():
    # endpoint has "/v1" (no "/api"), so LLMClient routes this as OpenAI-compatible,
    # not Ollama-native -- no separate "use_native_api" field exists on LLMConfig.
    config = LLMConfig(endpoint="http://localhost:1234/v1", model="local-model")
    client = LLMClient(config)

    fake = MagicMock()
    fake.status_code = 200
    fake.json.return_value = {"choices": [{"message": {"content": "hello"}}]}

    # LLMClient posts via a persistent requests.Session, not the module-level
    # requests.post, so the transport must be mocked at Session.post.
    with patch("requests.Session.post", return_value=fake) as post:
        reply = client.chat([{"role": "user", "content": "hi"}])

    assert reply == "hello"
    assert "/chat/completions" in post.call_args[0][0]


def test_chat_returns_none_when_the_transport_fails():
    import requests

    config = LLMConfig(endpoint="http://localhost:1234/v1", model="local-model")
    client = LLMClient(config)

    with patch("requests.Session.post", side_effect=requests.exceptions.ConnectionError("connection refused")):
        assert client.chat([{"role": "user", "content": "hi"}]) is None


def test_stream_chat_is_gone():
    """Dead code: never called, and it POSTed to /chat/completions
    unconditionally -> 404 against the default Ollama native endpoint."""
    assert not hasattr(LLMClient, "stream_chat")
