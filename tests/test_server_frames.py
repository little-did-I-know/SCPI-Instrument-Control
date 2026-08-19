"""frames.py: one internal waveform message, two wire encodings.

The JSON encoding is the pre-existing WebSocket contract and must not change;
the binary encoding is the new opt-in dense path. Both are pure functions of
the internal message, so they are tested here without a socket or a session.
"""
import json
import math
import struct

import numpy as np
import pytest

from scpi_control.server import frames
from scpi_control.server.frames import (
    DENSE_MAX_POINTS,
    MAX_FRAME_POINTS,
    decode_binary,
    is_sample_message,
    reference_message,
    to_binary,
    to_json,
    waveform_message,
)


def _msg(n, channel=1, seq=3, t0=-0.007, dt=1e-6):
    time_axis = t0 + np.arange(n) * dt
    voltage = np.sin(np.arange(n) * 0.01)
    return waveform_message(channel, time_axis, voltage, seq=seq)


def test_constants_pin_the_two_caps():
    assert MAX_FRAME_POINTS == 2000  # the JSON wire cap; the contract tests below hand-compute from it
    assert DENSE_MAX_POINTS == 100_000


def test_waveform_message_carries_a_contiguous_float64_array_and_metadata():
    msg = _msg(5)
    assert msg["type"] == "waveform" and msg["channel"] == 1 and msg["seq"] == 3
    assert msg["t0"] == pytest.approx(-0.007) and msg["dt"] == pytest.approx(1e-6)
    assert isinstance(msg["samples"], np.ndarray)
    assert msg["samples"].dtype == np.float64 and msg["samples"].flags["C_CONTIGUOUS"]
    assert len(msg["samples"]) == 5
    assert "points" not in msg


def test_waveform_message_with_no_samples_uses_the_legacy_placeholders():
    msg = waveform_message("M1", [], [])
    assert msg["t0"] == 0.0 and msg["dt"] == 1.0 and len(msg["samples"]) == 0


def test_reference_message_shape():
    msg = reference_message("golden", 2, [0.0, 1.0], [0.5, 0.25])
    assert msg["type"] == "reference" and msg["name"] == "golden" and msg["channel"] == 2
    assert "seq" not in msg and len(msg["samples"]) == 2


def test_is_sample_message():
    assert is_sample_message(_msg(3))
    assert is_sample_message(reference_message(None, None, [], []))
    assert not is_sample_message({"type": "state", "state": {}})
    assert not is_sample_message({"type": "waveform", "points": [1.0]})  # already JSON-shaped
    assert not is_sample_message("closed")


@pytest.mark.parametrize("n", [0, 1, 1999, 2000, 2001, 4001, 14001, 100_000])
def test_to_json_reproduces_the_legacy_wire_shape(n):
    msg = _msg(n)
    out = to_json(msg)
    step = max(1, -(-n // MAX_FRAME_POINTS))
    assert set(out) == {"type", "channel", "t0", "dt", "points"}  # no samples, no seq, nothing new
    assert out["type"] == "waveform" and out["channel"] == 1
    assert out["t0"] == msg["t0"]
    assert out["dt"] == pytest.approx(msg["dt"] * step)
    assert len(out["points"]) <= MAX_FRAME_POINTS
    assert out["points"] == [float(v) for v in msg["samples"][::step]]
    assert all(type(v) is float for v in out["points"])  # json-serialisable Python floats, not numpy scalars
    json.dumps(out)


def test_to_json_of_an_empty_message_keeps_the_legacy_placeholders():
    out = to_json(waveform_message("F1", [], []))
    assert out == {"type": "waveform", "channel": "F1", "t0": 0.0, "dt": 1.0, "points": []}


def test_to_json_of_a_reference_keeps_name_and_channel_and_drops_samples():
    out = to_json(reference_message("golden", 2, [0.0, 1.0, 2.0], [1.0, 2.0, 3.0]))
    assert out == {"type": "reference", "name": "golden", "channel": 2, "t0": 0.0, "dt": 1.0, "points": [1.0, 2.0, 3.0]}


def test_to_json_passes_non_sample_messages_through_untouched():
    state = {"type": "state", "state": {"timebase": 1e-3}}
    assert to_json(state) is state


def test_binary_round_trip_preserves_every_sample_as_float32():
    msg = _msg(100_000, channel="M2", seq=42)
    blob = to_binary(msg)
    header, samples = decode_binary(blob)
    assert header == {"type": "waveform", "channel": "M2", "t0": msg["t0"], "dt": msg["dt"], "seq": 42, "n": 100_000, "dtype": "f32"}
    assert samples.dtype == np.dtype("<f4") and len(samples) == 100_000
    np.testing.assert_array_equal(samples, msg["samples"].astype("<f4"))


def test_binary_layout_is_length_prefixed_and_payload_is_4_byte_aligned():
    blob = to_binary(_msg(3))
    (header_len,) = struct.unpack_from("<I", blob, 0)
    assert header_len % 4 == 0  # padded so the browser can wrap the payload in a Float32Array view without copying
    header = json.loads(blob[4 : 4 + header_len])  # trailing spaces are legal JSON whitespace
    assert header["n"] == 3
    assert len(blob) == 4 + header_len + 3 * 4


def test_binary_empty_frame_has_n_zero_and_no_payload():
    header, samples = decode_binary(to_binary(waveform_message("M1", [], [])))
    assert header["n"] == 0 and len(samples) == 0


def test_binary_nan_survives():
    msg = waveform_message(1, [0.0, 1e-6], [float("nan"), 1.5])
    _header, samples = decode_binary(to_binary(msg))
    assert math.isnan(float(samples[0])) and float(samples[1]) == pytest.approx(1.5)


def test_binary_reference_header_mirrors_the_message_type():
    header, _ = decode_binary(to_binary(reference_message("golden", 1, [0.0], [1.0])))
    assert header["type"] == "reference" and header["name"] == "golden" and header["channel"] == 1 and "seq" not in header


def test_to_binary_refuses_a_non_sample_message():
    with pytest.raises(TypeError):
        to_binary({"type": "state", "state": {}})


def test_module_has_no_fastapi_dependency():
    # frames.py is imported by adapters.py, which the no-web test paths import too.
    assert "fastapi" not in frames.__dict__ and "starlette" not in frames.__dict__
