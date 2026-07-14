import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { ReadoutStrip } from "./ReadoutStrip";
import { useSession } from "../../store/session";

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4 });
  useSession.getState().applyState({
    run_state: "TRIGD",
    timebase: 0.001,
    channels: { "1": { enabled: true, voltage_scale: 0.5, voltage_offset: 0, coupling: "DC", probe_ratio: 10 }, "2": { enabled: false, voltage_scale: 1, voltage_offset: 0, coupling: "AC", probe_ratio: 1 } },
    trigger: { mode: "AUTO", source: "C1", level: 0, slope: "POS", coupling: "DC" },
  });
});

describe("ReadoutStrip", () => {
  it("shows a card for each enabled channel with its Vpp when measured", () => {
    useSession.getState().applyMeasurements([{ channel: 1, mtype: "PKPK", value: 2.5 }]);
    render(<ReadoutStrip />);
    expect(screen.getByText("C1")).toBeInTheDocument();
    expect(screen.queryByText("C2")).toBeNull();
    expect(screen.getByText(/2\.500/)).toBeInTheDocument();
  });

  it("shows placeholder dashes when no measurement has arrived", () => {
    render(<ReadoutStrip />);
    expect(screen.getByText("--.--")).toBeInTheDocument();
  });
});
