"""Fixtures shared across the test suite."""

import asyncio
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from scpi_control.report_generator.models.report_data import WaveformData


def _event_loop_state():
    """(holder, loop, set_called) for this thread's current-event-loop state.

    ``asyncio`` exposes no way to *read* the current loop without creating one:
    ``asyncio.get_event_loop()`` is the only getter, and on a pristine main
    thread it installs a brand new loop as a side effect. Snapshotting through
    it would therefore mean creating a loop for every one of the ~2100 tests in
    this suite, and would destroy the very pristine-ness we want to restore.

    So this reads the policy's thread-local holder directly. Both attributes
    have lived on ``asyncio.BaseDefaultEventLoopPolicy._Local`` since 3.4 and
    are still there on 3.14; uvloop's policy subclasses it and has them too.
    They are private, which is why ``test_the_event_loop_guard_is_in_force``
    (tests/test_server_admin_listener.py) exists -- if a future Python moves
    them, that test fails loudly instead of the guard silently doing nothing.

    Returns ``(None, None, False)`` for an exotic policy without the holder, so
    the guard degrades to a no-op rather than damaging state it cannot read.
    """
    holder = getattr(asyncio.get_event_loop_policy(), "_local", None)
    if holder is None:
        return None, None, False
    return holder, getattr(holder, "_loop", None), getattr(holder, "_set_called", False)


@contextmanager
def preserved_event_loop_state():
    """Restore the current-event-loop state that ``asyncio.run()`` destroys.

    ``asyncio.run()`` ends with ``events.set_event_loop(None)``, which leaves
    the policy holding ``_set_called = True`` and ``_loop = None``. In that
    state ``asyncio.get_event_loop()`` no longer creates a loop on demand -- it
    raises ``RuntimeError: There is no current event loop in thread
    'MainThread'``. That is process-global, so a test calling ``asyncio.run()``
    breaks whatever runs *next* in the same worker, not itself.

    This is not hypothetical: it took down three tests in
    tests/test_server_stream_ws.py on CI, a file nobody had touched, on Python
    3.9 only. 3.9 caps at fastapi 0.128.8, and that older starlette stack calls
    ``get_event_loop()`` where newer releases do not, so 3.10-3.14 stayed green
    while the oldest supported Python failed.

    Snapshot-and-restore rather than "install a fresh loop": for the vast
    majority of tests nothing changed and the teardown is two comparisons and
    no allocation. Nothing here creates a loop, and nothing closes one -- a
    loop a test opened is that test's to close.
    """
    holder, loop, set_called = _event_loop_state()
    try:
        yield
    finally:
        if holder is not None:
            _, now_loop, now_set_called = _event_loop_state()
            if now_loop is not loop or now_set_called != set_called:
                holder._loop = loop
                holder._set_called = set_called


@pytest.fixture(autouse=True)
def _no_leaked_event_loop():
    """Never let one test's ``asyncio.run()`` break the next test in the worker.

    The third guard of its kind here, and for the third time because per-test
    discipline had already failed: ``_no_real_home`` after a test minted a live
    token into the developer's real ~/.siglent, ``_no_real_browser`` after
    tests started opening real browser windows, and now this. Two tests on this
    branch call ``asyncio.run()`` -- one directly, one via a real
    ``uvicorn.Server.run()``, which *is* ``asyncio.run()`` -- and the damage
    they do lands somewhere else entirely, on one Python version, in whichever
    file the worker happens to pick up next. Asking the next person who writes
    an ``asyncio.run()`` in a test to remember this is exactly the discipline
    that has already failed twice.

    Async tests are unaffected: both pytest-asyncio and anyio create and hold
    their own loop for the test rather than adopting the ambient one, and
    anyio's blocking portal (what starlette's TestClient uses) runs its loop in
    a worker thread whose state this fixture never reads or writes.
    """
    with preserved_event_loop_state():
        yield


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


@pytest.fixture(autouse=True)
def _no_real_browser(monkeypatch):
    """Never let a test pop a real browser window (or whatever a headless CI
    runner does when asked to open one).

    Per-test discipline is not enough here, the same lesson as _no_real_home
    above: scpi_control.server.__main__._open_browser is reachable from any
    test that calls main() against a fresh (empty) config dir -- a first-run
    gateway opens the setup screen unless told not to. Two tests already hit
    this by accident once that path started doing real browser I/O, each
    stubbing it individually. This is the backstop so a third one cannot slip
    through the same way ~/.siglent did.

    Patches ``webbrowser.open`` itself, not our own ``_open_browser``
    wrapper. ``webbrowser.open`` is the actual OS boundary -- patching it
    also covers any future code path that reaches the stdlib directly,
    something patching our wrapper could never do -- and it leaves
    ``_open_browser``'s own try/except doing real work against a stubbed
    call instead of being bypassed entirely.

    This does not stop a test from asserting its own behaviour: a test can
    still monkeypatch ``_open_browser`` directly, to capture the URL it was
    given or to force it to raise. Fixtures run before the test body, so a
    test's own monkeypatch.setattr on the same or a different target simply
    layers on top of (or replaces) this one -- it is never overridden by it.
    """
    monkeypatch.setattr("webbrowser.open", lambda url, *args, **kwargs: True)


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
