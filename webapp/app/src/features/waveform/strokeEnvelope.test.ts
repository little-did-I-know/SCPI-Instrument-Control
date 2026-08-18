import { describe, expect, it } from "vitest";
import { strokeEnvelope, type YMap } from "./WaveformCanvas";
import type { Envelope } from "./envelope";

// jsdom has no 2D canvas context, so `WaveformCanvas`'s draw loop (reached only
// via rAF, and skipped entirely when `clientWidth` is 0) never runs `strokeEnvelope`
// in the render tests. This drives it directly with a fake recording context so the
// NaN-handling logic -- easy to get subtly wrong -- is actually exercised.
type Call = [string, ...unknown[]];

function fakeCtx(): { ctx: CanvasRenderingContext2D; calls: Call[] } {
  const calls: Call[] = [];
  const record =
    (name: string) =>
    (...args: unknown[]) => {
      calls.push([name, ...args]);
    };
  const ctx = {
    strokeStyle: "",
    fillStyle: "",
    lineWidth: 0,
    lineJoin: "",
    globalAlpha: 1,
    save: record("save"),
    restore: record("restore"),
    beginPath: record("beginPath"),
    moveTo: record("moveTo"),
    lineTo: record("lineTo"),
    closePath: record("closePath"),
    fill: record("fill"),
    stroke: record("stroke"),
    setLineDash: record("setLineDash"),
  } as unknown as CanvasRenderingContext2D;
  return { ctx, calls };
}

const y: YMap = (v) => 100 - v;

describe("strokeEnvelope: poly", () => {
  it("breaks the path across a NaN sample instead of bridging it with a straight chord", () => {
    const { ctx, calls } = fakeCtx();
    const env: Envelope = { mode: "poly", xs: Float64Array.from([0, 1, 2, 3]), ys: Float64Array.from([1, NaN, 3, 4]) };
    strokeEnvelope(ctx, env, y, "#fff", [], 2);

    const moveTos = calls.filter((c) => c[0] === "moveTo");
    const lineTos = calls.filter((c) => c[0] === "lineTo");
    expect(moveTos).toHaveLength(2); // path re-opens after the gap
    expect(lineTos).toHaveLength(1);
    for (const call of [...moveTos, ...lineTos]) {
      expect(Number.isFinite(call[2] as number)).toBe(true); // no NaN y ever reaches the path
    }
  });

  it("draws one continuous path when there is no NaN", () => {
    const { ctx, calls } = fakeCtx();
    const env: Envelope = { mode: "poly", xs: Float64Array.from([0, 1, 2]), ys: Float64Array.from([1, 2, 3]) };
    strokeEnvelope(ctx, env, y, "#fff", [], 2);

    const moveTos = calls.filter((c) => c[0] === "moveTo");
    const lineTos = calls.filter((c) => c[0] === "lineTo");
    expect(moveTos).toHaveLength(1);
    expect(lineTos).toHaveLength(2);
  });
});

describe("strokeEnvelope: band", () => {
  it("splits the fill into two subpaths and breaks the mean stroke across a NaN column", () => {
    const { ctx, calls } = fakeCtx();
    const env: Envelope = {
      mode: "band",
      mins: Float64Array.from([1, NaN, 2]),
      maxs: Float64Array.from([5, NaN, 6]),
      means: Float64Array.from([3, NaN, 4]),
    };
    strokeEnvelope(ctx, env, y, "#fff", [], 2);

    const fills = calls.filter((c) => c[0] === "fill");
    expect(fills).toHaveLength(2); // one subpath per side of the gap

    // The mean stroke is drawn after every band fill; isolate its moveTo calls
    // from the band subpaths' own moveTo calls (one per subpath).
    const lastFillIndex = calls.map((c) => c[0]).lastIndexOf("fill");
    const meanMoveTos = calls.slice(lastFillIndex + 1).filter((c) => c[0] === "moveTo");
    expect(meanMoveTos).toHaveLength(2);
  });

  it("draws one filled band whose closing reverse pass covers every column when there is no NaN", () => {
    const { ctx, calls } = fakeCtx();
    const cols = 3;
    const env: Envelope = {
      mode: "band",
      mins: Float64Array.from([1, 2, 3]),
      maxs: Float64Array.from([5, 6, 7]),
      means: Float64Array.from([3, 4, 5]),
    };
    strokeEnvelope(ctx, env, y, "#fff", [], 2);

    const fills = calls.filter((c) => c[0] === "fill");
    expect(fills).toHaveLength(1);

    // Within the single band subpath (from its beginPath to its fill), the top
    // (max) pass contributes cols-1 lineTos and the closing reverse (min) pass
    // contributes cols more.
    const fillIndex = calls.findIndex((c) => c[0] === "fill");
    const beginIndex = calls
      .slice(0, fillIndex)
      .map((c) => c[0])
      .lastIndexOf("beginPath");
    const lineTosInSubpath = calls.slice(beginIndex, fillIndex).filter((c) => c[0] === "lineTo");
    expect(lineTosInSubpath).toHaveLength(cols - 1 + cols);
  });
});
