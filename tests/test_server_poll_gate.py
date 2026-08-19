"""ScopeAdapter.poll() gates the waveform fetch on new_acquisition_ready().

Without this gate, poll() asks for a waveform on a fixed timer regardless of
whether the scope has actually finished acquiring one. Against a real
instrument at a slow timebase, that read blocks for the rest of the
acquisition -- and the session's single worker thread is also the only thing
servicing user commands, so every control in the web UI hangs for the length
of the capture.

These tests use a fake scope rather than a MockConnection-backed Oscilloscope:
this is the adapter's decision logic under test, not SCPI wire behaviour.
"""

import numpy as np
import pytest

from scpi_control.server.adapters import DENSE_MAX_POINTS, MAX_FRAME_POINTS, ScopeAdapter
from scpi_control.waveform import WaveformData


class _FakeChannel:
    enabled = True
    # The rest is only here so read_state() (which initial_frame calls) can
    # read a channel without a real Oscilloscope.
    voltage_scale = 1.0
    voltage_offset = 0.0
    coupling = "DC"
    probe_ratio = 1.0


class _FakeTrigger:
    mode = "AUTO"
    source = "C1"
    level = 0.0
    slope = "POS"
    coupling = "DC"


class _FakeScope:
    """Records the stride it was asked for; answers new_acquisition_ready()
    from a fixed sequence, raising if asked more than once per tick (the
    underlying INR? register is read-and-clear -- a second read in the same
    tick would consume a real event and get a meaningless answer)."""

    def __init__(self, ready, record_length=None, max_points=None, waveform_len=2):
        self._ready = iter(ready)
        self._record_length = record_length
        self._max_points = max_points
        self.max_points_queries = 0
        self.supported_channels = [1]
        self.math1 = None
        self.math2 = None
        self.last_stride = None
        self.timebase = 1e-3
        self.trigger = _FakeTrigger()
        self._waveform_len = waveform_len

    def acquisition_status(self):
        return "STOP"

    def new_acquisition_ready(self):
        return next(self._ready)

    def record_length(self):
        return self._record_length

    def waveform_max_points(self):
        self.max_points_queries += 1
        return self._max_points

    def get_channel(self, n):
        return _FakeChannel()

    def get_waveform(self, channel, provenance=False, stride=None):
        self.last_stride = stride
        # A real WaveformData (a dataclass), not the old _FakeWaveform: the
        # adapter's post-read cap uses dataclasses.replace() on it.
        n = self._waveform_len
        return WaveformData(time=np.arange(n) * 1e-6, voltage=np.arange(n, dtype=float), channel=channel)


def _adapter(ready, record_length=None, max_points=None, waveform_len=2):
    scope = _FakeScope(ready, record_length=record_length, max_points=max_points, waveform_len=waveform_len)
    adapter = ScopeAdapter()
    published = []
    return adapter, scope, published


def test_the_first_tick_fetches_without_waiting_for_a_new_acquisition():
    # Otherwise a scope sitting in Stop shows an empty canvas forever, when it
    # has a perfectly good last frame to display.
    adapter, scope, published = _adapter(ready=[False, False])
    adapter.poll(scope, published.append, 1)
    assert any(f["type"] == "waveform" for f in published)


def test_a_later_tick_publishes_nothing_when_no_new_acquisition_landed():
    adapter, scope, published = _adapter(ready=[False, False])
    adapter.poll(scope, published.append, 1)  # first tick always fetches
    published.clear()
    adapter.poll(scope, published.append, 2)
    assert published == []


def test_a_later_tick_fetches_when_a_new_acquisition_landed():
    adapter, scope, published = _adapter(ready=[False, True])
    adapter.poll(scope, published.append, 1)
    published.clear()
    adapter.poll(scope, published.append, 2)
    assert any(f["type"] == "waveform" for f in published)


def test_a_dialect_without_the_gate_keeps_fetching_every_tick():
    # The tri-state's whole purpose: None must not be read as False, or the live
    # view dies on every non-Siglent scope.
    adapter, scope, published = _adapter(ready=[None, None])
    adapter.poll(scope, published.append, 1)
    published.clear()
    adapter.poll(scope, published.append, 2)
    assert any(f["type"] == "waveform" for f in published)


def test_a_new_viewer_gets_the_first_tick_exemption_again():
    """Final-review fix (Important 2): the exemption was tracked per SESSION
    but the canvas it protects belongs to a SUBSCRIBER. The frontend clears
    every frame on unmount, and initial_frame publishes only a `state` frame --
    so a viewer that reloads the page had an empty canvas and a flag saying "a
    frame was already published", and on a scope sitting in Stop (INR? bit 0
    never sets again) it stayed empty forever, with no error and no log line.
    Seeding a new stream must re-arm the exemption.
    """
    adapter, scope, published = _adapter(ready=[False, False])
    adapter.poll(scope, published.append, 1)  # first tick fetches under the exemption
    assert any(f["type"] == "waveform" for f in published)

    adapter.initial_frame(scope)  # a viewer (re)opens the stream: fresh, empty canvas

    published.clear()
    adapter.poll(scope, published.append, 2)
    assert any(f["type"] == "waveform" for f in published), "a reloaded viewer with a cleared canvas must get a frame, not wait forever for an acquisition that never comes"


