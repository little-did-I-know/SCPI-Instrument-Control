import { beforeEach, describe, expect, it } from "vitest";
import { useSession } from "./session";
import type { ScopeState, SessionInfo } from "../api/types";

const SESSION: SessionInfo = { id: "abc", label: "bench", mock: false, address: "192.168.1.50", state: "connected", idn: "Siglent,SDS824X HD,1,1", model: "SDS824X HD", dialect: "modern", num_channels: 4, viewers: 0, owner: "", kind: "scope" };

const STATE: ScopeState = {
  run_state: "STOP",
  timebase: 0.001,
  channels: { "1": { enabled: true, voltage_scale: 0.5, voltage_offset: 0, coupling: "DC", probe_ratio: 10 } },
  trigger: { mode: "AUTO", source: "C1", level: 0.5, slope: "POS", coupling: "DC" },
};

beforeEach(() => useSession.getState().clearSession());

describe("session store", () => {
  it("starts empty and disconnected", () => {
    const s = useSession.getState();
    expect(s.session).toBeNull();
    expect(s.scope).toBeNull();
    expect(s.status).toBe("disconnected");
  });

  it("applyState replaces the scope snapshot", () => {
    useSession.getState().setSession(SESSION);
    useSession.getState().applyState(STATE);
    expect(useSession.getState().scope?.timebase).toBe(0.001);
    expect(useSession.getState().scope?.channels["1"].enabled).toBe(true);
    useSession.getState().applyState({ ...STATE, timebase: 0.002 });
    expect(useSession.getState().scope?.timebase).toBe(0.002);
  });

  it("tolerates null trigger fields (legacy/modern degrade)", () => {
    useSession.getState().applyState({ ...STATE, trigger: { mode: "AUTO", source: null, level: null, slope: null, coupling: null } });
    expect(useSession.getState().scope?.trigger.level).toBeNull();
  });

  it("clearSession resets everything", () => {
    useSession.getState().setSession(SESSION);
    useSession.getState().applyState(STATE);
    useSession.getState().applyMeasurements([{ channel: 1, mtype: "PKPK", value: 2 }]);
    useSession.getState().clearSession();
    const s = useSession.getState();
    expect(s.session).toBeNull();
    expect(s.scope).toBeNull();
    expect(s.measurements).toEqual([]);
    expect(s.status).toBe("disconnected");
  });

  it("applyMeasurements stores nulls as-is", () => {
    useSession.getState().applyMeasurements([{ channel: 1, mtype: "FREQ", value: null }]);
    expect(useSession.getState().measurements[0].value).toBeNull();
  });

  it("setSession clears both kind slices, so a switch never shows the previous instrument", () => {
    // Both, not just the one belonging to the outgoing kind: with two kinds a
    // psu -> psu switch would otherwise paint the previous supply's outputs
    // under the new supply's name until its first frame lands.
    useSession.getState().setSession(SESSION);
    useSession.getState().applyState(STATE);
    useSession.getState().applyPsuState({ outputs: [{ output: 1, voltage: 3.3, current: 0.5, enabled: false, measured_voltage: 0, measured_current: 0, measured_power: 0 }] });
    useSession.getState().setSession({ ...SESSION, id: "next", kind: "psu" });
    expect(useSession.getState().scope).toBeNull();
    expect(useSession.getState().psu).toBeNull();
    expect(useSession.getState().session?.id).toBe("next");
  });

  it("applyPsuState replaces the psu snapshot, and clearSession resets it", () => {
    useSession.getState().applyPsuState({ outputs: [{ output: 1, voltage: 3.3, current: 0.5, enabled: false, measured_voltage: 0, measured_current: 0, measured_power: 0 }] });
    expect(useSession.getState().psu?.outputs[0].output).toBe(1);
    useSession.getState().clearSession();
    expect(useSession.getState().psu).toBeNull();
  });
});

describe("view slice", () => {
  const STATE = { run_state: "STOP", timebase: 0.001, channels: {}, trigger: { mode: "AUTO", source: "C1", level: 0, slope: "POS", coupling: "DC" } };
  beforeEach(() => useSession.getState().clearSession());

  it("starts fitted and stores a view", () => {
    expect(useSession.getState().view).toBeNull();
    useSession.getState().setView({ tCenter: 0, tSpan: 1e-3 });
    expect(useSession.getState().view).toEqual({ tCenter: 0, tSpan: 1e-3 });
  });

  it("keeps the view across a state update with the same timebase", () => {
    useSession.getState().applyState(STATE);
    useSession.getState().setView({ tCenter: 0, tSpan: 1e-3 });
    useSession.getState().applyState({ ...STATE, run_state: "RUN" });
    expect(useSession.getState().view).toEqual({ tCenter: 0, tSpan: 1e-3 });
  });

  it("resets the view when the timebase changes", () => {
    useSession.getState().applyState(STATE);
    useSession.getState().setView({ tCenter: 0, tSpan: 1e-3 });
    useSession.getState().applyState({ ...STATE, timebase: 0.002 });
    expect(useSession.getState().view).toBeNull();
  });

  it("resets the view on session change and clear", () => {
    useSession.getState().setView({ tCenter: 0, tSpan: 1e-3 });
    useSession.getState().setSession({ id: "x", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "", kind: "scope" as const });
    expect(useSession.getState().view).toBeNull();
    useSession.getState().setView({ tCenter: 0, tSpan: 1e-3 });
    useSession.getState().clearSession();
    expect(useSession.getState().view).toBeNull();
  });
});
