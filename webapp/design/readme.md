# SCPI Instrument Control — Design System

A design system reconstructed from the **SCPI Instrument Control** project: a
universal Python library **and PyQt6 desktop application** for controlling
SCPI-compatible bench test equipment — oscilloscopes, power supplies (PSU),
arbitrary waveform generators (AWG) and data-acquisition (DAQ) units — over
Ethernet/LAN.

This system captures the visual language of that desktop app so you can design
new screens, dialogs, slides and marketing that look like they belong to the
product.

## Sources

Everything here was reconstructed from real source, not memory:

- **GitHub — primary source:** https://github.com/little-did-I-know/SCPI-Instrument-Control
  (branch `main`). The visual language was lifted from the PyQt6 GUI code under
  `scpi_control/gui/` — `main_window.py`, `widgets/*.py` (channel_control,
  trigger_control, measurement_panel, psu_control, terminal_widget,
  waveform_display_pg, daq_data_view, …) — where every colour, font, padding and
  radius is set via `setStyleSheet` / `pg.mkPen` / `QColor`. Values here are
  lifted verbatim.
- **Brand assets:** `resources/Test Equipment.png` / `.ico` and the wide variant
  (copied into `resources/`), plus `docs/images/*.png` reference screenshots.
- **Docs:** `docs/gui/interface.md` and `docs/gui/overview.md` for the window
  anatomy, tab inventory and interaction model.

Explore the repository above to build higher-fidelity designs — the widget
source is the ground truth for any control this system doesn't yet cover.

---

## The two surfaces

The product lives on **two coexisting surfaces**, and every design decision
follows from which one you are on:

1. **Desktop chrome (light).** The window, menus, toolbar, control-panel tabs
   and form controls are **native, light-themed Qt widgets** — white/`#f3f3f3`
   surfaces, thin grey borders, black text. The app does *not* apply a global
   dark theme.
2. **The scope canvas (dark).** The waveform display, live-data plots, SCPI
   terminal and measured-value readouts are **dark** (`#0d1117` / `#1e1e1e`),
   with a dotted division grid and bright, saturated content. This is the
   brand's signature — a piece of instrument on a desktop.

---

## CONTENT FUNDAMENTALS

How the product writes copy:

- **Voice: terse, technical, imperative.** UI actions are bare verbs — “Connect”,
  “Disconnect”, “Run”, “Stop”, “Single”, “Force Trigger”, “Auto Scale”,
  “Clear All”. No marketing fluff in the app.
- **Domain vocabulary is exact and unexpanded.** Uses instrument terminology
  and abbreviations as-is: `V/div`, `Vpp`, `Vrms`, `SNR`, `THD`, `C1`–`C4`,
  `TDIV`, `DC/AC/GND`, `POS/NEG`, `AUTO/NORMAL/SINGLE/STOP`, `20MHz`, `µs`, `kHz`.
  Never soften these into plain English.
