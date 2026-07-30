import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HorizontalPanel } from "./HorizontalPanel";
import { TriggerPanel } from "./TriggerPanel";
import { api } from "../../api/client";
import { useSession } from "../../store/session";

const BASE_STATE = {
  run_state: "STOP",
  timebase: 0.001,
  channels: {
    "1": { enabled: true, voltage_scale: 0.5, voltage_offset: 0, coupling: "DC", probe_ratio: null },
  },
  trigger: { mode: "AUTO", source: null, level: null, slope: null, coupling: null },
};

function stateWithTimebase(timebase: number) {
  return { ...BASE_STATE, timebase };
}

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "", kind: "scope" });
});
afterEach(() => vi.restoreAllMocks());

describe("HorizontalPanel", () => {
  it("renders without crashing before any scope state has arrived", () => {
    expect(() => render(<HorizontalPanel />)).not.toThrow();
    expect(screen.getByLabelText("Increase timebase")).toBeInTheDocument();
  });

  it("displays the timebase in engineering units, not decimals of seconds", () => {
    useSession.getState().applyState(stateWithTimebase(5e-7));
    render(<HorizontalPanel />);
    expect(screen.getByText("500 ns")).toBeInTheDocument();

    act(() => useSession.getState().applyState(stateWithTimebase(2e-6)));
    expect(screen.getByText("2 µs")).toBeInTheDocument();

    act(() => useSession.getState().applyState(stateWithTimebase(1e-3)));
    expect(screen.getByText("1 ms")).toBeInTheDocument();
  });

  it("steps 1-2-5 per decade on increment -- from 1 ms this is 2 ms, then 5 ms, then 10 ms, never 101 ms", async () => {
    useSession.getState().applyState(stateWithTimebase(0.001));
    const patchTimebase = vi.spyOn(api, "patchTimebase").mockResolvedValue(BASE_STATE);
    render(<HorizontalPanel />);

    await userEvent.click(screen.getByLabelText("Increase timebase"));
    await waitFor(() => expect(patchTimebase).toHaveBeenCalledWith("abc", 0.002));
  });

  it("continues the ladder across repeated increments, driven by the server-confirmed value", async () => {
    useSession.getState().applyState(stateWithTimebase(0.002));
    const patchTimebase = vi.spyOn(api, "patchTimebase").mockResolvedValue(BASE_STATE);
    render(<HorizontalPanel />);

    await userEvent.click(screen.getByLabelText("Increase timebase"));
    await waitFor(() => expect(patchTimebase).toHaveBeenLastCalledWith("abc", 0.005));

    act(() => useSession.getState().applyState(stateWithTimebase(0.005)));
    await userEvent.click(screen.getByLabelText("Increase timebase"));
    await waitFor(() => expect(patchTimebase).toHaveBeenLastCalledWith("abc", 0.01));
  });

  it("a sub-microsecond value is displayable and reachable by stepping down", async () => {
    useSession.getState().applyState(stateWithTimebase(1e-6));
    const patchTimebase = vi.spyOn(api, "patchTimebase").mockResolvedValue(BASE_STATE);
    render(<HorizontalPanel />);
    expect(screen.getByText("1 µs")).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Decrease timebase"));
    await waitFor(() => expect(patchTimebase).toHaveBeenCalledWith("abc", 5e-7));
  });

  it("sends the timebase as a float number of seconds, not a formatted string", async () => {
    useSession.getState().applyState(stateWithTimebase(1e-6));
    const patchTimebase = vi.spyOn(api, "patchTimebase").mockResolvedValue(BASE_STATE);
    render(<HorizontalPanel />);

    await userEvent.click(screen.getByLabelText("Decrease timebase"));
    await waitFor(() => expect(patchTimebase).toHaveBeenCalled());
    const sent = patchTimebase.mock.calls[0][1];
    expect(sent).toBe(0.0000005);
    expect(typeof sent).toBe("number");
  });

  it("cannot emit a value off the ladder -- the fastest rung has no further decrement, so negatives are unreachable", async () => {
    useSession.getState().applyState(stateWithTimebase(1e-9));
    const patchTimebase = vi.spyOn(api, "patchTimebase").mockResolvedValue(BASE_STATE);
    render(<HorizontalPanel />);

    expect(screen.getByText("1 ns")).toBeInTheDocument();
    const decrement = screen.getByLabelText("Decrease timebase");
    expect(decrement).toBeDisabled();

    await userEvent.click(decrement);
    expect(patchTimebase).not.toHaveBeenCalled();
  });

  it("cannot emit a value off the ladder at the slow end either", async () => {
    useSession.getState().applyState(stateWithTimebase(10));
    const patchTimebase = vi.spyOn(api, "patchTimebase").mockResolvedValue(BASE_STATE);
    render(<HorizontalPanel />);

    expect(screen.getByText("10 s")).toBeInTheDocument();
    const increment = screen.getByLabelText("Increase timebase");
    expect(increment).toBeDisabled();

    await userEvent.click(increment);
    expect(patchTimebase).not.toHaveBeenCalled();
  });

  // 0.101 s/div is the literal value the original free-decimal SpinBox
  // defect produced (1 ms + one 100 ms stepper click). Anyone who already
  // hit that bug has a scope sitting at exactly this off-ladder value, so
  // snapping it to the nearest rung before stepping is the realistic first
  // interaction with the new control, not an edge case.
  it("snaps an off-ladder starting value (0.101, the original defect's output) to the nearest rung before stepping up", async () => {
    useSession.getState().applyState(stateWithTimebase(0.101));
    const patchTimebase = vi.spyOn(api, "patchTimebase").mockResolvedValue(BASE_STATE);
    render(<HorizontalPanel />);

    expect(screen.getByText("100 ms")).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Increase timebase"));
    await waitFor(() => expect(patchTimebase).toHaveBeenCalledWith("abc", 0.2));
  });

  it("snaps the same off-ladder starting value (0.101) to the nearest rung before stepping down", async () => {
    useSession.getState().applyState(stateWithTimebase(0.101));
    const patchTimebase = vi.spyOn(api, "patchTimebase").mockResolvedValue(BASE_STATE);
    render(<HorizontalPanel />);

    expect(screen.getByText("100 ms")).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Decrease timebase"));
    await waitFor(() => expect(patchTimebase).toHaveBeenCalledWith("abc", 0.05));
  });
});

describe("TriggerPanel no longer owns the timebase", () => {
  it("does not render a Timebase control -- it moved to HorizontalPanel", () => {
    useSession.getState().applyState(stateWithTimebase(0.001));
    render(<TriggerPanel />);
    expect(screen.queryByLabelText("Timebase")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Increase timebase")).not.toBeInTheDocument();
  });
});
