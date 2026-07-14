import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { InstrumentDashboard } from "./InstrumentDashboard";
import type { DiscoveredDevice } from "../../api/types";

const dev = (over: Partial<DiscoveredDevice>): DiscoveredDevice => ({ address: "10.0.0.1", idn: "x", manufacturer: "Siglent", model: "M", dialect: "modern", kind: "scope", connected: false, ...over });

const DEVICES = [
  dev({ address: "10.0.0.1", model: "SDS824X HD", connected: true, session_id: "s1", viewers: 1 }),
  dev({ address: "10.0.0.2", model: "SDS1104X-E", kind: "scope", dialect: "legacy" }),
  dev({ address: "10.0.0.3", model: "SDG2042X", kind: "awg" }),
];

function renderDash(over = {}) {
  return render(<InstrumentDashboard devices={DEVICES} scanning={false} error={null} busyAddress={null} onConnect={vi.fn()} onOpen={vi.fn()} {...over} />);
}

describe("InstrumentDashboard", () => {
  it("splits held sessions from available and groups available by kind with counts", () => {
    renderDash();
    expect(screen.getByText(/your sessions/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open SDS824X HD" })).toBeInTheDocument();
    expect(screen.getByText(/oscilloscopes/i)).toBeInTheDocument(); // group header
    expect(screen.getByText(/AWGs/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect SDS1104X-E" })).toBeInTheDocument();
  });

  it("filters available devices by the search box", async () => {
    renderDash();
    await userEvent.type(screen.getByLabelText("Filter instruments"), "1104");
    expect(screen.getByText("SDS1104X-E")).toBeInTheDocument();
    expect(screen.queryByText("SDG2042X")).toBeNull();
    // held sessions are not filtered out
    expect(screen.getByText("SDS824X HD")).toBeInTheDocument();
  });

  it("shows a scanning state with no devices", () => {
    renderDash({ devices: [], scanning: true });
    expect(screen.getByText(/scanning your network/i)).toBeInTheDocument();
  });

  it("shows the error detail", () => {
    renderDash({ devices: [], error: "could not determine the local network" });
    expect(screen.getByText(/could not determine the local network/i)).toBeInTheDocument();
  });

  it("shows an empty nudge when idle with no devices", () => {
    renderDash({ devices: [] });
    expect(screen.getByText(/no instruments found/i)).toBeInTheDocument();
  });
});
