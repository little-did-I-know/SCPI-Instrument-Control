"""Generate the GitHub social-preview card (1280x640) for SCPI-Instrument-Control.

The waveform drawn on the card is not decoration: it is a real capture pulled
from the library's own mock scope, so the picture shows the thing the README
claims. Run from the repo root:

    python make_social_preview.py
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.signal_synth import SignalSpec

W, H = 1280, 640

BG = (11, 15, 20)
GRID = (26, 34, 44)
GRID_AXIS = (38, 50, 63)
TRACE = (245, 197, 24)  # Siglent C1 yellow
TRACE_GLOW = (245, 197, 24, 70)
WHITE = (240, 245, 250)
MUTED = (138, 156, 172)
ACCENT = (56, 189, 248)  # cyan

FONT_DIR = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"


def font(names, size):
    for n in names:
        p = FONT_DIR / n
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except OSError:
                pass
    return ImageFont.load_default()


def BOLD(size):
    return font(["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], size)


def REG(size):
    return font(["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], size)


def MONO(size):
    return font(["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf"], size)


def capture():
    """Pull a real 1 kHz / 3.3 V square wave from the mock scope."""
    scope = Oscilloscope(
        "mock",
        connection=MockConnection(
            "mock",
            channel_states={1: True},
            signals={1: SignalSpec(kind="square", frequency=1000.0, amplitude=1.65, offset=1.65)},
            # ~5 ms window at 2 MSa/s -> five full 1 kHz periods across the card.
            sample_rate=2e6,
            timebase=3.5e-3,
        ),
    )
    scope.connect()
    wf = scope.get_waveform(channel=1)
    scope.disconnect()
    return wf


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # --- oscilloscope graticule -------------------------------------------
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=GRID, width=1)

    # --- real waveform, bottom third --------------------------------------
    wf = capture()
    v = wf.voltage
    band_top, band_bot = 486, 566
    vmin, vmax = float(v.min()), float(v.max())
    span = (vmax - vmin) or 1.0

    step = max(1, len(v) // (W * 2))
    pts = []
    for i in range(0, len(v), step):
        x = i / (len(v) - 1) * W
        y = band_bot - (v[i] - vmin) / span * (band_bot - band_top)
        pts.append((x, y))

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).line(pts, fill=TRACE_GLOW, width=11, joint="curve")
    img.paste(Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB"), (0, 0))
    d = ImageDraw.Draw(img)
    d.line(pts, fill=TRACE, width=3, joint="curve")

    # --- text -------------------------------------------------------------
    d.text((72, 86), "SCPI Instrument Control", font=BOLD(72), fill=WHITE)
    d.text((72, 178), "Drive your whole bench from Python", font=REG(38), fill=MUTED)

    chips = ["Oscilloscopes", "AWGs", "Power supplies", "DAQ"]
    x = 74
    f = REG(24)
    for c in chips:
        w = d.textlength(c, font=f)
        d.rounded_rectangle([x, 246, x + w + 34, 292], radius=23, outline=(45, 60, 75), width=2)
        d.text((x + 17, 256), c, font=f, fill=ACCENT)
        x += w + 34 + 14

    d.text((72, 330), "Siglent  ·  Tektronix  ·  LeCroy  ·  Keysight     LAN · USB · GPIB · serial", font=REG(23), fill=(96, 114, 130))

    d.rounded_rectangle([72, 376, 660, 424], radius=8, fill=(19, 26, 34))
    d.text((92, 388), "pip install SCPI-Instrument-Control", font=MONO(25), fill=(186, 230, 253))

    # trace caption
    cap = "real capture from the built-in mock scope — 1 kHz · Vpp 3.28 V · no hardware attached"
    d.text(((W - d.textlength(cap, font=REG(20))) / 2, 600), cap, font=REG(20), fill=(96, 114, 130))

    out = Path("docs/images/social-preview.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)
    print(f"wrote {out} ({out.stat().st_size / 1024:.1f} KB, {img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
