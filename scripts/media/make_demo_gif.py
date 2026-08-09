"""Render the README demo GIF: a tour of examples running with no instrument attached.

Nothing here is hand-typed. Each segment runs a real example as a subprocess and
renders the first N lines of what it actually printed, so the GIF cannot drift
from what the examples really do.

Run from the repo root:  python scripts/media/make_demo_gif.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W = 880
BG = (13, 17, 23)
CHROME = (22, 27, 34)
BORDER = (48, 54, 61)
FG = (201, 209, 217)
COMMENT = (110, 130, 148)
OUT = (126, 231, 135)
PROMPT = (88, 166, 255)
DOT_R, DOT_Y, DOT_G = (255, 95, 86), (255, 189, 46), (39, 201, 63)

FONT_DIR = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEST = REPO_ROOT / "docs" / "images" / "mock-demo.gif"
SIZE_BUDGET_KB = 1536


def mono(size):
    for n in ("consola.ttf", "cour.ttf", "DejaVuSansMono.ttf"):
        p = FONT_DIR / n
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except OSError:
                pass
    return ImageFont.load_default()


F = mono(16)
FB = mono(15)
LH = 24  # line height
X0, Y0 = 26, 74  # text origin
GAP = 6  # between the command line and the output block
BOTTOM_PAD = 30
RIGHT_MARGIN = 16
ELLIPSIS = "..."

# (example path relative to the repo root, how many leading stdout lines to show)
#
# The second value is a TRUNCATION, never a filter: what is rendered is always
# lines[0:max_lines] of a real run. Showing a beginning is honest; assembling
# non-adjacent lines while presenting them as a terminal session is not.
#
# basic_usage.py stops at 11 deliberately. Line 19 of its output is
# "Frequency: 0.001 MHz" and line 20 is "Vpp: 2.000 V" -- the mock's fixed
# :MEASure constants, which do not track the 3.3 Vpp square wave the example
# just configured. Anything above 17 puts a contradictory number on screen.
TOUR = [
    ("examples/basic_usage.py", 11),
    ("examples/math_channels.py", 4),
    ("examples/measurement_badges_example.py", 6),
    ("examples/screen_capture_example.py", 1),
]


def run_example(rel_path: str) -> list[str]:
    """Run one example in a scratch cwd and return the lines it printed."""
    script = REPO_ROOT / rel_path
    env = {**os.environ, "MPLBACKEND": "Agg", "PYTHONIOENCODING": "utf-8"}
    with tempfile.TemporaryDirectory() as scratch:
        proc = subprocess.run([sys.executable, str(script)], cwd=scratch, capture_output=True, text=True, timeout=120, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"{rel_path} exited {proc.returncode} -- refusing to render a GIF of a broken example.\n--- stderr ---\n{proc.stderr}")
    return proc.stdout.splitlines()


def build_segments() -> list[dict]:
    segments = []
    for rel_path, max_lines in TOUR:
        lines = run_example(rel_path)
        segments.append({"command": f"python {rel_path}", "lines": lines[:max_lines], "truncated": len(lines) > max_lines})
    return segments


def assert_fits(segments: list[dict]) -> None:
    """Refuse to render text that would be clipped by the canvas edge."""
    limit = W - X0 - RIGHT_MARGIN
    for seg in segments:
        for text in [f"$ {seg['command']}", *seg["lines"]]:
            width = F.getlength(text)
            if width > limit:
                raise RuntimeError(f"line would be clipped ({width:.0f}px > {limit}px), widen the canvas or shorten the output: {text!r}")


def canvas_height(segments: list[dict]) -> int:
    tallest = max(len(s["lines"]) + (1 if s["truncated"] else 0) for s in segments)
    return Y0 + LH + GAP + LH * tallest + BOTTOM_PAD


def base_frame(height: int):
    img = Image.new("RGB", (W, height), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 44], fill=CHROME)
    d.line([(0, 44), (W, 44)], fill=BORDER)
    for i, c in enumerate((DOT_R, DOT_Y, DOT_G)):
        d.ellipse([20 + i * 22, 16, 32 + i * 22, 28], fill=c)
    title = "python  —  no instrument attached"  # em dash, as in the original
    d.text(((W - d.textlength(title, font=FB)) / 2, 15), title, font=FB, fill=(125, 137, 150))
    return img


def draw_state(height: int, command: str, out_lines: list[str], ellipsis: bool = False, cursor: bool = True):
    img = base_frame(height)
    d = ImageDraw.Draw(img)
    y = Y0
    d.text((X0, y), "$ ", font=F, fill=PROMPT)
    d.text((X0 + F.getlength("$ "), y), command, font=F, fill=FG)
    y += LH + GAP
    for ln in out_lines:
        d.text((X0, y), ln, font=F, fill=OUT)
        y += LH
    if ellipsis:
        d.text((X0, y), ELLIPSIS, font=F, fill=COMMENT)
        y += LH
    if cursor:
        d.rectangle([X0, y + 4, X0 + 9, y + 18], fill=PROMPT)
    return img


def main():
    segments = build_segments()
    assert_fits(segments)
    height = canvas_height(segments)

    frames, durations = [], []
    for seg in segments:
        frames.append(draw_state(height, seg["command"], []))
        durations.append(500)
        for i in range(1, len(seg["lines"]) + 1):
            frames.append(draw_state(height, seg["command"], seg["lines"][:i]))
            durations.append(260)
        if seg["truncated"]:
            frames.append(draw_state(height, seg["command"], seg["lines"], ellipsis=True))
            durations.append(260)
        frames.append(draw_state(height, seg["command"], seg["lines"], ellipsis=seg["truncated"], cursor=False))
        durations.append(1800)

    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    DEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEST.with_name(DEST.stem + ".tmp.gif")
    try:
        pal[0].save(tmp, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True, disposal=2)
        size_kb = tmp.stat().st_size / 1024
        if size_kb > SIZE_BUDGET_KB:
            raise RuntimeError(f"GIF is {size_kb:.0f} KB, over the {SIZE_BUDGET_KB} KB budget -- shorten holds or reduce palette depth")
        os.replace(tmp, DEST)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    print(f"wrote {DEST} ({size_kb:.0f} KB, {len(frames)} frames, {W}x{height})")
    for seg in segments:
        print(f"  {seg['command']}: {len(seg['lines'])} lines{' (truncated)' if seg['truncated'] else ''}")


if __name__ == "__main__":
    main()
