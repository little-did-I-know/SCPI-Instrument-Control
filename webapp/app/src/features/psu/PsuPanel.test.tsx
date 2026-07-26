import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PsuPanel } from "./PsuPanel";
import { api } from "../../api/client";
import { setToken } from "../../api/token";
import { useSession } from "../../store/session";

const SESSION = { id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "SPD3303X", dialect: "", num_channels: 2, viewers: 0, owner: "", kind: "psu" as const };
const STATE = {
  outputs: [
    { output: 1, voltage: 3.3, current: 0.5, enabled: false, measured_voltage: 0.0, measured_current: 0.0, measured_power: 0.0 },
    { output: 2, voltage: 5.0, current: 1.0, enabled: true, measured_voltage: 5.01, measured_current: 0.12, measured_power: 0.6 },
  ],
};

beforeEach(() => {
  localStorage.clear();
  setToken("test-token");
  useSession.getState().clearSession();
  useSession.getState().setSession(SESSION);
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("PsuPanel", () => {
  it("renders every output with its measured values", async () => {
    vi.spyOn(api, "psuState").mockResolvedValue(STATE);
    render(<PsuPanel />);
    await waitFor(() => expect(screen.getByText(/5\.01/)).toBeInTheDocument());
    expect(screen.getByText(/0\.12/)).toBeInTheDocument();
    expect(screen.getByText(/0\.6/)).toBeInTheDocument();
  });

  it("sends a voltage change for the right output", async () => {
    vi.spyOn(api, "psuState").mockResolvedValue(STATE);
    const setOutput = vi.spyOn(api, "setPsuOutput").mockResolvedValue(STATE);
    render(<PsuPanel />);
    const field = await screen.findByLabelText("Output 1 voltage");
    await userEvent.clear(field);
    await userEvent.type(field, "12{enter}");
    await waitFor(() => expect(setOutput).toHaveBeenCalledWith("abc", 1, expect.objectContaining({ voltage: 12 })));
  });

  it("toggles an output", async () => {
    vi.spyOn(api, "psuState").mockResolvedValue(STATE);
    const setEnable = vi.spyOn(api, "setPsuOutputEnable").mockResolvedValue(STATE);
    render(<PsuPanel />);
    await userEvent.click(await screen.findByLabelText("Output 1 enable"));
    await waitFor(() => expect(setEnable).toHaveBeenCalledWith("abc", 1, true));
  });

  it("exposes enable state accessibly, not only by colour", async () => {
    vi.spyOn(api, "psuState").mockResolvedValue(STATE);
    render(<PsuPanel />);
    expect(await screen.findByLabelText("Output 1 enable")).not.toBeChecked();
    expect(await screen.findByLabelText("Output 2 enable")).toBeChecked();
  });
});
