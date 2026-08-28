"""Render one small looping GIF per synthetic signal kind, for the README gallery.

Nothing here is hand-drawn: every frame is a live rolling-buffer capture, fed
chunk-by-chunk from `scpi_control.signal_synth.stream()` -- the same generator
that drives MockConnection -- and plotted with the report generator's own
`PlotStyle`, so the trace shapes and colours cannot drift from what the mock
scope and the reports actually show.

Each animation is a classic scrolling-scope loop: a fixed-length sample buffer
rolls left by one `stream()` chunk per frame, against a FIXED x/y axis (no
autoscale jitter). Frame count and chunk size are chosen per kind so the total
time advanced across all frames is an exact integer number of that signal's
own period (or, for "chirp", its sweep_time) -- so the last frame flows back
into the first with no visible phase jump when the GIF loops (`loop=0`).
`main()` verifies this numerically for every kind where it applies, and
refuses to write a GIF (RuntimeError) if a "seamless" kind's wrap-around jump
exceeds a tight tolerance. "dc" and "noise" have no cycle to align to and are
exempt -- see SEAMLESS_TOLERANCE_V and the KINDS table below.

Resolves its own repo root from __file__, so it can be run from anywhere:
  python scripts/media/make_signal_gallery_gifs.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
DEST_DIR = REPO_ROOT / "docs" / "images"
SIZE_BUDGET_KB = 450

FIG_SIZE_IN = (3.4, 1.9)  # inches
DPI = 100  # -> 340x190 px frames
PALETTE_COLORS = 48  # a single line + grid on white needs far fewer colours than the code-editor GIFs

# How close the buffer just after the LAST frame's chunk must land to the
# FIRST frame's buffer, in volts, for a "seamless" kind (see KINDS below).
# Tight: everything at play here (SignalSpec generators, t0 bookkeeping in
# stream()/synthesize()) is deterministic float64 arithmetic with no jitter
# or impairments enabled, so a genuinely aligned loop reproduces to within a
# few ULPs, not merely "close". A few micro-volts already means the frame
# math is wrong, not that the tolerance was too strict.
SEAMLESS_TOLERANCE_V = 1e-6

# One entry per scpi_control.signal_synth._GENERATORS kind. Kept as a plain
# literal list of dicts (no loops, no computed fields, no SignalSpec(...)
# calls) so tests/test_media_tour.py can parse it with ast.literal_eval
# without importing this module (and therefore without needing Pillow).
#
# sample_rate / chunk_size / window_samples / n_frames are chosen together so
# that, for every "seam_checked": True kind, n_frames * chunk_size samples is
# exactly one period (one sweep_time for "chirp") at that kind's sample_rate
# -- see the module docstring. window_samples is always an exact multiple of
# chunk_size, so priming the rolling buffer from whole stream() chunks lands
# on an exact window with no partial-chunk slicing.
# No type annotation on this assignment (unlike the rest of this file) so
# tests/test_media_tour.py's ast-based `_table()` helper -- which only
# recognizes a plain `ast.Assign`, matching make_demo_gif.py's TOUR and
# test_examples_smoke.py's EXECUTE -- can find and literal_eval it.
KINDS = [
    {
        "kind": "sine",
        "spec": {"frequency": 1000.0, "amplitude": 1.0, "offset": 0.0, "seed": 42},
        "sample_rate": 120000.0,
        "chunk_size": 4,
        "window_samples": 480,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.4, 1.4),
        "seam_checked": True,
    },
    {
        "kind": "square",
        "spec": {"frequency": 500.0, "amplitude": 1.0, "offset": 0.0, "seed": 42},
        "sample_rate": 60000.0,
        "chunk_size": 4,
        "window_samples": 360,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.4, 1.4),
        "seam_checked": True,
    },
    {
        "kind": "triangle",
        "spec": {"frequency": 800.0, "amplitude": 1.0, "offset": 0.0, "seed": 42},
        "sample_rate": 96000.0,
        "chunk_size": 4,
        "window_samples": 480,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.4, 1.4),
        "seam_checked": True,
    },
    {
        "kind": "ramp",
        "spec": {"frequency": 300.0, "amplitude": 1.0, "offset": 0.0, "seed": 42},
        "sample_rate": 36000.0,
        "chunk_size": 4,
        "window_samples": 360,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.4, 1.4),
        "seam_checked": True,
    },
    {
        "kind": "dc",
        # amplitude is intentionally omitted: SignalSpec.amplitude is ignored
        # for "dc" (it outputs exactly `offset`). noise_rms is a small
        # additive impairment -- SignalSpec's own docstring notes it applies
        # to any kind -- just enough that the trace reads as "alive" rather
        # than a dead flat line, while still being an honest DC level.
        "spec": {"offset": 2.5, "noise_rms": 0.03, "seed": 42},
        "sample_rate": 20000.0,
        "chunk_size": 6,
        "window_samples": 120,
        "n_frames": 30,
        "frame_ms": 70,
        "ylim": (2.2, 2.8),
        "seam_checked": False,  # no cycle structure to align to; the noise re-seeds every chunk anyway
    },
    {
        "kind": "noise",
        # amplitude IS the standard deviation for "noise" (SignalSpec docstring).
        "spec": {"amplitude": 0.6, "offset": 0.0, "seed": 42},
        "sample_rate": 50000.0,
        "chunk_size": 10,
        "window_samples": 250,
        "n_frames": 30,
        "frame_ms": 70,
        "ylim": (-2.0, 2.0),
        "seam_checked": False,  # no cycle structure to align to
    },
    {
        "kind": "multitone",
        "spec": {"frequency": 600.0, "amplitude": 0.8, "offset": 0.0, "harmonics": (0.3, 0.15), "seed": 42},
        "sample_rate": 72000.0,
        "chunk_size": 4,
        "window_samples": 240,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.5, 1.5),
        "seam_checked": True,
    },
    {
        "kind": "exponential",
        # duty=0.5 and 5*tau == duty*period, so each half-cycle fully settles
        # -- a clean RC charge/discharge shape rather than a fainter partial one.
        "spec": {"frequency": 250.0, "amplitude": 1.0, "offset": 0.0, "duty": 0.5, "tau": 4e-4, "seed": 42},
        "sample_rate": 30000.0,
        "chunk_size": 4,
        "window_samples": 360,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.4, 1.4),
        "seam_checked": True,
    },
    {
        "kind": "pulse",
        # pulse_width/edge_time left at SignalSpec's own defaults, which are
        # already sized for a 1 kHz fundamental (SignalSpec docstring).
        "spec": {"frequency": 1000.0, "amplitude": 1.0, "offset": 0.0, "seed": 42},
        "sample_rate": 120000.0,
        "chunk_size": 4,
        "window_samples": 360,
        "n_frames": 30,
        "frame_ms": 45,
        "ylim": (-1.4, 1.4),
        "seam_checked": True,
    },
    {
        "kind": "chirp",
        # window_samples spans exactly one whole sweep_time, and the total
        # time advanced across all frames is exactly one more sweep_time, so
        # "chirp" retraces at that same boundary (SignalSpec._chirp). That
        # alone only guarantees the FREQUENCY profile repeats and the phase
        # stays continuous (no step) -- it does NOT by itself make the retraced
        # samples bit-identical to the first sweep's, because _chirp_phase
        # accumulates sweep_time*(frequency+end_frequency)/2 radians/(2*pi) of
        # phase per sweep, and that must itself be a whole number of cycles for
        # the retrace to land back on the same phase rather than pi out of
        # phase. Verified empirically: end_frequency=5000 gave a full-amplitude
        # sign-flipped wrap (a 2 V jump at seam_checked time); 500+4500 Hz over
        # a 10 ms sweep gives 0.01*(500+4500)/2 = 25 whole cycles, which closes
        # the loop to the same few-ULP precision as the other kinds below.
        "spec": {"frequency": 500.0, "amplitude": 1.0, "offset": 0.0, "end_frequency": 4500.0, "sweep_time": 0.01, "sweep_log": False, "seed": 42},
        "sample_rate": 40000.0,
        "chunk_size": 10,
        "window_samples": 400,
        "n_frames": 40,
        "frame_ms": 45,
        "ylim": (-1.4, 1.4),
        "seam_checked": True,
    },
]


def _prime_buffer(gen, window_samples: int) -> np.ndarray:
    """Fill the rolling buffer with whole stream() chunks before rendering starts."""
    chunks = [next(gen)]
    total = chunks[0].size
    while total < window_samples:
        chunk = next(gen)
        chunks.append(chunk)
        total += chunk.size
    buffer = np.concatenate(chunks)
    if buffer.size != window_samples:
        raise RuntimeError(f"buffer priming landed on {buffer.size} samples, expected exactly {window_samples} -- window_samples must be a multiple of chunk_size")
    return buffer


def render_frame(t_ms: np.ndarray, voltage: np.ndarray, entry: Dict[str, Any], style) -> Image.Image:
    """Render one rolling-buffer frame to an in-memory RGB image."""
    fig = Figure(figsize=FIG_SIZE_IN, dpi=DPI)
    fig.patch.set_facecolor(style.background_color)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)

    ax.plot(t_ms, voltage, color=style.waveform_color, linewidth=style.waveform_linewidth)
    style.apply_to_axes(ax)

    ax.set_xlim(t_ms[0], t_ms[-1])
    ax.set_ylim(*entry["ylim"])
    ax.set_xlabel("Time (ms)", fontsize=style.label_fontsize)
    ax.set_ylabel("Voltage (V)", fontsize=style.label_fontsize)
    ax.set_title(entry["kind"], fontsize=style.title_fontsize)
    fig.tight_layout()

    canvas.draw()
    w, h = canvas.get_width_height()
    img = Image.frombuffer("RGBA", (w, h), canvas.buffer_rgba(), "raw", "RGBA", 0, 1)
    return img.convert("RGB")


def build_kind(entry: Dict[str, Any], style) -> tuple[list[Image.Image], np.ndarray, np.ndarray]:
    """Stream `entry`'s signal and render its frames.

    Returns (frames, first_frame_buffer, post_loop_buffer) -- the two buffers
    are the raw voltage arrays (not images), for the seamless-loop check.
    """
    # Local import: keeps this module importable (e.g. by tooling that just
    # wants KINDS) without requiring scpi_control's own import chain to have
    # already succeeded, mirroring make_annotation_gif.py's lazy imports.
    from scpi_control.signal_synth import SignalSpec, stream

    spec = SignalSpec(kind=entry["kind"], **entry["spec"])
    sample_rate = entry["sample_rate"]
    chunk_size = entry["chunk_size"]
    window_samples = entry["window_samples"]
    n_frames = entry["n_frames"]

    gen = stream(spec, sample_rate=sample_rate, chunk_size=chunk_size, start_time=0.0)
    buffer = _prime_buffer(gen, window_samples)
    first_buffer = buffer.copy()
    t_ms = np.arange(window_samples) / sample_rate * 1e3

    frames = []
    for _ in range(n_frames):
        frames.append(render_frame(t_ms, buffer, entry, style))
        chunk = next(gen)
        buffer = np.concatenate([buffer[chunk.size :], chunk])

    return frames, first_buffer, buffer


def _check_seamless(entry: Dict[str, Any], first_buffer: np.ndarray, post_loop_buffer: np.ndarray) -> float:
    """Empirically verify the wrap-around jump, in volts. Raises if too large."""
    max_diff = float(np.max(np.abs(post_loop_buffer - first_buffer)))
    if max_diff > SEAMLESS_TOLERANCE_V:
        raise RuntimeError(
            f"{entry['kind']!r} is marked seam_checked but the buffer after "
            f"{entry['n_frames']} frames differs from the first frame by up to "
            f"{max_diff:.3e} V (tolerance {SEAMLESS_TOLERANCE_V:.0e} V) -- the "
            "loop would show a visible jump; check sample_rate/chunk_size/n_frames"
        )
    return max_diff


def _write_gif(dest: Path, frames: list[Image.Image], durations: list[int]) -> float:
    palettised = [f.convert("P", palette=Image.ADAPTIVE, colors=PALETTE_COLORS) for f in frames]
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".tmp.gif")
    try:
        palettised[0].save(tmp, save_all=True, append_images=palettised[1:], duration=durations, loop=0, optimize=True, disposal=2)
        size_kb = tmp.stat().st_size / 1024
        if size_kb > SIZE_BUDGET_KB:
            raise RuntimeError(f"{dest.name} is {size_kb:.0f} KB, over the {SIZE_BUDGET_KB} KB budget -- reduce frame count, dimensions, or palette depth")
        os.replace(tmp, dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return size_kb


def main() -> None:
    # Local import for the same reason as build_kind's.
    from scpi_control.report_generator.models.plot_style import PlotStyle

    style = PlotStyle()
    if not KINDS:
        raise RuntimeError("KINDS is empty -- nothing to render")

    for entry in KINDS:
        frames, first_buffer, post_loop_buffer = build_kind(entry, style)
        seam_note = ""
        if entry["seam_checked"]:
            max_diff = _check_seamless(entry, first_buffer, post_loop_buffer)
            seam_note = f", seam {max_diff:.2e} V"

        dest = DEST_DIR / f"signal-{entry['kind']}.gif"
        durations = [entry["frame_ms"]] * len(frames)
        size_kb = _write_gif(dest, frames, durations)
        w, h = frames[0].size
        print(f"wrote {dest} ({size_kb:.0f} KB, {len(frames)} frames, {w}x{h}{seam_note})")


if __name__ == "__main__":
    sys.exit(main())
