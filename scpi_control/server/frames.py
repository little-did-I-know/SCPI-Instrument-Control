"""Waveform stream messages: one un-serialized internal shape, two wire encodings.

The poll loop publishes *messages* -- plain dicts carrying a numpy array under
``samples`` -- and never a wire format. Encoding happens once per delivered
frame, per socket, in ``api/stream.py``, because two clients on the same
session may have negotiated different formats:

* ``to_json``   -- the pre-8.x WebSocket contract, unchanged: at most
                   MAX_FRAME_POINTS stride-decimated Python floats under
                   ``points``. Value-identical to what the adapter used to
                   publish directly (samples stay float64 internally).
* ``to_binary`` -- the opt-in dense path (``?format=binary``):
                   ``uint32 LE header_len | UTF-8 JSON header | float32 LE[]``.
                   The header is space-padded to a multiple of four bytes so
                   the payload starts 4-byte aligned and a browser can wrap it
                   in a Float32Array view without copying.

Kept free of FastAPI so adapters.py (imported on paths that never load the
web extra) can depend on it.
"""
import json
import struct
from typing import Any, Dict, Sequence, Tuple, Union

import numpy as np

# The JSON wire cap. This is the contract every existing WebSocket consumer
# was written against, so it does not move when the dense budget does.
MAX_FRAME_POINTS = 2000
# Default per-frame budget for the dense path. Measured on an SDS824X HD, a
# waveform read costs ~250 ms whether it returns 700 or 100 000 points, so a
# dense frame is free at the instrument; the cap bounds memory and bandwidth
# (100k float32 = 400 kB per frame per channel).
DENSE_MAX_POINTS = 100_000
DENSE_DTYPE = np.dtype("<f4")

_SAMPLE_TYPES = ("waveform", "reference")


def waveform_message(channel: Union[int, str], time_axis: Sequence[float], voltage: Sequence[float], seq: int = 0) -> Dict[str, Any]:
    """The internal waveform message for one trace (a channel number, or 'M1'/'M2'/'F1'/'F2')."""
    samples = np.ascontiguousarray(np.asarray(voltage, dtype=np.float64).ravel())
    n_time = len(time_axis)
    t0 = float(time_axis[0]) if n_time else 0.0
    dt = float(time_axis[1] - time_axis[0]) if n_time > 1 else 1.0
    return {"type": "waveform", "channel": channel, "t0": t0, "dt": dt, "seq": int(seq), "samples": samples}


def reference_message(name: Any, channel: Any, time_axis: Sequence[float], voltage: Sequence[float]) -> Dict[str, Any]:
    """The internal reference-overlay message; ``name``/``channel`` are None when the overlay is cleared."""
    message = waveform_message(channel, time_axis, voltage)
    del message["seq"]
    message["type"] = "reference"
    message["name"] = name
    return message


def is_sample_message(message: Any) -> bool:
    return isinstance(message, dict) and message.get("type") in _SAMPLE_TYPES and isinstance(message.get("samples"), np.ndarray)


def to_json(message: Any) -> Any:
    """The legacy JSON wire dict for a sample message; anything else is returned as-is."""
    if not is_sample_message(message):
        return message
    samples = message["samples"]
    step = max(1, -(-len(samples) // MAX_FRAME_POINTS))  # ceiling division keeps len(points) <= cap
    out = {key: value for key, value in message.items() if key not in ("samples", "seq")}
    out["dt"] = message["dt"] * step
    out["points"] = [float(v) for v in samples[::step]]
    return out


def to_binary(message: Any) -> bytes:
    """``uint32 LE header_len | JSON header (space-padded to 4n bytes) | float32 LE payload``."""
    if not is_sample_message(message):
        raise TypeError("to_binary() needs a waveform/reference message with samples, got {0!r}".format(type(message).__name__ if not isinstance(message, dict) else message.get("type")))
    samples = np.ascontiguousarray(message["samples"], dtype=DENSE_DTYPE)
    header = {key: value for key, value in message.items() if key != "samples"}
    header["n"] = int(samples.size)
    header["dtype"] = "f32"
    head = json.dumps(header, separators=(",", ":")).encode("utf-8")
    head += b" " * (-len(head) % 4)
    return struct.pack("<I", len(head)) + head + samples.tobytes()


def decode_binary(blob: bytes) -> Tuple[Dict[str, Any], np.ndarray]:
    """Inverse of to_binary(); the reference decoder for Python clients and tests."""
    (header_len,) = struct.unpack_from("<I", blob, 0)
    header = json.loads(bytes(blob[4 : 4 + header_len]).decode("utf-8"))
    samples = np.frombuffer(blob, dtype=DENSE_DTYPE, offset=4 + header_len, count=int(header["n"]))
    return header, samples
