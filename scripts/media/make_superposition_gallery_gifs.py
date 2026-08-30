"""Render one small looping GIF per superposition example, for the README gallery.

A parallel, sibling gallery to make_signal_gallery_gifs.py's per-kind one: where
that script shows each `scpi_control.signal_synth` kind on its own, this one
shows what `SuperposedSignal` adds -- two or more independently-synthesized
`SignalSpec`s summed onto one channel (a tone riding on noise, two tones
beating, a spur on a square wave). Every frame is still a live rolling-buffer
capture built from real `signal_synth` generators, plotted with the report
generator's own `PlotStyle`, so nothing here is hand-drawn.

`signal_synth.stream()` itself only streams a single `SignalSpec`, not a
`SuperposedSignal` -- `synthesize_combined()`/`make_waveform_combined()` are
one-shot calls, not streaming ones. This script does not add that streaming
support to the library; instead it drives one independent `stream()`
generator per component (each with its own spec, impairments, and seed) and
sums the corresponding chunks together every frame. That is mathematically
identical to streaming a `SuperposedSignal`: `synthesize_combined()` already
sums independently-synthesized arrays with no state shared between
components, and chunk-by-chunk summation of independently-streamed chunks is
the same sum, just computed incrementally.

Each animation is the same classic scrolling-scope loop as the per-kind
gallery: a fixed-length sample buffer rolls left by one summed chunk per
frame, against a FIXED x/y axis. For a "seam_checked": True entry, every
component's own frequency must divide the total time advanced across all
frames (n_frames * chunk_size samples) into a whole number of cycles -- the
same requirement make_signal_gallery_gifs.py's docstring works out for
"chirp", just applied to every component independently rather than to a
single kind -- so the last frame flows back into the first with no visible
phase jump. `run_gallery()` (in gallery_common.py) verifies this numerically
and refuses to write a GIF (RuntimeError) if the wrap-around jump exceeds a
tight tolerance. An entry with a non-periodic component (e.g. "noise", which
has no cycle to align to and re-seeds every chunk anyway) is marked
"seam_checked": False instead, the same way the per-kind gallery treats "dc"
and "noise".

Resolves its own repo root from __file__, so it can be run from anywhere:
  python scripts/media/make_superposition_gallery_gifs.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np

# Sibling-module import: gallery_common.py has the render pipeline (frame
# drawing, seamless-loop check, palettized GIF writing, main() body) this
# script needs unchanged, so it is imported rather than copy-pasted. Both
# scripts live directly in scripts/media/ with no package __init__.py, so the
# directory is put on sys.path explicitly rather than relying on the
# interpreter having added it only because this file happened to be the one
# invoked directly.
_MEDIA_DIR = Path(__file__).resolve().parent
if str(_MEDIA_DIR) not in sys.path:
    sys.path.insert(0, str(_MEDIA_DIR))

from gallery_common import _prime_buffer, render_frame, run_gallery, title_entry  # noqa: E402

# One entry per superposition example. Kept as a plain literal list of dicts
# (no loops, no computed fields, no SignalSpec(...)/SuperposedSignal(...)
# calls) so tests/test_media_tour.py can parse it with ast.literal_eval
# without importing this module (and therefore without needing Pillow) --
# mirroring make_signal_gallery_gifs.py's KINDS. Named COMBOS, not KINDS, so
# the existing per-kind tests (which target make_signal_gallery_gifs.py's
# KINDS specifically, by module path) can never be pointed at this table by
# accident.
#
# Every "components" entry is a per-component spec-param dict in the same
# shape as KINDS' own "spec" dicts (kind + only the params that need
# overriding). All components in one entry share that entry's sample_rate /
# chunk_size, since they are streamed and summed chunk-for-chunk (see the
# module docstring). window_samples is always an exact multiple of
# chunk_size, and for "seam_checked": True entries, n_frames * chunk_size
# samples is an exact common multiple of every periodic component's period.
# No type annotation on this assignment, for the same ast.Assign-only reason
# as KINDS.
COMBOS = [
    {
        "name": "sine_plus_noise",
        "components": [
            {"kind": "sine", "frequency": 1000.0, "amplitude": 1.0, "offset": 0.0, "seed": 42},
            # amplitude IS the standard deviation for "noise" (SignalSpec
            # docstring); 0.2 keeps the sine shape clearly visible underneath.
            {"kind": "noise", "amplitude": 0.2, "offset": 0.0, "seed": 43},
        ],
        "sample_rate": 120000.0,
        "chunk_size": 4,
        "window_samples": 480,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.6, 1.6),
        "seam_checked": False,  # the noise component has no cycle structure to align to; it re-seeds every chunk anyway
    },
    {
        "name": "two_tone_beat",
        # 1000 Hz and 1050 Hz differ by 50 Hz, so their sum's envelope beats
        # at 50 Hz -- a full beat cycle every 1/50 = 0.02 s = 20 ms. Over that
        # 20 ms, the 1000 Hz component completes exactly 20 cycles and the
        # 1050 Hz component exactly 21 -- both whole numbers -- so a total
        # elapsed time of 20 ms (or any whole multiple of it) closes the loop
        # for both components simultaneously.
        "components": [
            {"kind": "sine", "frequency": 1000.0, "amplitude": 0.6, "offset": 0.0, "seed": 42},
            {"kind": "sine", "frequency": 1050.0, "amplitude": 0.6, "offset": 0.0, "seed": 43},
        ],
        # sample_rate=48000, chunk_size=32, n_frames=30 -> total advance =
        # 960 samples = 960/48000 = 0.02 s = one full 20 ms beat cycle.
        # window_samples=1920 = 2 beat cycles, an exact multiple of
        # chunk_size (60 chunks), so the window shows the whole beat envelope
        # rather than a mid-beat crop.
        "sample_rate": 48000.0,
        "chunk_size": 32,
        "window_samples": 1920,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.6, 1.6),
        "seam_checked": True,
    },
    {
        "name": "square_plus_spur",
        # 2500 Hz is exactly 5x the square wave's 500 Hz, so one 500 Hz
        # period (2 ms) contains exactly 5 whole spur cycles -- the spur
        # closes its own loop at the same boundary the square wave does.
        "components": [
            {"kind": "square", "frequency": 500.0, "amplitude": 1.0, "offset": 0.0, "seed": 42},
            {"kind": "sine", "frequency": 2500.0, "amplitude": 0.2, "offset": 0.0, "seed": 43},
        ],
        # Same sample_rate/chunk_size/window_samples/n_frames as the per-kind
        # gallery's own "square" entry: total advance = 4*30 = 120 samples =
        # 120/60000 = 0.002 s = exactly one 500 Hz period (and, per above,
        # exactly 5 spur periods too).
        "sample_rate": 60000.0,
        "chunk_size": 4,
        "window_samples": 360,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.5, 1.5),
        "seam_checked": True,
    },
]


def build_combo(entry: Dict[str, Any], style) -> tuple[list, np.ndarray, np.ndarray]:
    """Stream `entry`'s components in parallel, sum them, and render frames.

    Returns (frames, first_frame_buffer, post_loop_buffer) -- the two buffers
    are the raw summed voltage arrays (not images), for the seamless-loop
    check, exactly like make_signal_gallery_gifs.build_kind().
    """
    # Local import: keeps this module importable (e.g. by tooling that just
    # wants COMBOS) without requiring scpi_control's own import chain to have
    # already succeeded, mirroring build_kind()'s identical local import.
    from scpi_control.signal_synth import SignalSpec, stream

    sample_rate = entry["sample_rate"]
    chunk_size = entry["chunk_size"]
    window_samples = entry["window_samples"]
    n_frames = entry["n_frames"]
    entry_title = title_entry(entry)

    specs = [SignalSpec(**component) for component in entry["components"]]
    gens = [stream(spec, sample_rate=sample_rate, chunk_size=chunk_size, start_time=0.0) for spec in specs]

    buffer = np.sum([_prime_buffer(gen, window_samples) for gen in gens], axis=0)
    first_buffer = buffer.copy()
    t_ms = np.arange(window_samples) / sample_rate * 1e3

    frames = []
    for _ in range(n_frames):
        frames.append(render_frame(t_ms, buffer, entry_title, style))
        chunk = np.sum([next(gen) for gen in gens], axis=0)
        buffer = np.concatenate([buffer[chunk.size :], chunk])

    return frames, first_buffer, buffer


def main() -> None:
    run_gallery(COMBOS, build_combo, "superposition")


if __name__ == "__main__":
    sys.exit(main())
