import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChannelsPanel } from "./ChannelsPanel";
import { api } from "../../api/client";
import { useSession } from "../../store/session";

const STATE = {
  run_state: "STOP",
  timebase: 0.001,
  channels: {
    "1": { enabled: true, voltage_scale: 0.5, voltage_offset: 0, coupling: "DC", probe_ratio: 10 },
    "2": { enabled: false, voltage_scale: 1, voltage_offset: 0, coupling: "AC", probe_ratio: 1 },
  },
  trigger: { mode: "AUTO", source: "C1", level: 0.5, slope: "POS", coupling: "DC" },
};

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "SDS1104X-E", dialect: "legacy", num_channels: 2 });
  useSession.getState().applyState(STATE);
});
afterEach(() => vi.restoreAllMocks());

describe("ChannelsPanel", () => {
  it("renders one group per channel with its settings", () => {
    render(<ChannelsPanel />);
    expect(screen.getByText("C1")).toBeInTheDocument();
    expect(screen.getByText("C2")).toBeInTheDocument();
  });

  it("toggling enable PATCHes the channel and does not mutate the store directly", async () => {
    const patchChannel = vi.spyOn(api, "patchChannel").mockResolvedValue(STATE);
    render(<ChannelsPanel />);

    await userEvent.click(screen.getByLabelText("Enable C2"));

    await waitFor(() => expect(patchChannel).toHaveBeenCalledWith("abc", 2, { enabled: true }));
    // store still shows the server's last snapshot — the WS broadcast is the only writer
    expect(useSession.getState().scope?.channels["2"].enabled).toBe(false);
  });

  it("editing V/div by its accessible name PATCHes the channel", async () => {
    const patchChannel = vi.spyOn(api, "patchChannel").mockResolvedValue(STATE);
    render(<ChannelsPanel />);
    const field = screen.getByLabelText("V/div C1");
    await userEvent.clear(field);
    await userEvent.type(field, "2");
    await userEvent.tab();
    await waitFor(() => expect(patchChannel).toHaveBeenCalledWith("abc", 1, { voltage_scale: 2 }));
  });

  it("changing coupling PATCHes the new value", async () => {
    const patchChannel = vi.spyOn(api, "patchChannel").mockResolvedValue(STATE);
    render(<ChannelsPanel />);

    await userEvent.selectOptions(screen.getByLabelText("Coupling C1"), "AC");

    await waitFor(() => expect(patchChannel).toHaveBeenCalledWith("abc", 1, { coupling: "AC" }));
  });
});
