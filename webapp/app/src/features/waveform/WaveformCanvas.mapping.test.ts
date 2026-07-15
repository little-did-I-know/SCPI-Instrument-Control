import { describe, expect, it } from "vitest";
import { mathTracePixels } from "./WaveformCanvas";

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
