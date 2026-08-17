"""Render the plot-annotation demo GIF: the code, then the plots it produced.

Nothing here is mocked up. The lines rendered in the code pane are the exact
lines this script then EXECUTES, and the images held at the end are the PNGs
that execution wrote -- so the GIF cannot show an API that no longer exists, or
an output the shown code does not actually produce. If the snippet raises, no
GIF is written.

The setup the snippet needs (a captured waveform, a report to hold it) is
imported from examples/report_annotations_advanced.py rather than restated here,
so the demo and the example cannot drift apart.

Resolves its own repo root from __file__, so it can be run from anywhere:
  python scripts/media/make_annotation_gif.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[2]
DEST = REPO_ROOT / "docs" / "images" / "plot-annotations.gif"
EXAMPLE = "examples/report_annotations_advanced.py"
SIZE_BUDGET_KB = 1536

W = 880
X0, Y0 = 26, 74
LH = 24
BOTTOM_PAD = 26
RIGHT_MARGIN = 16
IMAGE_MARGIN = 26

# Shared window chrome and palette, loaded from the tour generator by path
# (scripts/ is not a package, so a plain import would not resolve).
_spec = importlib.util.spec_from_file_location("make_demo_gif", Path(__file__).with_name("make_demo_gif.py"))
_tour = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tour)

F, FB = _tour.F, _tour.FB
BG, BORDER, FG, COMMENT, OUT, PROMPT = _tour.BG, _tour.BORDER, _tour.FG, _tour.COMMENT, _tour.OUT, _tour.PROMPT
KEYWORD = (255, 166, 87)
STRING = (165, 214, 255)

TITLE = "annotating a report plot  —  python"

# Setup, executed but not shown: it is the part that is not about annotations.
# `out` is injected by the caller.
PRELUDE = """
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(REPO_ROOT / "examples"))
from report_annotations_advanced import make_step_response

from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.models.annotations import KIND_HLINE, KIND_LABEL, KIND_SPAN, KIND_VLINE, PlotAnnotation
from scpi_control.report_generator.models.report_data import ReportMetadata, TestReport, TestSection

wf = make_step_response(out / "capture.npz")
report = TestReport(
    metadata=ReportMetadata(title="Annotated Bench Check", technician="robin", test_date=datetime(2026, 8, 17)),
    sections=[TestSection(title="Step Response", waveforms=[wf])],
)
"""

# Shown AND executed, one frame per line. Keep every line inside the canvas --
# assert_fits() refuses to render anything wider.
SNIPPET = """\
# wf: a WaveformData just captured from the scope. Coordinates below are in
# DOMAIN units -- seconds here, hertz on an FFT plot -- never display units.
wf.annotations = [
    PlotAnnotation(kind=KIND_VLINE, text="trigger", x=1e-3),
    PlotAnnotation(kind=KIND_LABEL, text="overshoot", x=1.03e-3, y=3.75),
    PlotAnnotation(kind=KIND_HLINE, text="3.3 V nominal", y=3.3),
    PlotAnnotation(kind=KIND_SPAN, text="settling", x=1e-3, x_end=2.4e-3),
]
wf.caption = "Figure 1: C1 step response, 10x probe"

# A region zoom carries no annotations of its own -- it inherits the parent's,
# clipped to its own window.
wf.add_region(0.9e-3, 2.2e-3, label="Settling")

MarkdownReportGenerator().generate(report, out / "report.md")

