import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SpectrumCanvas, formatHz, spectrumTracePixels } from "./SpectrumCanvas";
import { clearSpectrum, setSpectrum } from "./spectrum";
import { api } from "../../api/client";
import { useSession } from "../../store/session";

const FRAME = { channel: 1, f0: 0, df: 10, points: [-60, -20, -60, -80], db: true, window: "hanning", peaks: [[10, -20]] as [number, number][], thd: 1.5 };

beforeEach(() => {
  clearSpectrum();
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "" });
});
afterEach(() => vi.restoreAllMocks());

describe("spectrumTracePixels", () => {
  it("maps min to the bottom margin and max to the top margin", () => {
    const px = spectrumTracePixels([-80, -20], 100, 100, 0);
    expect(px[0].y).toBeCloseTo(95);
    expect(px[1].y).toBeCloseTo(5);
  });

  it("handles a flat spectrum without dividing by zero", () => {
    const px = spectrumTracePixels([-30, -30], 100, 100, 0);
    expect(px.every((p) => Number.isFinite(p.y))).toBe(true);
  });
});

describe("formatHz", () => {
  it("scales units", () => {
    expect(formatHz(50)).toBe("50.0 Hz");
    expect(formatHz(1500)).toBe("1.5 kHz");
    expect(formatHz(20e6)).toBe("20.0 MHz");
  });
});

describe("SpectrumCanvas", () => {
  it("shows the empty state and PATCHes enabled on click", async () => {
    const patch = vi.spyOn(api, "patchSpectrum").mockResolvedValue({ enabled: true, channel: 1, window: "hanning", db: true });
    render(<SpectrumCanvas />);
    await userEvent.click(screen.getByRole("button", { name: /enable spectrum/i }));
    expect(patch).toHaveBeenCalledWith("abc", { enabled: true });
  });

  it("renders a canvas without throwing when a frame is present", () => {
    setSpectrum(FRAME);
    expect(() => render(<SpectrumCanvas />)).not.toThrow();
  });
});
