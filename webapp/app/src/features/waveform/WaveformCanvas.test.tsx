import { render } from "@testing-library/react";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { WaveformCanvas, currentRecord } from "./WaveformCanvas";
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

  it("renders a dense Float32Array frame and a zoomed view without throwing", () => {
    clearFrames();
    const dense = new Float32Array(100_000).map((_, i) => Math.sin(i / 100));
    setFrame(1, { t0: -0.05, dt: 1e-6, seq: 1, points: dense });
    useSession.getState().setView({ tCenter: 0, tSpan: 0.001 });
    expect(() => render(<WaveformCanvas />)).not.toThrow();
    clearFrames();
  });

  it("shows the fit control only while zoomed", () => {
    const { queryByText, rerender } = render(<WaveformCanvas />);
    expect(queryByText(/fit/)).toBeNull();
    useSession.getState().setView({ tCenter: 0, tSpan: 0.001 });
    rerender(<WaveformCanvas />);
    expect(queryByText(/fit/)).not.toBeNull();
  });

  it("currentRecord prefers the first enabled channel with data, then computed traces", () => {
    clearFrames();
    setFrame("M1", { t0: 1, dt: 1, points: [0, 1] });
    expect(currentRecord([1, 2])).toEqual({ t0: 1, dt: 1, n: 2 });
    setFrame(2, { t0: 5, dt: 2, points: [0, 1, 2] });
    expect(currentRecord([1, 2])).toEqual({ t0: 5, dt: 2, n: 3 });
    clearFrames();
    expect(currentRecord([1])).toBeNull();
  });

  it("blocks text selection on the canvas via CSS instead of cancelling pointerdown", () => {
    const { container } = render(<WaveformCanvas />);
    const canvas = container.querySelector("canvas");
    expect(canvas?.style.userSelect).toBe("none");
  });
});
