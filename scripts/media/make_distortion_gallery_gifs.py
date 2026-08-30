"""Render one small looping GIF per harmonic-distortion demo, for the README gallery.

A parallel, sibling gallery to make_clipping_gallery_gifs.py -- same relationship
to make_signal_gallery_gifs.py's per-kind one and make_superposition_gallery_gifs.py's
combo one: where those show a `scpi_control.signal_synth` kind (or a sum of
kinds) on its own, this one shows what `SignalSpec.distortion_h2`/
`distortion_h3` add -- a kind-agnostic Chebyshev-waveshaping harmonic-coloration
impairment applied to the base signal, same as documented on
SignalSpec.distortion_h2/distortion_h3. Every frame is still a live
rolling-buffer capture built from a real `signal_synth.stream()` generator,
plotted with the report generator's own `PlotStyle`, so nothing here is
hand-drawn.

Like make_clipping_gallery_gifs.py (and unlike make_superposition_gallery_gifs.py),
each demo here is a single `SignalSpec` (distortion is not a multi-component
feature), so this script streams it exactly the way make_signal_gallery_gifs.py's
build_kind() and make_clipping_gallery_gifs.py's build_demo() do -- one
`stream()` generator per entry.

Each animation is the same classic scrolling-scope loop as the other galleries:
a fixed-length sample buffer rolls left by one `stream()` chunk per frame,
against a FIXED x/y axis. For a "seam_checked": True entry, the spec's own
frequency must divide the total time advanced across all frames (n_frames *
chunk_size samples) into a whole number of cycles, exactly like the per-kind
and clipping galleries' requirement -- harmonic distortion via Chebyshev
waveshaping is a memoryless, per-sample nonlinearity (T_2(u)=2u**2-1 for
2nd/even, T_3(u)=4u**3-3u for 3rd/odd), so it does not change the signal's
period and does not break an otherwise-seamless loop. `main()` verifies this
numerically and refuses to write a GIF (RuntimeError) if the wrap-around jump
exceeds a tight tolerance.

Resolves its own repo root from __file__, so it can be run from anywhere:
  python scripts/media/make_distortion_gallery_gifs.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np

# Sibling-module import: make_signal_gallery_gifs.py already has the render
# pipeline (frame drawing, seamless-loop check, palettized GIF writing) this
# script needs unchanged, so it is imported rather than copy-pasted. Both
# scripts live directly in scripts/media/ with no package __init__.py, so the
# directory is put on sys.path explicitly rather than relying on the
# interpreter having added it only because this file happened to be the one
# invoked directly.
_MEDIA_DIR = Path(__file__).resolve().parent
if str(_MEDIA_DIR) not in sys.path:
    sys.path.insert(0, str(_MEDIA_DIR))

from make_signal_gallery_gifs import DEST_DIR, _check_seamless, _prime_buffer, _write_gif, render_frame  # noqa: E402

# One entry per harmonic-distortion demo. Kept as a plain literal list of
# dicts (no loops, no computed fields, no SignalSpec(...) calls) so
# tests/test_media_tour.py can parse it with ast.literal_eval without
# importing this module (and therefore without needing Pillow) -- mirroring
# make_signal_gallery_gifs.py's KINDS, make_superposition_gallery_gifs.py's
# COMBOS, and make_clipping_gallery_gifs.py's DEMOS. Named DEMOS -- the same
# name make_clipping_gallery_gifs.py uses -- since the two never coexist in
# the same module and tests/test_media_tour.py always parses it by explicit
# path, not by import.
#
# Both entries share the same base sine (1 kHz, amplitude=1.0, seed=42) as the
# two demonstrated FORMS of the impairment (pure 2nd-harmonic vs. pure
# 3rd-harmonic), for a direct visual comparison -- only which distortion field
# is nonzero differs. sample_rate/chunk_size/window_samples/n_frames are the
# same as the per-kind and clipping galleries' own "sine" entry: total advance
# = 30*4 = 120 samples = 120/120000 = 1 ms = exactly one 1 kHz period.
# Harmonic distortion is a memoryless per-sample nonlinearity applied on top
# of that sine, so it does not change the period and the loop stays seamless
# -- verified empirically (`main()`'s _check_seamless call) rather than merely
# assumed.
#
# ylim: with amplitude=1.0 and distortion_h2/h3=0.35, the worst-case sample
# reaches +-1.35 V (verified empirically -- synthesize() on both entries peaks
# at exactly 1.35 V, the h2 demo asymmetrically at -0.707/+1.35 V, the h3 demo
# symmetrically at +-1.35 V), so (-1.6, 1.6) gives comfortable headroom above
# that actual peak, the same way the clipping gallery's (-1.2, 1.2) sits above
# its own 1.0 V clip_level.
# No type annotation on this assignment, for the same ast.Assign-only reason
# as KINDS/COMBOS/DEMOS.
DEMOS = [
    {
        "name": "second_harmonic",
        "spec": {"kind": "sine", "frequency": 1000.0, "amplitude": 1.0, "offset": 0.0, "distortion_h2": 0.35, "seed": 42},
        "sample_rate": 120000.0,
        "chunk_size": 4,
        "window_samples": 480,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.6, 1.6),
        "seam_checked": True,
    },
    {
        "name": "third_harmonic",
        "spec": {"kind": "sine", "frequency": 1000.0, "amplitude": 1.0, "offset": 0.0, "distortion_h3": 0.35, "seed": 42},
        "sample_rate": 120000.0,
        "chunk_size": 4,
        "window_samples": 480,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.6, 1.6),
        "seam_checked": True,
    },
]


def _title_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """A copy of `entry` with a "kind" field, for reusing render_frame/_check_seamless.

    Both helpers were written for KINDS, where every entry has a top-level
    "kind" and uses it as a frame title / in an error message. A DEMOS entry
    keeps "kind" nested inside "spec" instead (see the module docstring), so
    this substitutes a readable title derived from "name" -- the same
    technique make_superposition_gallery_gifs.py's and
    make_clipping_gallery_gifs.py's _title_entry use.
    """
    return {**entry, "kind": entry["name"].replace("_", " ")}


def build_demo(entry: Dict[str, Any], style) -> tuple[list, np.ndarray, np.ndarray]:
    """Stream `entry`'s single SignalSpec and render its frames.

    Returns (frames, first_frame_buffer, post_loop_buffer) -- the two buffers
    are the raw voltage arrays (not images), for the seamless-loop check,
    exactly like make_signal_gallery_gifs.build_kind() and
    make_clipping_gallery_gifs.build_demo().
    """
    # Local import: keeps this module importable (e.g. by tooling that just
    # wants DEMOS) without requiring scpi_control's own import chain to have
    # already succeeded, mirroring build_kind()'s identical local import.
    from scpi_control.signal_synth import SignalSpec, stream

    sample_rate = entry["sample_rate"]
    chunk_size = entry["chunk_size"]
    window_samples = entry["window_samples"]
    n_frames = entry["n_frames"]
    title_entry = _title_entry(entry)

    spec = SignalSpec(**entry["spec"])
    gen = stream(spec, sample_rate=sample_rate, chunk_size=chunk_size, start_time=0.0)
    buffer = _prime_buffer(gen, window_samples)
    first_buffer = buffer.copy()
    t_ms = np.arange(window_samples) / sample_rate * 1e3

    frames = []
    for _ in range(n_frames):
        frames.append(render_frame(t_ms, buffer, title_entry, style))
        chunk = next(gen)
        buffer = np.concatenate([buffer[chunk.size :], chunk])

    return frames, first_buffer, buffer


def main() -> None:
    # Local import for the same reason as build_demo's.
    from scpi_control.report_generator.models.plot_style import PlotStyle

    style = PlotStyle()
    if not DEMOS:
        raise RuntimeError("DEMOS is empty -- nothing to render")

    for entry in DEMOS:
        frames, first_buffer, post_loop_buffer = build_demo(entry, style)
        seam_note = ""
        if entry["seam_checked"]:
            max_diff = _check_seamless(_title_entry(entry), first_buffer, post_loop_buffer)
            seam_note = f", seam {max_diff:.2e} V"

        dest = DEST_DIR / f"distortion-{entry['name']}.gif"
        durations = [entry["frame_ms"]] * len(frames)
        size_kb = _write_gif(dest, frames, durations)
        w, h = frames[0].size
        print(f"wrote {dest} ({size_kb:.0f} KB, {len(frames)} frames, {w}x{h}{seam_note})")


if __name__ == "__main__":
    sys.exit(main())
