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

  // --- a read that failed must render as unknown, never as a value ---------

  it("shows an unreadable enable state as unknown, not as off", async () => {
    // enabled === null means the instrument would not tell us. On an SPD3303X
    // that is CH3's normal answer (no status bit, no OUTP3?), and painting a
    // live rail as a confident "off" is the dangerous half of the safety
    // invariant. It must read as mixed and refuse the flip.
    const unknown = { outputs: [{ ...STATE.outputs[0], enabled: null }] };
    vi.spyOn(api, "psuState").mockResolvedValue(unknown);
    const setEnable = vi.spyOn(api, "setPsuOutputEnable").mockResolvedValue(unknown);
    render(<PsuPanel />);
    const toggle = await screen.findByLabelText("Output 1 enable");
    expect(toggle).toHaveAttribute("aria-checked", "mixed");
    expect(toggle).toBeDisabled();
    expect(screen.getByText(/state unknown/i)).toBeInTheDocument();
    await userEvent.click(toggle);
    expect(setEnable).not.toHaveBeenCalled();
  });

  it("shows a failed measurement as --.--, not as 0.000", async () => {
    const unread = { outputs: [{ ...STATE.outputs[0], measured_voltage: null, measured_current: null, measured_power: null }] };
    vi.spyOn(api, "psuState").mockResolvedValue(unread);
    render(<PsuPanel />);
    await screen.findByLabelText("Output 1 voltage");
    expect(screen.queryByText("0.000")).not.toBeInTheDocument();
    expect(screen.getAllByText("--.--")).toHaveLength(3);
  });

  it("shows an unreadable setpoint as --.-- instead of an editable zero", async () => {
    const unread = { outputs: [{ ...STATE.outputs[0], voltage: null }] };
    vi.spyOn(api, "psuState").mockResolvedValue(unread);
    render(<PsuPanel />);
    const voltage = await screen.findByLabelText("Output 1 voltage");
    expect(voltage).not.toHaveValue("0.000 V");
    expect(voltage).toHaveTextContent("--.--");
    // the current limit was readable, so it stays editable
    expect(screen.getByLabelText("Output 1 current")).toHaveValue("0.500 A");
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
