import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PsuPanel } from "./PsuPanel";
import { ApiError, api } from "../../api/client";
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

  // --- review fixes: reconciliation, the non-optimistic invariant, and the
  // in-flight lock all need their own coverage -- none of the four tests
  // above touch a failure path or a pending request at all.

  it("shows a loading state before the initial fetch resolves, then clears it", async () => {
    let resolvePsuState: (value: typeof STATE) => void = () => {};
    vi.spyOn(api, "psuState").mockImplementation(() => new Promise((resolve) => { resolvePsuState = resolve; }));
    render(<PsuPanel />);
    expect(screen.getByText(/Loading power supply state/i)).toBeInTheDocument();
    resolvePsuState(STATE);
    await waitFor(() => expect(screen.queryByText(/Loading power supply state/i)).not.toBeInTheDocument());
  });

  it("does not flip the toggle before the enable request resolves (non-optimistic)", async () => {
    vi.spyOn(api, "psuState").mockResolvedValue(STATE);
    let resolveEnable: (value: typeof STATE) => void = () => {};
    const setEnable = vi.spyOn(api, "setPsuOutputEnable").mockImplementation(() => new Promise((resolve) => { resolveEnable = resolve; }));
    render(<PsuPanel />);
    const toggle = await screen.findByLabelText("Output 1 enable");
    await userEvent.click(toggle);
    // The request is still pending: a user must never see "on" before the
    // instrument has actually confirmed it, so the control must still show
    // the last known-true (off) state here, not the requested one.
    expect(toggle).not.toBeChecked();
    resolveEnable(STATE);
    await waitFor(() => expect(setEnable).toHaveBeenCalled());
  });

  it("reconciles the toggle to server truth after a failed enable request", async () => {
    // The initial mount fetch returns the normal fixture (output 1 off); the
    // reconciliation fetch fired after the failed PATCH reports output 1 has
    // actually landed ON underneath (e.g. the PATCH's response was lost but
    // the instrument applied it). Only a real reconcile call surfaces that.
    const reconciled = { outputs: [{ ...STATE.outputs[0], enabled: true }, STATE.outputs[1]] };
    vi.spyOn(api, "psuState").mockResolvedValueOnce(STATE).mockResolvedValueOnce(reconciled);
    vi.spyOn(api, "setPsuOutputEnable").mockRejectedValue(new ApiError(500, "Error", "psu offline"));
    render(<PsuPanel />);
    const toggle = await screen.findByLabelText("Output 1 enable");
    await userEvent.click(toggle);
    await screen.findByRole("alert");
    await waitFor(() => expect(toggle).toBeChecked());
  });

  it("reconciles setpoints to server truth after a failed voltage change", async () => {
    const reconciled = { outputs: [{ ...STATE.outputs[0], voltage: 9.9 }, STATE.outputs[1]] };
    vi.spyOn(api, "psuState").mockResolvedValueOnce(STATE).mockResolvedValueOnce(reconciled);
    vi.spyOn(api, "setPsuOutput").mockRejectedValue(new ApiError(400, "Error", "output 1 not available"));
    render(<PsuPanel />);
    const field = await screen.findByLabelText("Output 1 voltage");
    await userEvent.clear(field);
    await userEvent.type(field, "12{enter}");
    await screen.findByRole("alert");
    await waitFor(() => expect(field).toHaveValue("9.900 V"));
  });

  it("ignores a second click on the same toggle while its request is in flight", async () => {
    vi.spyOn(api, "psuState").mockResolvedValue(STATE);
    let resolveEnable: (value: typeof STATE) => void = () => {};
    const setEnable = vi.spyOn(api, "setPsuOutputEnable").mockImplementation(() => new Promise((resolve) => { resolveEnable = resolve; }));
    render(<PsuPanel />);
    const toggle = await screen.findByLabelText("Output 1 enable");
    await userEvent.click(toggle);
    await userEvent.click(toggle); // disabled while pending -> must be a no-op
    resolveEnable(STATE);
    await waitFor(() => expect(setEnable).toHaveBeenCalledTimes(1));
  });
});
