// Reduce a dense trace to what one screen width can show, honestly:
//   * poly  -- the window holds no more samples than pixels: exact positions,
//              so a fully zoomed trace shows its samples as steps;
//   * band  -- denser than pixels: per-column min/max (a one-sample glitch
//              always survives) plus the column mean for a centre stroke.
// Pure and allocation-light; runs on every redraw.

export type Envelope =
  | { mode: "poly"; xs: Float64Array; ys: Float64Array }
  | { mode: "band"; mins: Float64Array; maxs: Float64Array; means: Float64Array };

const EPS = 1e-9;

export function envelope(points: ArrayLike<number>, t0: number, dt: number, tStart: number, tSpan: number, widthPx: number): Envelope | null {
  const n = points.length;
  if (n === 0 || widthPx <= 0 || tSpan <= 0 || dt <= 0) return null;
  const tEnd = tStart + tSpan;
  const i0 = Math.max(0, Math.ceil((tStart - t0) / dt - EPS));
  const i1 = Math.min(n - 1, Math.floor((tEnd - t0) / dt + EPS));
  if (i1 < i0) return null;
  const count = i1 - i0 + 1;

  if (count <= widthPx) {
    const xs = new Float64Array(count);
    const ys = new Float64Array(count);
    for (let k = 0; k < count; k++) {
      xs[k] = ((t0 + (i0 + k) * dt - tStart) / tSpan) * widthPx;
      ys[k] = points[i0 + k];
    }
    return { mode: "poly", xs, ys };
  }

  const cols = Math.floor(widthPx);
  const mins = new Float64Array(cols);
  const maxs = new Float64Array(cols);
  const means = new Float64Array(cols);
  for (let c = 0; c < cols; c++) {
    const a = Math.max(i0, Math.ceil((tStart + (c / cols) * tSpan - t0) / dt - EPS));
    // The last column is inclusive of i1 so the sample sitting exactly at tEnd is never dropped.
    const b = c === cols - 1 ? i1 : Math.min(i1, Math.ceil((tStart + ((c + 1) / cols) * tSpan - t0) / dt - EPS) - 1);
    let mn = Infinity;
    let mx = -Infinity;
    let sum = 0;
    let seen = 0;
    for (let i = a; i <= b; i++) {
      const v = points[i];
      if (v !== v) continue; // NaN
      if (v < mn) mn = v;
      if (v > mx) mx = v;
      sum += v;
      seen++;
    }
    if (seen === 0) {
      mins[c] = maxs[c] = means[c] = NaN;
    } else {
      mins[c] = mn;
      maxs[c] = mx;
      means[c] = sum / seen;
    }
  }
  return { mode: "band", mins, maxs, means };
}

/** Min/max over a trace by loop -- `Math.min(...arr)` overflows the argument limit on dense frames. */
export function traceRange(points: ArrayLike<number>): { min: number; max: number } | null {
  let mn = Infinity;
  let mx = -Infinity;
  for (let i = 0; i < points.length; i++) {
    const v = points[i];
    if (v !== v) continue;
    if (v < mn) mn = v;
    if (v > mx) mx = v;
  }
  return mn === Infinity ? null : { min: mn, max: mx };
}
