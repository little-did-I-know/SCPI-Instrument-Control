import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AwgPanel } from "./AwgPanel";
import { ApiError, api } from "../../api/client";
import { setToken } from "../../api/token";
import { useSession } from "../../store/session";

const SESSION = { id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "SDG1032X", dialect: "", num_channels: 2, viewers: 0, owner: "", kind: "awg" as const };
const STATE = {
  channels: [
    { channel: 1, function: "SINE", frequency: 1000, amplitude: 2, offset: 0, phase: 0, enabled: false, duty_cycle: null, symmetry: null },
    { channel: 2, function: "PULSE", frequency: 10000, amplitude: 5, offset: 0.5, phase: 90, enabled: true, duty_cycle: 25, symmetry: null },
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

describe("AwgPanel", () => {
  it("renders a control set for every channel", async () => {
    vi.spyOn(api, "awgState").mockResolvedValue(STATE);
    render(<AwgPanel />);
    expect(await screen.findByLabelText("Channel 1 frequency")).toHaveValue("1000.000 Hz");
    expect(screen.getByLabelText("Channel 2 amplitude")).toHaveValue("5.000 Vpp");
  });

  it("sends a frequency change for the right channel", async () => {
    vi.spyOn(api, "awgState").mockResolvedValue(STATE);
    const setChannel = vi.spyOn(api, "setAwgChannel").mockResolvedValue(STATE);
    render(<AwgPanel />);
    const field = await screen.findByLabelText("Channel 1 frequency");
    await userEvent.clear(field);
    await userEvent.type(field, "2500{enter}");
    await waitFor(() => expect(setChannel).toHaveBeenCalledWith("abc", 1, expect.objectContaining({ frequency: 2500 })));
  });

  it("sends a function change", async () => {
    vi.spyOn(api, "awgState").mockResolvedValue(STATE);
    const setChannel = vi.spyOn(api, "setAwgChannel").mockResolvedValue(STATE);
    render(<AwgPanel />);
    await userEvent.selectOptions(await screen.findByLabelText("Channel 1 function"), "SQUARE");
    await waitFor(() => expect(setChannel).toHaveBeenCalledWith("abc", 1, { function: "SQUARE" }));
  });

  it("shows the duty cycle only for a PULSE channel", async () => {
    // The shape parameter follows the function: showing a duty field on a SINE
    // channel invites setting a value the instrument will ignore.
    vi.spyOn(api, "awgState").mockResolvedValue(STATE);
    render(<AwgPanel />);
    await screen.findByLabelText("Channel 1 frequency");
    expect(screen.queryByLabelText("Channel 1 duty cycle")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Channel 2 duty cycle")).toHaveValue("25.000 %");
  });

  it("shows the symmetry only for a RAMP channel", async () => {
    const ramp = { channels: [{ ...STATE.channels[0], function: "RAMP", symmetry: 50 }] };
    vi.spyOn(api, "awgState").mockResolvedValue(ramp);
    render(<AwgPanel />);
    expect(await screen.findByLabelText("Channel 1 symmetry")).toHaveValue("50.000 %");
    expect(screen.queryByLabelText("Channel 1 duty cycle")).not.toBeInTheDocument();
  });

  it("toggles an output", async () => {
    vi.spyOn(api, "awgState").mockResolvedValue(STATE);
    const setEnable = vi.spyOn(api, "setAwgChannelEnable").mockResolvedValue(STATE);
    render(<AwgPanel />);
    await userEvent.click(await screen.findByLabelText("Channel 1 enable"));
    await waitFor(() => expect(setEnable).toHaveBeenCalledWith("abc", 1, true));
  });

  it("kills every output from one button", async () => {
    vi.spyOn(api, "awgState").mockResolvedValue(STATE);
    const allOff = vi.spyOn(api, "allAwgOutputsOff").mockResolvedValue(STATE);
    render(<AwgPanel />);
    await userEvent.click(await screen.findByRole("button", { name: /all outputs off/i }));
    await waitFor(() => expect(allOff).toHaveBeenCalledWith("abc"));
  });

  it("does not flip the toggle before the enable request resolves (non-optimistic)", async () => {
    vi.spyOn(api, "awgState").mockResolvedValue(STATE);
    let resolveEnable: (value: typeof STATE) => void = () => {};
    const setEnable = vi.spyOn(api, "setAwgChannelEnable").mockImplementation(() => new Promise((resolve) => { resolveEnable = resolve; }));
    render(<AwgPanel />);
    const toggle = await screen.findByLabelText("Channel 1 enable");
    await userEvent.click(toggle);
    // A user must never see "on" before the instrument has confirmed it.
    expect(toggle).not.toBeChecked();
    resolveEnable(STATE);
    await waitFor(() => expect(setEnable).toHaveBeenCalled());
  });

  it("reconciles to instrument truth after a failed write", async () => {
    const reconciled = { channels: [{ ...STATE.channels[0], frequency: 9999 }, STATE.channels[1]] };
    vi.spyOn(api, "awgState").mockResolvedValueOnce(STATE).mockResolvedValueOnce(reconciled);
    vi.spyOn(api, "setAwgChannel").mockRejectedValue(new ApiError(400, "Error", "frequency out of range"));
    render(<AwgPanel />);
    const field = await screen.findByLabelText("Channel 1 frequency");
    await userEvent.clear(field);
    await userEvent.type(field, "2500{enter}");
    await screen.findByRole("alert");
    await waitFor(() => expect(field).toHaveValue("9999.000 Hz"));
  });

  it("shows an unreadable enable state as unknown, not as off", async () => {
    // AWGOutput.enabled raises when an SDG's OUTPut? response has no STATE
    // field. An energised output shown as a confident "off" is the dangerous
    // direction, so the toggle must refuse a flip whose starting point is
    // unknown.
    const unknown = { channels: [{ ...STATE.channels[0], enabled: null }] };
    vi.spyOn(api, "awgState").mockResolvedValue(unknown);
    const setEnable = vi.spyOn(api, "setAwgChannelEnable").mockResolvedValue(unknown);
    render(<AwgPanel />);
    const toggle = await screen.findByLabelText("Channel 1 enable");
    expect(toggle).toHaveAttribute("aria-checked", "mixed");
    expect(toggle).toBeDisabled();
    await userEvent.click(toggle);
    expect(setEnable).not.toHaveBeenCalled();
  });

  it("shows an unreadable setpoint as --.-- instead of an editable zero", async () => {
    const unread = { channels: [{ ...STATE.channels[0], frequency: null }] };
    vi.spyOn(api, "awgState").mockResolvedValue(unread);
    render(<AwgPanel />);
    const frequency = await screen.findByLabelText("Channel 1 frequency");
    expect(frequency).not.toHaveValue("0.000 Hz");
    expect(frequency).toHaveTextContent("--.--");
  });

  it("shows an unreadable function as unknown, not as a blank dropdown", async () => {
    // Every other field says WHY it is empty. A blank <select> is the one
    // control that leaves the user guessing whether the instrument reported
    // nothing or the app simply failed to render.
    const unread = { channels: [{ ...STATE.channels[0], function: null }] };
    vi.spyOn(api, "awgState").mockResolvedValue(unread);
    render(<AwgPanel />);
    const field = await screen.findByLabelText("Channel 1 function");
    expect(field).toHaveTextContent("--.--");
    expect(field.tagName).not.toBe("SELECT");
  });
});
