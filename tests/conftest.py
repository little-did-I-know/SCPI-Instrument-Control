"""Fixtures shared across the test suite."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from scpi_control.report_generator.models.report_data import WaveformData


@pytest.fixture(autouse=True)
def _no_real_home(monkeypatch, tmp_path):
    """Never let a test touch the real home directory's default config/storage.

    Per-test discipline has already failed once: a CLI test invoked without
    pinning --config-dir minted a live token into the developer's actual
    ~/.siglent/tokens.json. This fixture is the backstop so that mistake
    cannot happen again, regardless of which test makes it.

    Two known hazards, both worked around here:

    - ``scpi_control.server.auth.DEFAULT_CONFIG_DIR`` is computed once at
      import time (``Path.home() / ".siglent"``), so monkeypatching
      ``Path.home`` after import does not affect it -- the module attribute
      itself has to be patched. ``scpi_control.server.__main__`` imports that
      same name by value (``from ... import DEFAULT_CONFIG_DIR``), which
      copies the binding at import time, so it is patched separately too.
    - ``scpi_control.reference_waveform.ReferenceWaveform.__init__`` calls
      ``Path.home()`` at runtime when no ``storage_dir`` is given, so
      patching ``Path.home`` globally covers that path.

    This only changes *default* resolution: tests that pass an explicit path
    (e.g. ``TokenStore(str(tmp_path / "tokens.json"))``) never consult
    ``Path.home()`` or ``DEFAULT_CONFIG_DIR`` and are unaffected.
    """
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.setattr("scpi_control.server.auth.DEFAULT_CONFIG_DIR", fake_home / ".siglent")
    monkeypatch.setattr("scpi_control.server.__main__.DEFAULT_CONFIG_DIR", fake_home / ".siglent")
    yield fake_home


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


@pytest.fixture()
def gateway_auth(tmp_path):
    """(token_store, headers, raw_token) for an authenticated gateway test client.

    raw_token is needed by WebSocket tests: default client headers do not apply
    to the handshake, which authenticates via subprotocol instead.
    """
    from scpi_control.server.auth import TokenStore

    store = TokenStore(str(tmp_path / "tokens.json"))
    raw = store.mint("tester")
    return store, {"Authorization": "Bearer {0}".format(raw)}, raw


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
