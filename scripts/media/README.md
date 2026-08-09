# Media generators

Scripts that regenerate the images the README and docs site ship. Every one of
them drives the **real library against the built-in mock scope**, so the
pictures cannot drift from what the code actually does — no hand-drawn mockups,
no hardware required.

Run them from the repository root:

```bash
python scripts/media/make_demo_gif.py          # docs/images/mock-demo.gif
python scripts/media/make_social_preview.py    # docs/images/social-preview.png
python scripts/media/make_gui_screenshots.py   # docs/images/gui-live-view.png, gui-fft.png
```

| Script | Produces | Needs |
| --- | --- | --- |
| `make_demo_gif.py` | The README hero GIF — a tour of four examples running with no instrument attached. Each segment runs the real example as a subprocess and renders a contiguous prefix of what it actually printed, so the GIF cannot drift from the examples. | Pillow |
| `make_social_preview.py` | The 1280×640 GitHub social-preview card. Upload it under **Settings → Social preview** (see `BRANDING.md`). | Pillow |
| `make_gui_screenshots.py` | Desktop-GUI screenshots with live traces. Builds the real `MainWindow` and swaps only the `Oscilloscope` factory for one on a `MockConnection`. | PyQt6, PyQtGraph, Matplotlib |

## Notes

- **`docs/images/` is special.** `.gitignore` ignores `*.png` repository-wide and
  re-allows only `docs/**/*.png` and `resources/*.png`. An image written
  anywhere else will silently fail to commit.
- **The GUI script suppresses modal dialogs.** `MainWindow._connect_to_scope()`
  ends with a blocking `QMessageBox.information()` on success, which hangs a
  headless capture run forever.
- **No Measurements-tab capture.** The mock answers `:MEASure` queries with
  fixed constants that do not track the waveform it synthesizes, so such a
  screenshot would show numbers contradicting the trace beside them. See the
  comment in `make_gui_screenshots.py`.
- **The demo GIF shows contiguous prefixes, never filtered lines.** `TOUR`'s
  second value truncates each example's output; it never selects a subset.
  `basic_usage.py` stops at 11 lines on purpose — line 19 is the mock's fixed
  `:MEASure` value, which does not track the waveform the example configured.
  `tests/test_media_tour.py` guards that every toured example still exists and
  is still covered by the execution guard.
