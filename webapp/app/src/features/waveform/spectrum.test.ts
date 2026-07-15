import { describe, expect, it, beforeEach } from "vitest";
import { clearSpectrum, getSpectrum, setSpectrum, subscribeSpectrum } from "./spectrum";
import type { SpectrumFrame } from "../../api/types";

const FRAME: SpectrumFrame = { channel: 1, f0: 0, df: 10, points: [1, 2], db: true, window: "hanning", peaks: [], thd: null };

beforeEach(() => clearSpectrum());

describe("spectrum buffer", () => {
  it("stores and clears the latest frame", () => {
    setSpectrum(FRAME);
    expect(getSpectrum()?.points).toEqual([1, 2]);
    clearSpectrum();
    expect(getSpectrum()).toBeNull();
  });

  it("notifies subscribers on set", () => {
    let calls = 0;
    const unsubscribe = subscribeSpectrum(() => { calls += 1; });
    setSpectrum(FRAME);
    setSpectrum(null);
    unsubscribe();
    setSpectrum(FRAME);
    expect(calls).toBe(2);
  });
});
