// Pure view-state math for the Time canvas. A View is a window over the held
// record in SECONDS (never pixels or sample indices), so every trace -- live
// channels, math, filters, the reference ghost -- maps through the same
// window regardless of its own t0/dt. `null` means "fitted to the record".

export type TimeRecord = { t0: number; dt: number; n: number };
export type View = { tCenter: number; tSpan: number };

export const DIVS_X = 14;
/** Zoom-in stops here so a fully zoomed trace shows its samples as steps, not a smooth line. */
export const MIN_PX_PER_SAMPLE = 4;

export function recordSpan(rec: TimeRecord): number {
  return rec.dt * Math.max(1, rec.n - 1);
}

export function fullView(rec: TimeRecord): View {
  const span = recordSpan(rec);
  return { tCenter: rec.t0 + span / 2, tSpan: span };
}

export function resolve(view: View | null, rec: TimeRecord): View {
  return view ?? fullView(rec);
}

function clamp(view: View, rec: TimeRecord, widthPx: number): View | null {
  const full = recordSpan(rec);
  const minSpan = Math.min(full, (rec.dt * Math.max(1, widthPx)) / MIN_PX_PER_SAMPLE);
  const tSpan = Math.min(full, Math.max(minSpan, view.tSpan));
  if (tSpan >= full) return null;
  const lo = rec.t0 + tSpan / 2;
  const hi = rec.t0 + full - tSpan / 2;
  return { tCenter: Math.min(hi, Math.max(lo, view.tCenter)), tSpan };
}

/** Scale the span by `factor` (< 1 zooms in) keeping the time under `anchorFrac` (0..1 across the canvas) fixed. */
export function zoomAt(view: View | null, rec: TimeRecord, factor: number, anchorFrac: number, widthPx: number): View | null {
  const cur = resolve(view, rec);
  const tAnchor = cur.tCenter - cur.tSpan / 2 + anchorFrac * cur.tSpan;
  const tSpan = cur.tSpan * factor;
  const tCenter = tAnchor - anchorFrac * tSpan + tSpan / 2;
  return clamp({ tCenter, tSpan }, rec, widthPx);
}

export function pan(view: View | null, rec: TimeRecord, dtSeconds: number, widthPx: number): View | null {
  const cur = resolve(view, rec);
  return clamp({ tCenter: cur.tCenter + dtSeconds, tSpan: cur.tSpan }, rec, widthPx);
}

const UNITS: [string, number][] = [
  ["s", 1],
  ["ms", 1e-3],
  ["µs", 1e-6],
  ["ns", 1e-9],
];

/** Engineering format with up to three significant digits: 0.0005 -> "500 µs". */
export function formatSeconds(seconds: number): string {
  if (seconds === 0 || !Number.isFinite(seconds)) return "0 s";
  const abs = Math.abs(seconds);
  const [unit, scale] = UNITS.find(([, s]) => abs >= s * 0.9995) ?? UNITS[UNITS.length - 1];
  const value = Number((seconds / scale).toPrecision(3));
  return `${value} ${unit}`;
}
