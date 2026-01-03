"""
LLM client for communicating with local and cloud-based language models.

Supports OpenAI-compatible APIs including Ollama, LM Studio, and OpenAI.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import json
import requests
from pathlib import Path


@dataclass
class LLMConfig:
    """Configuration for LLM client."""

    endpoint: str = "http://localhost:11434/v1"  # Default Ollama endpoint
    model: str = "llama3.2"
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 60  # seconds

    def save(self, filepath: Path) -> None:
        """Save configuration to JSON file."""
        data = {
            "endpoint": self.endpoint,
            "model": self.model,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: Path) -> "LLMConfig":
        """Load configuration from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    @classmethod
    def create_ollama_config(cls, model: str = "llama3.2", port: int = 11434) -> "LLMConfig":
        """Create configuration for Ollama."""
        return cls(
            endpoint=f"http://localhost:{port}/v1",
            model=model,
            api_key=None,
        )

    @classmethod
    def create_lm_studio_config(cls, model: str = "local-model", port: int = 1234) -> "LLMConfig":
        """Create configuration for LM Studio."""
        return cls(
            endpoint=f"http://localhost:{port}/v1",
            model=model,
            api_key=None,
        )

    @classmethod
    def create_openai_config(cls, api_key: str, model: str = "gpt-4") -> "LLMConfig":
        """Create configuration for OpenAI."""
        return cls(
            endpoint="https://api.openai.com/v1",
            model=model,
            api_key=api_key,
        )


class LLMClient:
    """Client for communicating with LLM services."""

    def __init__(self, config: LLMConfig):
        """
        Initialize LLM client.

        Args:
            config: LLM configuration
        """
        self.config = config
        self._session = requests.Session()

        # Set up headers
        if config.api_key:
            self._session.headers["Authorization"] = f"Bearer {config.api_key}"
        self._session.headers["Content-Type"] = "application/json"

    def test_connection(self) -> bool:
        """
        Test connection to the LLM service.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try a simple completion request
            response = self.complete("Test connection", max_tokens=5)
            return response is not None
        except Exception:
            return False

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """
        Get a completion from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt for context
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            Completion text, or None if request failed
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        return self.chat(messages, temperature=temperature, max_tokens=max_tokens)

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """
        Send a chat request to the LLM.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            Response text, or None if request failed
        """
        url = f"{self.config.endpoint.rstrip('/')}/chat/completions"

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
        }

        try:
            response = self._session.post(
                url,
                json=payload,
                timeout=self.config.timeout,
            )
            response.raise_for_status()

            data = response.json()
            return data["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            print(f"LLM request failed: {e}")
            return None
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"Failed to parse LLM response: {e}")
            return None

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        Send a streaming chat request to the LLM.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Yields:
            Response chunks as they arrive
        """
        url = f"{self.config.endpoint.rstrip('/')}/chat/completions"

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
            "stream": True,
        }

        try:
            response = self._session.post(
                url,
                json=payload,
                timeout=self.config.timeout,
                stream=True,
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                line = line.decode("utf-8")

                if line.startswith("data: "):
                    line = line[6:]  # Remove "data: " prefix

                if line == "[DONE]":
                    break

                try:
                    chunk = json.loads(line)
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                except json.JSONDecodeError:
                    continue

        except requests.exceptions.RequestException as e:
            print(f"LLM streaming request failed: {e}")

    def get_available_models(self) -> List[str]:
        """
        Get list of available models from the LLM service.

        Returns:
            List of model names, or empty list if request failed
        """
        url = f"{self.config.endpoint.rstrip('/')}/models"

        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            models = [model["id"] for model in data.get("data", [])]
            return models

        except Exception as e:
            print(f"Failed to get models: {e}")
            return []
