"""
LLM client for communicating with local and cloud-based language models.

Supports OpenAI-compatible APIs including Ollama, LM Studio, and OpenAI.
Uses the official Ollama Python client for Ollama connections.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Try to import ollama Python client
try:
    import ollama

    OLLAMA_CLIENT_AVAILABLE = True
except ImportError:
    OLLAMA_CLIENT_AVAILABLE = False


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
    def create_ollama_config(cls, model: str = "llama3.2", hostname: str = "localhost", port: int = 11434, use_native_api: bool = True) -> "LLMConfig":
        """
        Create configuration for Ollama.

        Args:
            model: Model name to use
            hostname: Hostname or IP address of Ollama server (default: "localhost")
            port: Port number (default: 11434)
            use_native_api: Use Ollama's native API instead of OpenAI-compatible (default: True)
        """
        # Use native Ollama API endpoint by default (more reliable)
        endpoint = f"http://{hostname}:{port}/api" if use_native_api else f"http://{hostname}:{port}/v1"
        return cls(
            endpoint=endpoint,
            model=model,
            api_key=None,
        )

    @classmethod
    def create_lm_studio_config(cls, model: str = "local-model", hostname: str = "localhost", port: int = 1234) -> "LLMConfig":
        """
        Create configuration for LM Studio.

        Args:
            model: Model name to use
            hostname: Hostname or IP address of LM Studio server (default: "localhost")
            port: Port number (default: 1234)
        """
        return cls(
            endpoint=f"http://{hostname}:{port}/v1",
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

        # Detect if using Ollama native API
        self._is_ollama_native = "/api" in config.endpoint and "/v1" not in config.endpoint

        # Initialize Ollama Python client if available and using Ollama
        self._ollama_client = None
        if self._is_ollama_native and OLLAMA_CLIENT_AVAILABLE:
            try:
                # Extract host from endpoint (e.g., "http://192.168.1.4:11434/api" -> "http://192.168.1.4:11434")
                host = config.endpoint.rsplit("/api", 1)[0] if "/api" in config.endpoint else config.endpoint
                self._ollama_client = ollama.Client(host=host)
                print(f"Using Ollama Python SDK (host: {host})")

                # Verify connection by listing models
                try:
                    models = self._ollama_client.list()
                    print(f"Connected to Ollama ({len(models.models)} models available)")
                except Exception as e:
                    print(f"Warning: Ollama client created but can't connect: {e}")
                    # Keep the client anyway - maybe it'll work later
            except Exception as e:
                print(f"Failed to initialize Ollama client: {e}")
                print("Falling back to HTTP requests")
                self._ollama_client = None

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
        # Use Ollama Python client if available
        if self._ollama_client is not None:
            return self._chat_ollama_python_client(messages, temperature, max_tokens)
        elif self._is_ollama_native:
            return self._chat_ollama_native(messages, temperature, max_tokens)
        else:
            return self._chat_openai_compatible(messages, temperature, max_tokens)

    def _chat_openai_compatible(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """OpenAI-compatible API format."""
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

            # Check for errors in response
            if "error" in data:
                print(f"LLM API error: {data['error']}")
                return None

            return data["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            print(f"LLM request failed: {e}")
            return None
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"Failed to parse LLM response: {e}")
            return None

    def _chat_ollama_python_client(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """Use Ollama Python client for chat."""
        try:
            # Build options
            options = {
                "temperature": temperature if temperature is not None else self.config.temperature,
            }
            if max_tokens is not None:
                options["num_predict"] = max_tokens

            # Make request using Python client
            response = self._ollama_client.chat(
                model=self.config.model,
                messages=messages,
                options=options,
            )

            # Extract content from response
            return response["message"]["content"]

        except ollama.ResponseError as e:
            print(f"Ollama API error: {e}")
            print(f"Model: {self.config.model}")
            if "do load request" in str(e):
                print("\n" + "=" * 60)
                print("ERROR: Ollama server cannot load the model")
                print("=" * 60)
                print("This is an Ollama server issue, not the application.")
                print("\nPossible causes:")
                print("  1. Not enough VRAM/RAM for the model")
                print("  2. Ollama service needs restart")
                print("  3. Model files are corrupted")
                print("\nTry on your Ollama server:")
                print(f"  ollama run {self.config.model} 'test'")
                print("=" * 60 + "\n")
            return None
        except Exception as e:
            print(f"Unexpected error with Ollama client: {type(e).__name__}: {e}")
            return None

    def _chat_ollama_native(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """Ollama native API format (HTTP fallback)."""
        url = f"{self.config.endpoint.rstrip('/')}/chat"

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.config.temperature,
            },
        }

        # Ollama native API doesn't use max_tokens in the same way
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        try:
            response = self._session.post(
                url,
                json=payload,
                timeout=self.config.timeout,
            )
            response.raise_for_status()

            data = response.json()

            # Check for errors
            if "error" in data:
                print(f"Ollama API error: {data['error']}")
                return None

            # Ollama native format returns message in different structure
            return data.get("message", {}).get("content", None)

        except requests.exceptions.RequestException as e:
            print(f"LLM request failed: {e}")
            print(f"Endpoint: {url}")
            print(f"Model: {self.config.model}")
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
        # Use Ollama Python client if available
        if self._ollama_client is not None:
            try:
                response = self._ollama_client.list()
                # Extract model names from Model objects
                return [model.model for model in response.models]
            except Exception as e:
                print(f"Failed to get models from Ollama: {e}")
                return []

        # HTTP-based approach for other services
        if self._is_ollama_native:
            # Ollama native API uses /api/tags
            url = f"{self.config.endpoint.rstrip('/')}/tags"
        else:
            # OpenAI-compatible uses /models
            url = f"{self.config.endpoint.rstrip('/')}/models"

        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()

            if self._is_ollama_native:
                # Ollama format: {"models": [{"name": "..."}, ...]}
                models = [model["name"] for model in data.get("models", [])]
            else:
                # OpenAI format: {"data": [{"id": "..."}, ...]}
                models = [model["id"] for model in data.get("data", [])]

            return models

        except Exception as e:
            print(f"Failed to get models: {e}")
            return []
