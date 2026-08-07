"""Render the README demo GIF: a terminal session driving the built-in mock scope.

The output text is not hand-written -- it is captured by actually running the
snippet, so the GIF cannot drift from what the library really prints.

Run from the repo root:  python make_demo_gif.py
"""

from __future__ import annotations

import io
import os
from contextlib import redirect_stdout
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 880, 636
BG = (13, 17, 23)
CHROME = (22, 27, 34)
BORDER = (48, 54, 61)
FG = (201, 209, 217)
COMMENT = (110, 130, 148)
KEYWORD = (255, 123, 114)
STRING = (165, 214, 255)
NUM = (247, 200, 115)
OUT = (126, 231, 135)
PROMPT = (88, 166, 255)
DOT_R, DOT_Y, DOT_G = (255, 95, 86), (255, 189, 46), (39, 201, 63)

FONT_DIR = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"


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

SNIPPET = """from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.signal_synth import SignalSpec

# A virtual scope probing a 3.3 V, 1 kHz clock
scope = Oscilloscope("mock", connection=MockConnection(
    "mock",
    channel_states={1: True},
    signals={1: SignalSpec(kind="square", frequency=1000.0,
                           amplitude=1.65, offset=1.65)},
    sample_rate=20e6, timebase=500e-6))
scope.connect()

wf = scope.get_waveform(channel=1)
print(f"{len(wf.time)} samples")
print(f"Vpp  {wf.voltage.max() - wf.voltage.min():.3f} V")
print(f"Freq {scope.measurement.measure_frequency(1):.2f} Hz")"""


def real_output() -> list[str]:
    """Actually run the snippet and capture what it prints."""
    from scpi_control.connection import MockConnection
    from scpi_control.oscilloscope import Oscilloscope
    from scpi_control.signal_synth import SignalSpec

    buf = io.StringIO()
    with redirect_stdout(buf):
        scope = Oscilloscope(
            "mock",
            connection=MockConnection("mock", channel_states={1: True}, signals={1: SignalSpec(kind="square", frequency=1000.0, amplitude=1.65, offset=1.65)}, sample_rate=20e6, timebase=500e-6),
        )
        scope.connect()
        wf = scope.get_waveform(channel=1)
        print(f"{len(wf.time)} samples")
        print(f"Vpp  {wf.voltage.max() - wf.voltage.min():.3f} V")
        print(f"Freq {scope.measurement.measure_frequency(1):.2f} Hz")
        scope.disconnect()
    return buf.getvalue().rstrip("\n").split("\n")


def colour_for(line: str):
    s = line.lstrip()
    if s.startswith("#"):
        return COMMENT
    if s.startswith(("from ", "import ")):
        return KEYWORD
    return FG


def base_frame():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 44], fill=CHROME)
    d.line([(0, 44), (W, 44)], fill=BORDER)
    for i, c in enumerate((DOT_R, DOT_Y, DOT_G)):
        d.ellipse([20 + i * 22, 16, 32 + i * 22, 28], fill=c)
    title = "python  —  no instrument attached"
    d.text(((W - d.textlength(title, font=FB)) / 2, 15), title, font=FB, fill=(125, 137, 150))
    return img


def draw_state(code_lines, out_lines, cursor=True):
    img = base_frame()
    d = ImageDraw.Draw(img)
    y = Y0
    for ln in code_lines:
        d.text((X0, y), ln, font=F, fill=colour_for(ln))
        y += LH
    if out_lines:
        y += 6
        for ln in out_lines:
            d.text((X0, y), ln, font=F, fill=OUT)
            y += LH
    if cursor:
        d.rectangle([X0, y + 4, X0 + 9, y + 18], fill=PROMPT)
    return img


def main():
    out_lines = real_output()
    src = SNIPPET.split("\n")

    frames, durations = [], []

    # 1. reveal the code line by line
    for i in range(1, len(src) + 1):
        frames.append(draw_state(src[:i], []))
        durations.append(150 if src[i - 1].strip() else 60)

    # 2. beat before the output lands
    frames.append(draw_state(src, []))
    durations.append(700)

    # 3. output lines
    for i in range(1, len(out_lines) + 1):
        frames.append(draw_state(src, out_lines[:i]))
        durations.append(320)

    # 4. hold the finished screen
    frames.append(draw_state(src, out_lines, cursor=False))
    durations.append(3200)

    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    dest = Path("docs/images/mock-demo.gif")
    dest.parent.mkdir(parents=True, exist_ok=True)
    pal[0].save(dest, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True, disposal=2)
    print(f"wrote {dest} ({dest.stat().st_size / 1024:.0f} KB, {len(frames)} frames)")
    print("captured output:", out_lines)


if __name__ == "__main__":
    main()
