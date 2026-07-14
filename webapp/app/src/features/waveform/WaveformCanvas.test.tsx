import { render } from "@testing-library/react";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { WaveformCanvas } from "./WaveformCanvas";
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
});