- **Person:** instructional docs address the reader as **you** (“Enter your
  oscilloscope's IP address”, “Press Utility on the oscilloscope”). Log/status
  lines are impersonal and system-voiced (“=== Oscilloscope Connected ===”,
  “ERROR: Not connected to oscilloscope”).
- **Casing:** Title Case for buttons, tabs and menus (“Capture Waveform”,
  “Visual Measure”). SCPI commands are UPPERCASE (`*IDN?`, `C1:VDIV 1V`).
  Units keep canonical casing (`kHz`, `mV`, `ms`, `Ω`).
- **Numbers are formatted with fixed precision + unit.** Readouts read
  `0.000 V`, `2.000 A`, `1.000 kHz`, `35.0 ns` — 3 decimals for volts/amps,
  auto-ranged SI units for time/frequency.
- **Emoji:** used **sparingly and only as functional status/section markers** in
  docs and a few labels — 🟢🟡🔴🟠 for connection state, ⚠ on the safety
  “All Outputs OFF” button, and occasional 🎨/📊 section flags in docs. Not
  decorative; do not sprinkle emoji into the UI.
- **Tone:** confident, helpful, lab-grade. Docs include “Quick Tip” / “!!! tip”
  callouts. The vibe is *engineer's instrument*, not consumer gadget.

---

## VISUAL FOUNDATIONS

**Colour.**
- *Light chrome:* `--app-bg #f3f3f3`, `--surface #ffffff`, borders `#cfcfcf` /
  `#a0a0a0`, text `#1a1a1a` with `#888` hints.
- *Dark scope canvas:* `--scope-canvas #0d1117` (GitHub-dark, chosen in
  `waveform_display_pg.py`), panels `#1e1e1e`/`#2d2d2d`, borders/grid `#30363d`,
  text `#e6edf3` with `#8b949e` muted ticks.
- *Channel identity* is the strongest colour signal: **CH1 gold `#FFD700`,
  CH2 cyan `#00CED1`, CH3 magenta `#FF1493`, CH4 green `#00FF00`** (with vibrant
  trace variants `#FFDC32 / #40E0D0 / #FF69B4 / #32FF64` on the canvas), plus
  DAQ extras (tomato, purple, sea-green, orange). Channel colour appears on the
  group-box title, cursor labels and the trace.
- *Semantic actions:* success/Connect green `#4CAF50`, danger/Disconnect red
  `#f44336`, safety-critical crimson `#DC143C`, warning/CC-mode orange `#FFA500`,
  info blue `#2196F3`. Live readouts are pure green `#00ff00`.
- No brand gradients. No purple/blue hero gradients. Colour is functional
  (identity + status), never decorative.

**Type.** Two families. `--font-ui` = Segoe UI (the native Windows Qt font);
`--font-mono` = Courier New — used for **every** numeric readout, the SCPI
terminal, FFT peak tables and command examples. Sizes track Qt point sizes
(8/9/10/11/12pt → 11–16px) with larger 20/28px front-panel readouts. Weights
400/600/700.

**Spacing & density.** Dense and utilitarian: 5px layout margins, 6px control
padding, 6×20px buttons, 10px on the safety button. Do not inflate to an 8px
web grid — the app is tight on purpose.

**Radius, borders, elevation.** Small radii: 3px on controls/inputs/buttons,
5px on emphasis/safety buttons. Focused inputs get a **2px solid green**
(`#4CAF50`) border — a signature detail from the terminal input. Borders are
1px hairlines. The UI is **flat**: shadows are reserved for floating dialogs and
dropdown popups only — no card drop-shadows in the panels.

**Backgrounds & texture.** Flat fills only. The scope canvas carries a **dotted
14×10 division grid** (`#30363d`, ~0.2 alpha) with a slightly brighter centre
crosshair — that grid *is* the texture. No photographic backgrounds, no
patterns, no blur/glass. The one photographic asset is the project hero image
(bench instruments on black), used for PyPI/GitHub/docs — not inside the app.

**Cards / containers.** The container primitive is the **GroupBox** — a 1px
bordered rectangle with a title sitting in a notch on the top border, the title
colour-coded to its channel. No rounded cards, no left-border-accent cards.

**Motion.** Minimal and functional. Real-time plotting is the only continuous
motion (the trace scrolls while running). Buttons transition background colour
on hover/press over ~90ms; the connecting-status dot pulses. No easing-heavy
entrances, no bounce, no decorative loops.

**Hover / press states.** Buttons darken on press (Connect `#4CAF50` → hover
`#45a049` → pressed `#3d8b40`; Disconnect `#f44336` → `#da190b` → `#c1170a`);
default light buttons go `#f0f0f0` → `#e8e8e8` → `#dcdcdc`; ghost/toolbar
actions get a faint grey wash. Inputs/selects darken their border on hover and
turn the border green on focus.

---

## ICONOGRAPHY

- **The app is almost icon-free.** The reference main window uses **text labels,
  not icons**, for toolbar actions (“Run”, “Stop”, “Single”, “Capture
  Waveform”). There is **no bundled icon font and no SVG icon set** in the
  source — do not invent one.
- **Status is communicated with coloured dots**, described in docs as the
  emoji 🟢 (connected) / 🟡 (connecting) / 🔴 (disconnected) / 🟠 (error). The
  `StatusIndicator` component reproduces these as coloured dots, which is the
  correct, on-brand treatment.
- **Emoji as functional glyphs** appear in a few places: ⚠ on the safety
  “All Outputs OFF” button, and 🎨/📊 as doc section markers. Use emoji only in
  these functional roles.
- **Steppers/chevrons** are the only ui glyphs (spin-box ▲▼, combo-box ▾),
  rendered as unicode, matching native Qt.
- **If you need an icon set** for a new surface, add a CDN line icon set
  (e.g. Lucide) at a 1.5–2px stroke to sit with the hairline borders, and note
  the addition — but prefer text labels, as the product does. *(No icon set is
  wired in by default.)*
- **Brand image:** `resources/Test Equipment.png` (the hero render of an
  oscilloscope, PSU and AWG on black) is the closest thing to a logo. There is
  **no vector logo or wordmark** in the source; render the product name in type
  (see the Brand → Wordmark card) wherever a mark is needed.

---

## Components

Reusable React primitives, reconstructed from the PyQt6 widget vocabulary the
source defines. Import from `window.SCPIInstrumentControlDesignSystem_b228f5`.

**Controls** (`components/controls/`)
- **Button** — push button (QPushButton) with `default` / `primary` (Connect) /
  `danger` (Disconnect) / `critical` (safety) / `ghost` (toolbar) variants.
- **Checkbox** — QCheckBox toggle with label (Enable, Bandwidth Limit, Grid…).
- **ComboBox** — QComboBox dropdown (Coupling, Probe, Trigger source…).
- **SpinBox** — QDoubleSpinBox numeric field with unit suffix + steppers.

**Layout** (`components/layout/`)
- **GroupBox** — titled bordered panel with a colour-coded title; the control
  cluster container.
- **Tabs** — QTabWidget control-panel tab bar.
- **Toolbar** (+ **ToolbarSeparator**) — the main-window action strip.

**Data & readouts** (`components/data/`)
- **Reading** — monospace live readout in scope green, with CV/CC mode badge.
- **StatusIndicator** — coloured connection-status dot + label.
- **DataTable** — QTableWidget with alternating rows (light + dark variants).
- **Terminal** — the SCPI command console (colour-coded output + input row).

Each component directory carries `<Name>.jsx`, `<Name>.d.ts`, `<Name>.prompt.md`
and a `*.card.html` showcase.

## UI Kits

- **`ui_kits/instrument-gui-modern/`** — an **interactive recreation of the
  oscilloscope main window** in the modern **light-console** style: header with
  wordmark + status pill, a standout live-readout strip (per-channel Vpp/freq
  cards with channel-colour accents), left control rail (Channels / Trigger /
  Measure / Terminal), and the dark waveform canvas framed as the instrument
  window. Click **Connect** to bring it online, enable channels to draw traces,
  and Run/Stop the live view. Built by composing the components above. Backed by
  the `--lc-*` (light) and `--console-*` (dark alternate) theme tokens.

## Foundations (Design System tab)

Specimen cards live in `guidelines/` and populate the Design System tab, grouped
**Colors** (channels, traces, semantic, light chrome, scope dark, readout/
terminal), **Type** (UI face, mono/readout face, scale), **Spacing** (scale,
radius/borders, density-in-use) and **Brand** (wordmark, hero image).

---

## Repo index (manifest)

- `styles.css` — root entry; `@import`s all tokens. Consumers link this only.
- `tokens/` — `colors.css`, `scope.css`, `typography.css`, `spacing.css`,
  `fonts.css`, `theme-console.css` (modern light `--lc-*` + dark `--console-*`).
- `components/` — `controls/`, `layout/`, `data/`.
- `ui_kits/instrument-gui-modern/` — main-window recreation, modern light
  console (`index.html`, `app.jsx`, `WaveformCanvas.jsx`).
- `guidelines/` — foundation specimen cards.
- `resources/` — brand hero image + icon, reference screenshots.
- `SKILL.md` — Agent-Skill wrapper.
- Generated (do not edit): `_ds_bundle.js`, `_ds_manifest.json`,
  `_adherence.oxlintrc.json`.

---

## ⚠ Font substitution — needs your input

The desktop app uses **Segoe UI** (Windows system font) for UI and **Courier
New** for readouts/terminal. Neither ships a font file:

- **Segoe UI** → the specimen cards load **Source Sans 3** (Google Fonts) as a
  cross-platform stand-in; `--font-ui` still lists `"Segoe UI"` first so it
  renders natively on Windows. On Windows this is exact; elsewhere it's an
  approximation.
- **Courier New** is near-universal and kept as-is (`"Cascadia Code"` is listed
  first as an optional upgrade if you upload it).

**If you have the licensed Segoe UI (or want a different UI face), please share
the font files and I'll wire them in via `@font-face` for pixel-exact
specimens.**
