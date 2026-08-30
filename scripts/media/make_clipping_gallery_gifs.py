"""Render one small looping GIF per clipping/saturation demo, for the README gallery.

A parallel, sibling gallery to make_signal_gallery_gifs.py's per-kind one and
make_superposition_gallery_gifs.py's combo one: where those show a
`scpi_control.signal_synth` kind (or a sum of kinds) on its own, this one
shows what `SignalSpec.clip_level`/`clip_softness` add -- a symmetric
clipping/saturation impairment applied to the base signal, kind-agnostic and
applied LAST (after drift/glitches/noise), same as documented on
SignalSpec.clip_level. Every frame is still a live rolling-buffer capture
built from a real `signal_synth.stream()` generator, plotted with the report
generator's own `PlotStyle`, so nothing here is hand-drawn.

Unlike make_superposition_gallery_gifs.py, each demo here is a single
`SignalSpec` (clipping is not a multi-component feature), so this script
uses gallery_common.build_single_spec_demo() -- one `stream()` generator per
entry, the same way make_signal_gallery_gifs.py's build_kind() streams a
KINDS entry -- rather than the parallel-multi-stream technique the
superposition script needed.

Each animation is the same classic scrolling-scope loop as the other two
galleries: a fixed-length sample buffer rolls left by one `stream()` chunk
per frame, against a FIXED x/y axis. For a "seam_checked": True entry, the
spec's own frequency must divide the total time advanced across all frames
(n_frames * chunk_size samples) into a whole number of cycles, exactly like
the per-kind gallery's requirement -- clipping is a memoryless, per-sample
nonlinearity, so it does not change the signal's period and does not break
an otherwise-seamless loop. `run_gallery()` (in gallery_common.py) verifies
this numerically and refuses to write a GIF (RuntimeError) if the
wrap-around jump exceeds a tight tolerance.

Resolves its own repo root from __file__, so it can be run from anywhere:
  python scripts/media/make_clipping_gallery_gifs.py
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

# One entry per clipping/saturation demo. Kept as a plain literal list of
# dicts (no loops, no computed fields, no SignalSpec(...) calls) so
# tests/test_media_tour.py can parse it with ast.literal_eval without
# importing this module (and therefore without needing Pillow) -- mirroring
# make_signal_gallery_gifs.py's KINDS and make_superposition_gallery_gifs.py's
# COMBOS. Named DEMOS -- a third, distinct name from both of those -- so the
# existing per-kind/per-combo tests (which target those two tables by exact
# name) can never be pointed at this table by accident.
#
# Both entries share the same base sine (1 kHz, amplitude=1.5, clip_level=1.0)
# as the two demonstrated FORMS of the impairment (hard vs. fully soft), for a
# direct visual comparison -- only clip_softness differs. sample_rate/
# chunk_size/window_samples/n_frames are the same as the per-kind gallery's
# own "sine" entry: total advance = 30*4 = 120 samples = 120/120000 = 1 ms =
# exactly one 1 kHz period. Clipping is a memoryless per-sample nonlinearity
# applied on top of that sine, so it does not change the period and the loop
# stays seamless -- verified empirically (run_gallery()'s seam check) rather
# than merely assumed.
# No type annotation on this assignment, for the same ast.Assign-only reason
# as KINDS/COMBOS.
DEMOS = [
    {
        "name": "hard_clip",
        "spec": {"kind": "sine", "frequency": 1000.0, "amplitude": 1.5, "offset": 0.0, "clip_level": 1.0, "clip_softness": 0.0, "seed": 42},
        "sample_rate": 120000.0,
        "chunk_size": 4,
        "window_samples": 480,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.2, 1.2),
        "seam_checked": True,
    },
    {
        "name": "soft_saturation",
        "spec": {"kind": "sine", "frequency": 1000.0, "amplitude": 1.5, "offset": 0.0, "clip_level": 1.0, "clip_softness": 1.0, "seed": 42},
        "sample_rate": 120000.0,
        "chunk_size": 4,
        "window_samples": 480,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.2, 1.2),
        "seam_checked": True,
    },
]


def main() -> None:
    run_gallery(DEMOS, build_single_spec_demo, "clipping")


if __name__ == "__main__":
    sys.exit(main())
