import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearFrames, getFrame, setFrame, subscribeFrames } from "./frames";

beforeEach(() => clearFrames());

describe("frame buffer", () => {
  it("stores and returns the latest frame per channel", () => {
    setFrame(1, { t0: 0, dt: 1e-6, points: [0, 1] });
    setFrame(1, { t0: 0, dt: 1e-6, points: [2, 3] });
    setFrame(2, { t0: 0, dt: 1e-6, points: [4] });
    expect(getFrame(1)?.points).toEqual([2, 3]);
    expect(getFrame(2)?.points).toEqual([4]);
  });

  it("notifies subscribers on each frame and stops after unsubscribe", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeFrames(listener);
    setFrame(1, { t0: 0, dt: 1, points: [1] });
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
    setFrame(1, { t0: 0, dt: 1, points: [2] });
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("clearFrames empties the buffer", () => {
    setFrame(1, { t0: 0, dt: 1, points: [1] });
    clearFrames();
    expect(getFrame(1)).toBeUndefined();
  });

  it("stores frames under string keys (math channels)", () => {
    setFrame("M1", { t0: 0, dt: 1, points: [1, 2] });
    expect(getFrame("M1")?.points).toEqual([1, 2]);
  });
});
