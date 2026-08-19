import { describe, expect, it } from "vitest";
import { envelope, traceRange } from "./envelope";

describe("envelope", () => {
  it("returns exact sample positions when the window holds no more samples than pixels", () => {
    const env = envelope([0, 1, 2, 3], 0, 1, 0, 3, 300)!;
    expect(env.mode).toBe("poly");
    if (env.mode !== "poly") return;
    expect(Array.from(env.xs)).toEqual([0, 100, 200, 300]);
    expect(Array.from(env.ys)).toEqual([0, 1, 2, 3]);
  });

  it("restricts poly output to the visible window", () => {
    const env = envelope([0, 1, 2, 3, 4, 5], 0, 1, 2, 2, 200)!; // window t in [2, 4]
    expect(env.mode).toBe("poly");
    if (env.mode !== "poly") return;
    expect(Array.from(env.ys)).toEqual([2, 3, 4]);
    expect(Array.from(env.xs)).toEqual([0, 100, 200]);
  });

  it("returns per-column min/max/mean when the window is denser than pixels", () => {
    // 8 samples across 4 columns -> 2 samples per column
    const env = envelope([0, 10, 1, 9, 2, 8, 3, 7], 0, 1, 0, 8, 4)!;
    expect(env.mode).toBe("band");
    if (env.mode !== "band") return;
    expect(Array.from(env.mins)).toEqual([0, 1, 2, 3]);
    expect(Array.from(env.maxs)).toEqual([10, 9, 8, 7]);
    expect(Array.from(env.means)).toEqual([5, 5, 5, 5]);
  });

  it("a single-sample glitch survives decimation", () => {
    const points = new Float32Array(100_000).fill(0);
    points[54_321] = 5;
    const env = envelope(points, 0, 1e-6, 0, 0.1, 1000)!;
    expect(env.mode).toBe("band");
    if (env.mode !== "band") return;
    expect(Math.max(...Array.from(env.maxs))).toBe(5);
    expect(env.maxs[543]).toBe(5); // 54321 / (100000/1000)
  });

  it("marks columns with no samples as NaN and skips NaN samples", () => {
    const env = envelope([1, NaN, 3, 4], 0, 1, 0, 3, 2)!; // 4 samples, 2 columns
    expect(env.mode).toBe("band");
    if (env.mode !== "band") return;
    expect(env.mins[0]).toBe(1); // NaN neighbour ignored
    expect(env.maxs[1]).toBe(4);
    const empty = envelope([1, 2], 0, 1, 0, 1, 1)!; // 2 samples in 1 column: dense -> band
    expect(empty.mode).toBe("band");
  });

  it("returns null for an empty trace, a zero-width plot, or a window outside the record", () => {
    expect(envelope([], 0, 1, 0, 1, 100)).toBeNull();
    expect(envelope([1, 2], 0, 1, 0, 1, 0)).toBeNull();
    expect(envelope([1, 2], 0, 1, 10, 1, 100)).toBeNull();
  });
});

describe("traceRange", () => {
  it("handles 100k samples without spreading into Math.min/max", () => {
    const points = new Float32Array(100_000).map((_, i) => Math.sin(i));
    const r = traceRange(points)!;
    expect(r.min).toBeCloseTo(-1, 3);
    expect(r.max).toBeCloseTo(1, 3);
  });

  it("returns null for empty or all-NaN input", () => {
    expect(traceRange([])).toBeNull();
    expect(traceRange([NaN, NaN])).toBeNull();
  });
});
