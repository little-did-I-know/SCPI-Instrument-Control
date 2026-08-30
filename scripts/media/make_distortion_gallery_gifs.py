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
feature), so this script streams it exactly the way
gallery_common.build_single_spec_demo() does (the same helper
make_clipping_gallery_gifs.py uses) -- one `stream()` generator per entry.

Each animation is the same classic scrolling-scope loop as the other galleries:
a fixed-length sample buffer rolls left by one `stream()` chunk per frame,
against a FIXED x/y axis. For a "seam_checked": True entry, the spec's own
frequency must divide the total time advanced across all frames (n_frames *
chunk_size samples) into a whole number of cycles, exactly like the per-kind
and clipping galleries' requirement -- harmonic distortion via Chebyshev
waveshaping is a memoryless, per-sample nonlinearity (T_2(u)=2u**2-1 for
2nd/even, T_3(u)=4u**3-3u for 3rd/odd), so it does not change the signal's
period and does not break an otherwise-seamless loop. `run_gallery()` (in
gallery_common.py) verifies this numerically and refuses to write a GIF
(RuntimeError) if the wrap-around jump exceeds a tight tolerance.

Resolves its own repo root from __file__, so it can be run from anywhere:
  python scripts/media/make_distortion_gallery_gifs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Sibling-module import: gallery_common.py has the render pipeline (frame
# drawing, seamless-loop check, palettized GIF writing, main() body, and the
# single-SignalSpec build helper) this script needs unchanged, so it is
# imported rather than copy-pasted. Both scripts live directly in
# scripts/media/ with no package __init__.py, so the directory is put on
# sys.path explicitly rather than relying on the interpreter having added it
# only because this file happened to be the one invoked directly.
_MEDIA_DIR = Path(__file__).resolve().parent
if str(_MEDIA_DIR) not in sys.path:
    sys.path.insert(0, str(_MEDIA_DIR))

from gallery_common import build_single_spec_demo, run_gallery  # noqa: E402

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
# -- verified empirically (run_gallery()'s seam check) rather than merely
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


def main() -> None:
    run_gallery(DEMOS, build_single_spec_demo, "distortion")


if __name__ == "__main__":
    sys.exit(main())
