import { act, render, screen, waitFor } from "@testing-library/react";
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

  it("keeps the server's selection after a remount instead of re-seeding stale local state", async () => {
    const setMeasurements = vi.spyOn(api, "setMeasurements").mockResolvedValue({ measurements: [] });
    // server truth: PKPK C1 is already active and streaming
    useSession.getState().applyMeasurements([{ channel: 1, mtype: "PKPK", value: 2.5 }]);

    const view = render(<MeasurePanel />);
    expect(screen.getByLabelText("PKPK C1")).toBeInTheDocument();

    // simulate a rail-tab switch away and back
    view.unmount();
    render(<MeasurePanel />);

    // now toggle a DIFFERENT measurement — the PUT must preserve the server's existing PKPK C1
    await userEvent.click(screen.getByLabelText("FREQ C1"));

    await waitFor(() =>
      expect(setMeasurements).toHaveBeenCalledWith("abc", [
        { channel: 1, mtype: "PKPK" },
        { channel: 1, mtype: "FREQ" },
      ]),
    );
  });

  // The remount test above only exercises the seed path (the store is already correct at mount).
  // The selection must track the store on EVERY render: a measurement that arrives on the stream
  // while the panel stays mounted must survive the next toggle's full-replacement PUT.
  it("computes the PUT from the server's latest list, not a local mirror captured at mount", async () => {
    const setMeasurements = vi.spyOn(api, "setMeasurements").mockResolvedValue({ measurements: [] });
    render(<MeasurePanel />); // store starts with no measurements

    // server truth arrives on the stream after mount (restored session / another client / late broadcast)
    act(() => useSession.getState().applyMeasurements([{ channel: 1, mtype: "PKPK", value: 2.5 }]));

    await userEvent.click(screen.getByLabelText("FREQ C1"));

    await waitFor(() =>
      expect(setMeasurements).toHaveBeenCalledWith("abc", [
        { channel: 1, mtype: "PKPK" },
        { channel: 1, mtype: "FREQ" },
      ]),
    );
  });
});