def test_the_stride_is_sized_from_the_record_length():
    adapter, scope, published = _adapter(ready=[True], record_length=2_000_000)
    adapter.poll(scope, published.append, 1)
    assert scope.last_stride == 20  # ceil(2_000_000 / DENSE_MAX_POINTS)


def test_the_stride_also_respects_the_instruments_transfer_cap():
    # A stride sized against DENSE_MAX_POINTS alone can still exceed a low
    # :WAVeform:MAXPoint? cap, turning ModernTransfer's guard
    # (FeatureNotSupportedError, waveform_transfer.py) into a total live-view
    # outage on a model that reports a cap below the dense budget. Size
    # against min(DENSE_MAX_POINTS, max_points) instead, so the guard is
    # unreachable by construction.
    adapter, scope, published = _adapter(ready=[True], record_length=200_000, max_points=500)
    adapter.poll(scope, published.append, 1)
    assert scope.last_stride == 400  # ceil(200000 / min(100000, 500))


def test_the_caps_are_what_the_stride_tests_assume():
    # Pins both constants the tests above compute their expectations from,
    # so a change to either fails loudly here instead of silently invalidating
    # the hand-computed assertions. MAX_FRAME_POINTS is the JSON wire cap and
    # is a contract; DENSE_MAX_POINTS is the dense-path budget.
    assert DENSE_MAX_POINTS == 100_000
    assert MAX_FRAME_POINTS == 2000


def test_a_reintroduced_2000_point_budget_would_fail_here():
    # Guard against the dense budget quietly regressing to the old JSON cap:
    # a 100k record must be read at stride 1, not 50.
    adapter, scope, published = _adapter(ready=[True], record_length=100_000)
    adapter.poll(scope, published.append, 1)
    assert scope.last_stride == 1


def test_the_transfer_cap_is_asked_once_per_session_not_once_per_tick():
    # :WAVeform:MAXPoint? is a per-model constant (5 000 000 on an SDS824X HD)
    # and costs a ~10 ms round trip; asking it every tick was pure overhead.
    adapter, scope, published = _adapter(ready=[True, True, True], record_length=100_000, max_points=5_000_000)
    for tick in (1, 2, 3):
        adapter.poll(scope, published.append, tick)
    assert scope.max_points_queries == 1


def test_an_unanswered_transfer_cap_is_asked_again_next_tick():
    # None means "the dialect could not answer" (legacy Siglent) or a transient
    # failure -- neither may be cached as a permanent answer.
    adapter, scope, published = _adapter(ready=[True, True], record_length=100_000, max_points=None)
    adapter.poll(scope, published.append, 1)
    adapter.poll(scope, published.append, 2)
    assert scope.max_points_queries == 2


def test_a_record_that_still_exceeds_the_budget_is_capped_after_the_read():
    # record_length() is None on legacy dialects, so no stride is requested and
    # the whole record comes back; the frame must still respect the budget.
    adapter, scope, published = _adapter(ready=[True], record_length=None, waveform_len=250_000)
    adapter.configure_stream(max_points=100_000, max_fps=20.0)
    adapter.poll(scope, published.append, 1)
    frame = next(f for f in published if f["type"] == "waveform")
    assert scope.last_stride is None
    assert len(frame["samples"]) <= 100_000
    assert frame["dt"] == pytest.approx(3e-6)  # stride 3 = ceil(250000/100000)


def test_published_frames_carry_samples_and_a_seq_that_advances_per_acquisition():
    adapter, scope, published = _adapter(ready=[True, True], record_length=100_000)
    adapter.poll(scope, published.append, 1)
    adapter.poll(scope, published.append, 2)
    frames = [f for f in published if f["type"] == "waveform"]
    assert all("samples" in f and "points" not in f for f in frames)
    assert frames[0]["seq"] + 1 == frames[1]["seq"]


def test_configure_stream_sets_the_scope_poll_interval_from_max_fps():
    adapter = ScopeAdapter()
    assert adapter.poll_interval == pytest.approx(1 / 20)  # default DEFAULT_STREAM_MAX_FPS
    adapter.configure_stream(max_points=50_000, max_fps=4.0)
    assert adapter.max_points == 50_000 and adapter.poll_interval == pytest.approx(0.25)
