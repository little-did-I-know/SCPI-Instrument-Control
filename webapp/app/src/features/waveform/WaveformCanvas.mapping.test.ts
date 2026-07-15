import { describe, expect, it } from "vitest";
import { mathTracePixels, refTracePixels } from "./WaveformCanvas";

describe("mathTracePixels", () => {
  it("returns [] for no points", () => {
    expect(mathTracePixels([], 100, 100, 8)).toEqual([]);
  });

  it("draws a flat trace at the vertical center with no NaN", () => {
    const px = mathTracePixels([5, 5, 5], 100, 100, 8);
    expect(px).toHaveLength(3);
    px.forEach((p) => {
      expect(Number.isFinite(p.x)).toBe(true);
      expect(Number.isFinite(p.y)).toBe(true);
      expect(p.y).toBeCloseTo(8 + 100 / 2); // pad + gh/2, the mid-line
    });
  });

  it("maps a symmetric trace above and below center, all finite", () => {
    const px = mathTracePixels([-1, 0, 1], 100, 100, 8);
    const center = 8 + 100 / 2;
    expect(px[1].y).toBeCloseTo(center); // 0 → center
    expect(px[0].y).toBeGreaterThan(center); // -1 below (y grows downward)
    expect(px[2].y).toBeLessThan(center); // +1 above
    px.forEach((p) => expect(Number.isFinite(p.y)).toBe(true));
  });
});

describe("refTracePixels", () => {
  it("uses the source channel's voltage scale when provided", () => {
    // 1 V/div on a 10-division canvas -> full scale 10 V; +5 V lands at the top edge
    const px = refTracePixels([0, 5], 1, 100, 100, 0);
    expect(px[0].y).toBeCloseTo(50);
    expect(px[1].y).toBeCloseTo(0);
  });

  it("falls back to auto-fit when no scale is available", () => {
    expect(refTracePixels([0, 1], undefined, 100, 100, 0)).toEqual(mathTracePixels([0, 1], 100, 100, 0));
  });
});