# FFT plots, overlays, styling and sidecars: examples/report_annotations_advanced.py
""".splitlines()

# (plot filename written by the snippet, caption shown under it while it holds)
OUTPUTS = [
    ("Step_Response_0.png", "plots/Step_Response_0.png  —  all four kinds (the caption goes in the report text)"),
    ("Step_Response_0_region_1.png", "plots/Step_Response_0_region_1.png  —  the same span, clamped to the region"),
]


def run_snippet(out: Path) -> list[Path]:
    """Execute PRELUDE + SNIPPET for real and return the plots it wrote."""
    namespace = {"REPO_ROOT": REPO_ROOT, "out": out, "__name__": "__annotation_demo__"}
    exec(compile(PRELUDE + "\n" + "\n".join(SNIPPET), "<annotation-demo>", "exec"), namespace)  # noqa: S102
    written = sorted((out / "plots").glob("*.png"))
    if not written:
        raise RuntimeError("the snippet ran but wrote no plots -- refusing to render a GIF with no output")
    return written


def assert_fits(lines: list[str]) -> None:
    limit = W - X0 - RIGHT_MARGIN
    for text in lines:
        width = F.getlength(text)
        if width > limit:
            raise RuntimeError(f"code line would be clipped ({width:.0f}px > {limit}px), shorten it: {text!r}")


def line_color(text: str):
    """Enough colour to read as code: comments dim, string literals tinted."""
    stripped = text.lstrip()
    if stripped.startswith("#"):
        return COMMENT
    if '"' in text:
        return STRING
    return FG


def draw_code(height: int, lines: list[str], cursor: bool = True):
    img = _tour.base_frame(height, width=W, title=TITLE)
    d = ImageDraw.Draw(img)
    y = Y0
    for text in lines:
        d.text((X0, y), text, font=F, fill=line_color(text))
        y += LH
    if cursor:
        d.rectangle([X0, y + 4, X0 + 9, y + 18], fill=PROMPT)
    return img


def scaled_plot(path: Path) -> Image.Image:
    plot = Image.open(path).convert("RGB")
    width = W - 2 * IMAGE_MARGIN
    return plot.resize((width, round(plot.height * width / plot.width)), Image.LANCZOS)


def draw_output(height: int, plot: Image.Image, caption: str):
    img = _tour.base_frame(height, width=W, title=TITLE)
    d = ImageDraw.Draw(img)
    # Not a shell prompt: these plots came from the snippet above, and saying
    # "$ python <example>" would credit them to a run that did not happen.
    d.text((X0, Y0 - 30), "→ the code above wrote report.md and plots/", font=F, fill=PROMPT)
    top = Y0 + 6
    img.paste(plot, (IMAGE_MARGIN, top))
    d.rectangle([IMAGE_MARGIN - 1, top - 1, IMAGE_MARGIN + plot.width, top + plot.height], outline=BORDER)
    d.text((X0, top + plot.height + 10), caption, font=FB, fill=OUT)
    return img


def main() -> None:
    assert_fits(SNIPPET)
    # The snippet's closing comment points viewers at the worked example. Fail
    # here rather than ship a GIF pointing at a file that moved or was renamed.
    if not (REPO_ROOT / EXAMPLE).is_file():
        raise RuntimeError(f"{EXAMPLE} does not exist")
    if not any(EXAMPLE.split("/")[-1] in line for line in SNIPPET):
        raise RuntimeError(f"the snippet no longer points at {EXAMPLE}")
    with tempfile.TemporaryDirectory() as scratch:
        out = Path(scratch)
        written = run_snippet(out)
        names = {p.name for p in written}
        missing = [name for name, _ in OUTPUTS if name not in names]
        if missing:
            raise RuntimeError(f"the snippet did not write {missing} -- got {sorted(names)}")
        plots = [(scaled_plot(out / "plots" / name), caption) for name, caption in OUTPUTS]

    code_height = Y0 + LH * (len(SNIPPET) + 1) + BOTTOM_PAD
    output_height = Y0 + 6 + max(p.height for p, _ in plots) + LH + BOTTOM_PAD
    height = max(code_height, output_height)

    frames, durations = [], []
    for i in range(1, len(SNIPPET) + 1):
        # Blank lines and comment blocks appear with their next code line rather
        # than as a frame of their own -- a pause on nothing reads as a stall.
        if not SNIPPET[i - 1].strip() or (SNIPPET[i - 1].lstrip().startswith("#") and i < len(SNIPPET)):
            continue
        frames.append(draw_code(height, SNIPPET[:i]))
        durations.append(420)
    frames.append(draw_code(height, SNIPPET, cursor=False))
    durations.append(1100)

    for plot, caption in plots:
        frames.append(draw_output(height, plot, caption))
        durations.append(3000)

    palettised = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
    DEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEST.with_name(DEST.stem + ".tmp.gif")
    try:
        palettised[0].save(tmp, save_all=True, append_images=palettised[1:], duration=durations, loop=0, optimize=True, disposal=2)
        size_kb = tmp.stat().st_size / 1024
        if size_kb > SIZE_BUDGET_KB:
            raise RuntimeError(f"GIF is {size_kb:.0f} KB, over the {SIZE_BUDGET_KB} KB budget -- shorten holds or reduce palette depth")
        os.replace(tmp, DEST)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    print(f"wrote {DEST} ({size_kb:.0f} KB, {len(frames)} frames, {W}x{height})")
    print(f"  {len(SNIPPET)} snippet lines executed, {len(plots)} output plots held")


if __name__ == "__main__":
    sys.exit(main())
