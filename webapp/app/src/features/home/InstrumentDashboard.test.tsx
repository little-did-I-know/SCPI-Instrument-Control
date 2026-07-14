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
  return render(<InstrumentDashboard devices={DEVICES} scanning={false} error={null} busyKey={null} onConnect={vi.fn()} onOpen={vi.fn()} {...over} />);
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

  it("disables a held card by its device key (works for address-less mock sessions)", () => {
    const mockHeld = dev({ address: null, model: "Mock", connected: true, session_id: "m1", viewers: 0 });
    render(<InstrumentDashboard devices={[mockHeld]} scanning={false} error={null} busyKey="m1" onConnect={vi.fn()} onOpen={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Open Mock" })).toBeDisabled();
  });

  it("gives distinct Open buttons for two address-less mock sessions", () => {
    const m1 = dev({ address: null, model: "Mock", connected: true, session_id: "m1", viewers: 0 });
    const m2 = dev({ address: null, model: "Mock", connected: true, session_id: "m2", viewers: 0 });
    render(<InstrumentDashboard devices={[m1, m2]} scanning={false} error={null} busyKey={null} onConnect={vi.fn()} onOpen={vi.fn()} />);
    expect(screen.getAllByRole("button", { name: "Open Mock" })).toHaveLength(2);
  });

  it("shows a no-match message and a filtered count when the search matches nothing", async () => {
    renderDash();
    await userEvent.type(screen.getByLabelText("Filter instruments"), "zzz-no-such-device");
    expect(screen.getByText(/no instruments match/i)).toHaveTextContent("zzz-no-such-device");
    // available header count reflects the filter (0 of 2)
    expect(screen.getByText(/0 of 2/)).toBeInTheDocument();
  });
});
