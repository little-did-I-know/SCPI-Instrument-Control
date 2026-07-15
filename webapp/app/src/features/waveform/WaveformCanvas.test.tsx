import { render } from "@testing-library/react";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { WaveformCanvas } from "./WaveformCanvas";
import { setFrame, clearFrames } from "./frames";
import { useSession } from "../../store/session";

beforeEach(() => useSession.getState().clearSession());

describe("WaveformCanvas", () => {
  it("renders with a null scope without an infinite render loop", () => {
    expect(() => render(<WaveformCanvas />)).not.toThrow();
  });

  it("renders under StrictMode double-mount without throwing", () => {
    expect(() =>
      render(
        <StrictMode>
          <WaveformCanvas />
        </StrictMode>,
      ),
    ).not.toThrow();
  });

  it("renders with a math frame present without throwing", () => {
    // seed a math frame in the buffer, then render
    clearFrames();
    setFrame("M1", { t0: 0, dt: 1, points: [0, 1, 0, -1] });
    expect(() => render(<WaveformCanvas />)).not.toThrow();
    clearFrames();
  });

  it("renders with filtered and reference frames present without throwing", () => {
    clearFrames();
    setFrame("F1", { t0: 0, dt: 1, points: [1, -1, 1] });
    setFrame("REF", { t0: 0, dt: 1, points: [0, 1, 0] });
    expect(() => render(<WaveformCanvas />)).not.toThrow();
    clearFrames();
  });
});
