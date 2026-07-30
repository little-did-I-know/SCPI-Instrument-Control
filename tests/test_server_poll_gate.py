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

from scpi_control.server.adapters import MAX_FRAME_POINTS, ScopeAdapter


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


class _FakeWaveform:
    time = [0.0, 1.0]
    voltage = [0.0, 1.0]


class _FakeScope:
    """Records the stride it was asked for; answers new_acquisition_ready()
    from a fixed sequence, raising if asked more than once per tick (the
    underlying INR? register is read-and-clear -- a second read in the same
    tick would consume a real event and get a meaningless answer)."""

    def __init__(self, ready, record_length=None, max_points=None):
        self._ready = iter(ready)
        self._record_length = record_length
        self._max_points = max_points
        self.supported_channels = [1]
        self.math1 = None
        self.math2 = None
        self.last_stride = None
        self.timebase = 1e-3
        self.trigger = _FakeTrigger()

    def acquisition_status(self):
        return "STOP"

    def new_acquisition_ready(self):
        return next(self._ready)

    def record_length(self):
        return self._record_length

    def waveform_max_points(self):
        return self._max_points

    def get_channel(self, n):
        return _FakeChannel()

    def get_waveform(self, channel, provenance=False, stride=None):
        self.last_stride = stride
        return _FakeWaveform()


def _adapter(ready, record_length=None, max_points=None):
    scope = _FakeScope(ready, record_length=record_length, max_points=max_points)
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
    adapter, scope, published = _adapter(ready=[True], record_length=200_000)
    adapter.poll(scope, published.append, 1)
    assert scope.last_stride == 100  # ceil(200000 / MAX_FRAME_POINTS)


def test_the_stride_also_respects_the_instruments_transfer_cap():
    # A stride sized against MAX_FRAME_POINTS alone can still exceed a low
    # :WAVeform:MAXPoint? cap, turning ModernTransfer's guard
    # (FeatureNotSupportedError, waveform_transfer.py) into a total live-view
    # outage on a model that reports a cap below MAX_FRAME_POINTS. Size
    # against min(MAX_FRAME_POINTS, max_points) instead, so the guard is
    # unreachable by construction.
    adapter, scope, published = _adapter(ready=[True], record_length=200_000, max_points=500)
    adapter.poll(scope, published.append, 1)
    assert scope.last_stride == 400  # ceil(200000 / min(2000, 500))


def test_max_frame_points_constant_is_what_the_stride_test_assumes():
    # Pins the constant the two tests above compute their expectations from,
    # so a change to it fails loudly here instead of silently invalidating
    # the hand-computed assertions above.
    assert MAX_FRAME_POINTS == 2000
