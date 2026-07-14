import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MeasurePanel } from "./MeasurePanel";
import { api } from "../../api/client";
import { useSession } from "../../store/session";

const STATE = { run_state: "STOP", timebase: 0.001, channels: { "1": { enabled: true, voltage_scale: 0.5, voltage_offset: 0, coupling: "DC", probe_ratio: 10 } }, trigger: { mode: "AUTO", source: "C1", level: 0, slope: "POS", coupling: "DC" } };

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4 });
  useSession.getState().applyState(STATE);
});
afterEach(() => vi.restoreAllMocks());

describe("MeasurePanel", () => {
  it("PUTs the selected measurement list", async () => {
    const setMeasurements = vi.spyOn(api, "setMeasurements").mockResolvedValue({ measurements: [{ channel: 1, mtype: "PKPK" }] });
    render(<MeasurePanel />);

    await userEvent.click(screen.getByLabelText("PKPK C1"));

    await waitFor(() => expect(setMeasurements).toHaveBeenCalledWith("abc", [{ channel: 1, mtype: "PKPK" }]));
  });

  it("renders streamed values and shows -- for nulls", () => {
    useSession.getState().applyMeasurements([
      { channel: 1, mtype: "PKPK", value: 2.5 },
      { channel: 1, mtype: "FREQ", value: null },
    ]);
    render(<MeasurePanel />);

    expect(screen.getByText("2.500")).toBeInTheDocument();
    expect(screen.getByText("--")).toBeInTheDocument();
  });
});
