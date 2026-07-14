import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TriggerPanel } from "./TriggerPanel";
import { api } from "../../api/client";
import { useSession } from "../../store/session";

const NULL_TRIGGER_STATE = {
  run_state: "STOP",
  timebase: 0.001,
  channels: {
    "1": { enabled: true, voltage_scale: 0.5, voltage_offset: 0, coupling: "DC", probe_ratio: null },
  },
  trigger: { mode: "AUTO", source: null, level: null, slope: null, coupling: null },
};

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4 });
});
afterEach(() => vi.restoreAllMocks());

describe("TriggerPanel null-tolerance", () => {
  it("renders without crashing when trigger fields are null", () => {
    useSession.getState().applyState(NULL_TRIGGER_STATE);
    expect(() => render(<TriggerPanel />)).not.toThrow();
    expect(screen.getByLabelText("Trigger level")).toBeInTheDocument();
  });

  it("renders without crashing before any scope state has arrived", () => {
    // scope is still null here — this is the state right after setSession(), before the
    // first WS `state` broadcast lands.
    expect(() => render(<TriggerPanel />)).not.toThrow();
    expect(screen.getByLabelText("Timebase")).toBeInTheDocument();
  });

  it("still allows setting a value on a null trigger source", async () => {
    useSession.getState().applyState(NULL_TRIGGER_STATE);
    const patchTrigger = vi.spyOn(api, "patchTrigger").mockResolvedValue(NULL_TRIGGER_STATE);
    render(<TriggerPanel />);

    await userEvent.selectOptions(screen.getByLabelText("Trigger source"), "C2");

    await waitFor(() => expect(patchTrigger).toHaveBeenCalledWith("abc", { source: "C2" }));
  });
});
