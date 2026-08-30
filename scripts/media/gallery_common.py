"""Shared rendering/writing primitives for the scripts/media/make_*_gallery_gifs.py scripts.

Four sibling scripts (make_signal_gallery_gifs.py, make_superposition_gallery_gifs.py,
make_clipping_gallery_gifs.py, make_distortion_gallery_gifs.py) each render a
gallery of small looping scrolling-scope GIFs for the README, built from live
`scpi_control.signal_synth.stream()` captures plotted with the report
generator's own `PlotStyle`. They share one frame-rendering/GIF-writing
pipeline, one seamless-loop verification routine, and one `main()` shape
(build every table entry, seam-check it, write it, print a summary line).
This module holds that shared code so it lives in exactly one place instead
of being copy-pasted across the four scripts.

This module is a library, not a runnable script: it has no `main()` and no
`if __name__ == "__main__":` block. Each gallery script still owns its own
table (KINDS/COMBOS/DEMOS) and its own per-table build function, since those
genuinely differ script to script -- see each script's module docstring for
what it contributes on top of this module.
"""

from __future__ import annotations

import os
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


def title_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """A copy of `entry` guaranteed to carry a "kind" field, for render_frame/_check_seamless.

    Both helpers were written for KINDS entries, where every entry already
    has exactly one top-level "kind" and uses it as a frame title / in an
    error message. This unifies the three near-identical `_title_entry()`
    helpers that used to live separately in make_superposition_gallery_gifs.py,
    make_clipping_gallery_gifs.py, and make_distortion_gallery_gifs.py: a
    COMBOS entry sums two or more kinds and a DEMOS entry keeps "kind" nested
    inside "spec", so neither has one top-level "kind" to use directly, and
    both substitute a readable title derived from "name" instead.

    A KINDS entry already has a top-level "kind" (it never needed a
    `_title_entry()` of its own), so it is returned unchanged -- this
    function is a safe pass-through for any entry shape, not just the ones
    that need the substitution.
    """
    if "kind" in entry:
        return entry
    return {**entry, "kind": entry["name"].replace("_", " ")}


def build_single_spec_demo(entry: Dict[str, Any], style) -> tuple[list, np.ndarray, np.ndarray]:
    """Stream `entry`'s single SignalSpec and render its frames.

    Shared by the clipping and distortion galleries (and any future gallery
    whose demo table is a single `SignalSpec` per entry, read from
    `entry["spec"]`, rather than a multi-component sum) -- each entry there
    is a single named impairment demo, not a multi-component signal, so this
    streams it exactly the way make_signal_gallery_gifs.py's build_kind()
    does: one `stream()` generator per entry.

    Returns (frames, first_frame_buffer, post_loop_buffer) -- the two buffers
    are the raw voltage arrays (not images), for the seamless-loop check,
    exactly like make_signal_gallery_gifs.build_kind().
    """
    # Local import: keeps this module importable (e.g. by tooling that just
    # wants a gallery's table) without requiring scpi_control's own import
    # chain to have already succeeded, mirroring build_kind()'s identical
    # local import.
    from scpi_control.signal_synth import SignalSpec, stream

    sample_rate = entry["sample_rate"]
    chunk_size = entry["chunk_size"]
    window_samples = entry["window_samples"]
    n_frames = entry["n_frames"]
    entry_title = title_entry(entry)

    spec = SignalSpec(**entry["spec"])
    gen = stream(spec, sample_rate=sample_rate, chunk_size=chunk_size, start_time=0.0)
    buffer = _prime_buffer(gen, window_samples)
    first_buffer = buffer.copy()
    t_ms = np.arange(window_samples) / sample_rate * 1e3

    frames = []
    for _ in range(n_frames):
        frames.append(render_frame(t_ms, buffer, entry_title, style))
        chunk = next(gen)
        buffer = np.concatenate([buffer[chunk.size :], chunk])

    return frames, first_buffer, buffer


def run_gallery(entries: list, build_fn, filename_prefix: str) -> None:
    """Shared `main()` body for all four make_*_gallery_gifs.py scripts.

    For each entry: calls `build_fn(entry, style)`, seam-checks the result
    when `entry["seam_checked"]`, writes the GIF to
    `DEST_DIR / f"{filename_prefix}-{slug}.gif"` (slug is `entry["name"]` if
    present, else `entry["kind"]`), and prints a one-line summary -- the
    identical shape every gallery script's own `main()` used to duplicate.
    """
    # Local import for the same reason as build_single_spec_demo's.
    from scpi_control.report_generator.models.plot_style import PlotStyle

    style = PlotStyle()
    if not entries:
        raise RuntimeError("entries is empty -- nothing to render")

    for entry in entries:
        frames, first_buffer, post_loop_buffer = build_fn(entry, style)
        seam_note = ""
        if entry["seam_checked"]:
            max_diff = _check_seamless(title_entry(entry), first_buffer, post_loop_buffer)
            seam_note = f", seam {max_diff:.2e} V"

        slug = entry.get("name") or entry.get("kind")
        dest = DEST_DIR / f"{filename_prefix}-{slug}.gif"
        durations = [entry["frame_ms"]] * len(frames)
        size_kb = _write_gif(dest, frames, durations)
        w, h = frames[0].size
        print(f"wrote {dest} ({size_kb:.0f} KB, {len(frames)} frames, {w}x{h}{seam_note})")
