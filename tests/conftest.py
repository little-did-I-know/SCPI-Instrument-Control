"""Fixtures shared across the test suite."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from scpi_control.report_generator.models.report_data import WaveformData


@contextmanager
def ollama_sdk(capabilities=("completion", "tools")):
    """Patch the ollama SDK class so nothing reaches the network.

    LLMClient.__init__ calls .list() against a real server (client.py:136), and a
    live Ollama runs on this machine. The existing dodges in
    test_report_llm_client.py -- patching OLLAMA_CLIENT_AVAILABLE=False, or using
    a /v1 endpoint -- both work by AVOIDING the SDK path, which is exactly where
    tool calling lives. So tool tests must patch the class itself.

    Get this wrong and the test does not fail: it does a real round-trip and
    passes for the wrong reason, and .list()'s failure is caught and merely
    warned (client.py:138-140), so a half-mock stays silent.
    """
    fake = MagicMock()
    fake.list.return_value = MagicMock(models=[])
    fake.show.return_value = MagicMock(capabilities=list(capabilities))
    with patch("scpi_control.report_generator.llm.client.ollama.Client", return_value=fake) as cls:
        yield fake, cls


@pytest.fixture
def bursty_waveform():
    """A sine carrying 20 multi-sample spikes -- more real transients than the
    tools will show, so truncation paths are reachable.

    The spikes are several samples wide because detect_transients discards any
    region shorter than 0.1% of the capture; single-sample spikes never clear
    that, however many you add. Function-scoped: detect_regions mutates
    waveform.regions, so each test needs its own.
    """
    n, rate = 4000, 1e6
    t = np.arange(n) / rate
    v = np.sin(2 * np.pi * 10_000 * t)
    for start in np.linspace(50, n - 100, 20).astype(int):
        v[start : start + 6] += 8.0
    return WaveformData(channel="C1", time=t, voltage=v, sample_rate=rate, record_length=n)
