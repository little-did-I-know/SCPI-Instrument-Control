import { describe, expect, it } from "vitest";
import { formatSeconds, fullView, pan, recordSpan, resolve, zoomAt, MIN_PX_PER_SAMPLE } from "./view";

const REC = { t0: -0.007, dt: 1e-6, n: 14_001 }; // 14 ms record centred on 0
const W = 1400;

describe("view math", () => {
  it("fullView spans the record and centres it", () => {
    expect(recordSpan(REC)).toBeCloseTo(0.014, 9);
    expect(fullView(REC)).toEqual({ tCenter: expect.closeTo(0, 9), tSpan: expect.closeTo(0.014, 9) });
    expect(resolve(null, REC)).toEqual(fullView(REC));
  });

  it("zoomAt halves the span and keeps the anchored time fixed", () => {
    const v = zoomAt(null, REC, 0.5, 0.25, W)!;
    // anchor was at t = -0.007 + 0.25*0.014 = -0.0035; after zoom it must sit at 25% of the new span
    expect(v.tSpan).toBeCloseTo(0.007, 9);
    expect(v.tCenter - v.tSpan / 2 + 0.25 * v.tSpan).toBeCloseTo(-0.0035, 9);
  });

  it("zooming out past the record returns null (fit)", () => {
    const zoomed = zoomAt(null, REC, 0.5, 0.5, W);
    expect(zoomAt(zoomed, REC, 4, 0.5, W)).toBeNull();
    expect(zoomAt(null, REC, 2, 0.5, W)).toBeNull();
  });

  it("zoom in stops at MIN_PX_PER_SAMPLE pixels per sample", () => {
    let v: ReturnType<typeof zoomAt> = null;
    for (let i = 0; i < 40; i++) v = zoomAt(v, REC, 0.5, 0.5, W);
    expect(v!.tSpan).toBeCloseTo((REC.dt * W) / MIN_PX_PER_SAMPLE, 12);
  });

  it("pan moves the centre and clamps to the record edges", () => {
    const zoomed = zoomAt(null, REC, 0.25, 0.5, W)!; // 3.5 ms window centred on 0
    expect(pan(zoomed, REC, 0.001, W)!.tCenter).toBeCloseTo(0.001, 9);
    const clamped = pan(zoomed, REC, 1, W)!;
    expect(clamped.tCenter + clamped.tSpan / 2).toBeCloseTo(REC.t0 + recordSpan(REC), 9);
    const clampedLeft = pan(zoomed, REC, -1, W)!;
    expect(clampedLeft.tCenter - clampedLeft.tSpan / 2).toBeCloseTo(REC.t0, 9);
  });

  it("panning a fitted view is a no-op that stays fitted", () => {
    expect(pan(null, REC, 0.001, W)).toBeNull();
  });

  it("a record with a single sample never divides by zero", () => {
    const one = { t0: 0, dt: 1e-6, n: 1 };
    expect(zoomAt(null, one, 0.5, 0.5, W)).toBeNull();
    expect(Number.isFinite(fullView(one).tSpan)).toBe(true);
  });
});

describe("formatSeconds", () => {
  it.each([
    [0, "0 s"],
    [1.5, "1.5 s"],
    [0.0005, "500 µs"],
    [1e-3, "1 ms"],
    [2.5e-6, "2.5 µs"],
    [-3e-9, "-3 ns"],
    [0.0123456, "12.3 ms"],
  ])("formats %s as %s", (s, text) => {
    expect(formatSeconds(s)).toBe(text);
  });
});
